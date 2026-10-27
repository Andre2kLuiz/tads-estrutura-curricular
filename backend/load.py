"""Carrega todos os data/*.json nos 3 bancos. Idempotente (recarrega o curso)."""
import glob, json, os
import psycopg
from pymongo import MongoClient
from neo4j import GraphDatabase

PG = os.getenv("PG_DSN", "postgresql://tads:tads@localhost:5433/tads")
MONGO = os.getenv("MONGO_URI", "mongodb://localhost:27017")
NEO = os.getenv("NEO_URI", "bolt://localhost:7687")
NEO_AUTH = ("neo4j", os.getenv("NEO_PASS", "tadspass123"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS curso(
  id SERIAL PRIMARY KEY, chave TEXT UNIQUE NOT NULL, sigla TEXT, nome TEXT,
  instituicao TEXT, versao TEXT);
CREATE TABLE IF NOT EXISTS disciplina(
  id SERIAL PRIMARY KEY, curso_id INT NOT NULL REFERENCES curso(id) ON DELETE CASCADE,
  codigo TEXT NOT NULL, nome TEXT NOT NULL, creditos INT, UNIQUE(curso_id, codigo));
CREATE TABLE IF NOT EXISTS prerequisito(
  disciplina_id INT REFERENCES disciplina(id) ON DELETE CASCADE,
  requisito_id  INT REFERENCES disciplina(id) ON DELETE CASCADE,
  grupo INT NOT NULL,  -- mesmo grupo = OU; grupos diferentes = E
  PRIMARY KEY(disciplina_id, requisito_id));
CREATE INDEX IF NOT EXISTS ix_prereq_req ON prerequisito(requisito_id);
"""

def arestas(data):
    for p in data["prerequisitos"]:
        for g, grupo in enumerate(p["grupos"], 1):
            for r in grupo:
                yield p["disciplina"], r, g

def load_pg(data):
    ch = data["curso"]["chave"]
    with psycopg.connect(PG, autocommit=True) as c:
        c.execute(SCHEMA)
        c.execute("DELETE FROM curso WHERE chave=%s", (ch,))
        cu = data["curso"]
        cid = c.execute("INSERT INTO curso(chave,sigla,nome,instituicao,versao) VALUES(%s,%s,%s,%s,%s) RETURNING id",
                        (ch, cu["sigla"], cu["nome"], cu["instituicao"], cu["versao"])).fetchone()[0]
        ids = {}
        for d in data["disciplinas"]:
            ids[d["codigo"]] = c.execute(
                "INSERT INTO disciplina(curso_id,codigo,nome,creditos) VALUES(%s,%s,%s,%s) RETURNING id",
                (cid, d["codigo"], d["nome"], d["creditos"])).fetchone()[0]
        for d, r, g in arestas(data):
            c.execute("INSERT INTO prerequisito VALUES(%s,%s,%s)", (ids[d], ids[r], g))

def load_mongo(data):
    ch = data["curso"]["chave"]
    db = MongoClient(MONGO).tads
    db.cursos.replace_one({"_id": ch}, {"_id": ch, **data["curso"]}, upsert=True)
    db.disciplinas.delete_many({"curso": ch})
    pre = {p["disciplina"]: p["grupos"] for p in data["prerequisitos"]}
    docs = []
    for d in data["disciplinas"]:
        grupos = pre.get(d["codigo"], [])
        docs.append({**d, "curso": ch, "grupos": grupos,
                     "requisitos": [r for g in grupos for r in g]})
    db.disciplinas.insert_many(docs)
    db.disciplinas.create_index([("curso", 1), ("codigo", 1)], unique=True)
    db.disciplinas.create_index([("curso", 1), ("requisitos", 1)])

def load_neo(data):
    ch = data["curso"]["chave"]
    with GraphDatabase.driver(NEO, auth=NEO_AUTH) as drv, drv.session() as s:
        s.run("CREATE CONSTRAINT disc_uni IF NOT EXISTS FOR (d:Disciplina) REQUIRE (d.curso, d.codigo) IS UNIQUE")
        s.run("MATCH (n) WHERE n.curso=$c OR n.chave=$c DETACH DELETE n", c=ch)
        s.run("CREATE (:Curso {chave:$c, nome:$n, versao:$v})", c=ch, n=data["curso"]["nome"], v=data["curso"]["versao"])
        s.run("""MATCH (c:Curso {chave:$c}) UNWIND $ds AS d
                 CREATE (c)-[:TEM]->(:Disciplina {curso:$c, codigo:d.codigo, nome:d.nome, creditos:d.creditos})""",
              c=ch, ds=data["disciplinas"])
        s.run("""UNWIND $rs AS r
                 MATCH (a:Disciplina {curso:$c, codigo:r.d}), (b:Disciplina {curso:$c, codigo:r.r})
                 CREATE (a)-[:REQUER {grupo:r.g}]->(b)""",
              c=ch, rs=[{"d": d, "r": r, "g": g} for d, r, g in arestas(data)])

if __name__ == "__main__":
    base = os.path.join(os.path.dirname(__file__), "..", "data", "*.json")
    for f in sorted(glob.glob(base)):
        data = json.load(open(f, encoding="utf-8"))
        for fn in (load_pg, load_mongo, load_neo):
            fn(data)
        print("carregado:", data["curso"]["chave"], len(data["disciplinas"]), "disciplinas")
