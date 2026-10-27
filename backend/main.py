import glob, json, os, re, time
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
import psycopg
from pymongo import MongoClient
from neo4j import GraphDatabase

PG = os.getenv("PG_DSN", "postgresql://tads:tads@localhost:5433/tads")
MONGO = os.getenv("MONGO_URI", "mongodb://localhost:27017")
NEO = os.getenv("NEO_URI", "bolt://localhost:7687")
NEO_AUTH = ("neo4j", os.getenv("NEO_PASS", "tadspass123"))
BASE = os.path.dirname(__file__)

pg = psycopg.connect(PG, autocommit=True)
mongo = MongoClient(MONGO).tads.disciplinas
neo = GraphDatabase.driver(NEO, auth=NEO_AUTH)

def rows_pg(sql, *params):
    cur = pg.execute(sql, params)
    cols = [c.name for c in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]

def rows_neo(cypher, **params):
    with neo.session() as s:
        return [r.data() for r in s.run(cypher, **params)]

# ---------- PostgreSQL ----------
J = "FROM disciplina d JOIN curso c ON c.id=d.curso_id"
def q_pg(tipo, q, curso):
    if tipo == "busca":
        return rows_pg(f"SELECT d.codigo,d.nome,d.creditos {J} WHERE c.chave=%s AND (d.codigo ILIKE %s OR d.nome ILIKE %s) ORDER BY d.codigo", curso, f"%{q}%", f"%{q}%")
    if tipo == "prereq":
        return rows_pg(f"SELECT r.codigo,r.nome,r.creditos,p.grupo {J} JOIN prerequisito p ON p.disciplina_id=d.id JOIN disciplina r ON r.id=p.requisito_id WHERE c.chave=%s AND d.codigo=%s ORDER BY p.grupo,r.codigo", curso, q)
    if tipo == "dependentes":
        return rows_pg(f"SELECT x.codigo,x.nome,x.creditos {J} JOIN prerequisito p ON p.requisito_id=d.id JOIN disciplina x ON x.id=p.disciplina_id WHERE c.chave=%s AND d.codigo=%s ORDER BY x.codigo", curso, q)
    if tipo == "prereq_transitivo":
        return rows_pg(f"""WITH RECURSIVE t AS (
              SELECT p.requisito_id, 1 AS nivel {J} JOIN prerequisito p ON p.disciplina_id=d.id WHERE c.chave=%s AND d.codigo=%s
              UNION
              SELECT p.requisito_id, t.nivel+1 FROM prerequisito p JOIN t ON p.disciplina_id=t.requisito_id)
            SELECT r.codigo,r.nome,r.creditos,MIN(t.nivel) AS nivel FROM t JOIN disciplina r ON r.id=t.requisito_id
            GROUP BY r.codigo,r.nome,r.creditos ORDER BY nivel,r.codigo""", curso, q)

# ---------- MongoDB ----------
P = {"_id": 0, "codigo": 1, "nome": 1, "creditos": 1}
def q_mongo(tipo, q, curso):
    if tipo == "busca":
        rx = {"$regex": re.escape(q), "$options": "i"}
        return list(mongo.find({"curso": curso, "$or": [{"codigo": rx}, {"nome": rx}]}, P).sort("codigo", 1))
    if tipo == "prereq":
        d = mongo.find_one({"curso": curso, "codigo": q})
        if not d: return []
        info = {x["codigo"]: x for x in mongo.find({"curso": curso, "codigo": {"$in": d["requisitos"]}}, P)}
        return [{**info[r], "grupo": g} for g, grp in enumerate(d["grupos"], 1) for r in sorted(grp)]
    if tipo == "dependentes":
        return list(mongo.find({"curso": curso, "requisitos": q}, P).sort("codigo", 1))
    if tipo == "prereq_transitivo":
        res = mongo.aggregate([
            {"$match": {"curso": curso, "codigo": q}},
            {"$graphLookup": {"from": "disciplinas", "startWith": "$requisitos", "connectFromField": "requisitos",
                              "connectToField": "codigo", "as": "anc", "depthField": "nivel",
                              "restrictSearchWithMatch": {"curso": curso}}},
            {"$unwind": "$anc"}, {"$replaceRoot": {"newRoot": "$anc"}},
            {"$project": {**P, "nivel": {"$add": ["$nivel", 1]}}},
            {"$sort": {"nivel": 1, "codigo": 1}}])
        return list(res)

# ---------- Neo4j ----------
R = "d.codigo AS codigo, d.nome AS nome, d.creditos AS creditos"
def q_neo(tipo, q, curso):
    if tipo == "busca":
        return rows_neo(f"MATCH (d:Disciplina {{curso:$c}}) WHERE toLower(d.codigo) CONTAINS toLower($q) OR toLower(d.nome) CONTAINS toLower($q) RETURN {R} ORDER BY codigo", c=curso, q=q)
    if tipo == "prereq":
        return rows_neo("MATCH (:Disciplina {curso:$c,codigo:$q})-[r:REQUER]->(d) RETURN " + R + ", r.grupo AS grupo ORDER BY grupo, codigo", c=curso, q=q)
    if tipo == "dependentes":
        return rows_neo("MATCH (d)-[:REQUER]->(:Disciplina {curso:$c,codigo:$q}) RETURN " + R + " ORDER BY codigo", c=curso, q=q)
    if tipo == "prereq_transitivo":
        return rows_neo("MATCH path=(:Disciplina {curso:$c,codigo:$q})-[:REQUER*1..]->(d) RETURN " + R + ", min(length(path)) AS nivel ORDER BY nivel, codigo", c=curso, q=q)

ENGINES = {"postgres": q_pg, "mongo": q_mongo, "neo4j": q_neo}
TIPOS = {"busca", "prereq", "dependentes", "prereq_transitivo"}

app = FastAPI(title="Consulta de Estrutura Curricular")

@app.get("/api/cursos")
def cursos():
    out = []
    for f in sorted(glob.glob(os.path.join(BASE, "..", "data", "*.json"))):
        c = json.load(open(f, encoding="utf-8"))["curso"]
        out.append({"chave": c["chave"], "nome": f'{c["sigla"]} {c["versao"]} - {c["nome"]}'})
    return out

@app.get("/api/query")
def query(db: str, tipo: str, q: str = "", curso: str = "TADS-2019"):
    if db not in ENGINES or tipo not in TIPOS:
        raise HTTPException(400, "db ou tipo inválido")
    t0 = time.perf_counter()
    resultado = ENGINES[db](tipo, q.strip(), curso)
    return {"db": db, "tipo": tipo, "total": len(resultado),
            "tempo_ms": round((time.perf_counter() - t0) * 1000, 3), "resultado": resultado}

app.mount("/", StaticFiles(directory=os.path.join(BASE, "..", "frontend"), html=True), name="ui")
