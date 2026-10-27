# Documentação: Consulta de Estrutura Curricular (TADS 2019)

Ferramenta web para consultar a estrutura curricular do curso TADS (UFRN, versão 2019) em três bancos de dados diferentes (PostgreSQL, MongoDB e Neo4j), comparando o tempo de resposta de cada um.

## 1. O que o projeto faz

- Guarda as 35 disciplinas do TADS 2019 e seus pré-requisitos nos **três bancos ao mesmo tempo**, cada um com seu próprio modelo de dados (relacional, documentos e grafo).
- Oferece uma **página web** onde você escolhe o banco, o tipo de consulta e o termo de busca.
- Mostra o resultado e **dois tempos**: o da consulta no servidor e o total (ida e volta do navegador).
- Permite **cadastrar outro curso** apenas adicionando um arquivo JSON, sem mudar código.

## 2. Visão geral da arquitetura

```
Navegador (frontend/index.html)
        |  HTTP  GET /api/query?db=...&tipo=...&q=...
        v
API FastAPI (backend/main.py)
   |-- PostgreSQL  (consulta SQL)
   |-- MongoDB     (consulta de documentos)
   |-- Neo4j       (consulta Cypher)
        ^
        |  carga inicial
backend/load.py  <--  data/*.json
```

Os três bancos rodam em contêineres Docker na sua própria máquina (`docker-compose.yml`). Isso é importante para a comparação ser justa: todos no mesmo ambiente, sem um local e outro em nuvem.

## 3. Estrutura de pastas

| Caminho | Para que serve |
|---|---|
| `docker-compose.yml` | Sobe PostgreSQL, MongoDB e Neo4j em contêineres. |
| `data/tads_2019.json` | Fonte única dos dados do curso (disciplinas e pré-requisitos). |
| `backend/load.py` | Lê os JSON de `data/` e carrega nos três bancos. |
| `backend/main.py` | API web (FastAPI) com as consultas nos três bancos; também serve a página. |
| `backend/requirements.txt` | Bibliotecas Python necessárias. |
| `frontend/index.html` | Interface web (HTML, CSS e JavaScript em um só arquivo). |
| `docs/modelos-logicos.md` | Os três modelos lógicos, justificativas e escolha final. |
| `README.md` | Resumo rápido de como rodar. |

## 4. Pré-requisitos para usar

- **Docker** e **Docker Compose** instalados.
- **Python 3.10 ou superior** com `pip`.
- Portas livres no seu computador: 5432 (ou 5433, veja a seção 10), 27017, 7474 e 7687.

## 5. Como usar, passo a passo

### 5.1 Subir os bancos

```bash
docker compose up -d
```

O Neo4j demora cerca de 30 segundos para ficar pronto. Para conferir se os três contêineres estão de pé:

```bash
docker compose ps
```

### 5.2 Instalar as dependências Python

```bash
cd backend
pip install -r requirements.txt
```

### 5.3 Configurar a porta do PostgreSQL (se você usou 5433)

```bash
# Linux/macOS
export PG_DSN=postgresql://tads:tads@localhost:5433/tads

# Windows PowerShell
$env:PG_DSN="postgresql://tads:tads@localhost:5433/tads"
```

Essa variável precisa estar definida no mesmo terminal em que você rodar os dois próximos comandos.

### 5.4 Carregar os dados

```bash
python load.py
```

Saída esperada: `carregado: TADS-2019 35 disciplinas`. O script pode ser rodado de novo a qualquer momento: ele apaga o curso e recarrega, sem duplicar nada.

### 5.5 Iniciar a aplicação

```bash
uvicorn main:app --reload
```

Abra `http://localhost:8000` no navegador.

### 5.6 Usar a página

1. Escolha o **curso** (hoje só existe TADS 2019).
2. Escolha o **tipo de consulta** (seção 6).
3. Escolha o **banco** (PostgreSQL, MongoDB ou Neo4j).
4. Digite o termo e clique em **Consultar** (ou aperte Enter).
5. Veja a tabela de resultados e a linha com os tempos.
6. Clique em **Comparar os 3 bancos** para rodar a mesma consulta nos três e ver os tempos lado a lado.

## 6. Tipos de consulta

| Tipo | O que digitar | O que retorna |
|---|---|---|
| Buscar por nome ou código | Parte do nome ou do código (ex.: `banco`, `TAD01`) | Disciplinas que contêm o termo. |
| Pré-requisitos diretos | Código exato (ex.: `TAD0156`) | Disciplinas exigidas diretamente, com o número do grupo. |
| Pré-requisitos em cadeia | Código exato | Todas as disciplinas que precisam ser cursadas antes, em qualquer nível, com o `nivel` (1 = direto, 2 = pré-requisito do pré-requisito, e assim por diante). |
| Disciplinas que ela libera | Código exato | Disciplinas que têm a informada como pré-requisito. |

### Como ler a coluna `grupo`

A regra E/OU do PDF foi representada por grupos:

- **Grupos diferentes = E** (todos são obrigatórios).
- **Mesmo grupo = OU** (basta uma das disciplinas do grupo).

Exemplos: TAD0156 tem três grupos (TAD0102, TAD0012 e TAD0103), então exige as três. TAD0029 tem um só grupo com TAD0009, TAD0103 e TAD0111, então basta uma delas.

### Como ler os tempos

- **Consulta (ms):** tempo gasto só dentro da API executando a consulta no banco.
- **Total (ms):** tempo medido no navegador, incluindo a rede local e o processamento da API.

Com tão poucos dados, as diferenças entre bancos são de poucos milissegundos e sofrem ruído. A primeira chamada de cada banco costuma ser mais lenta (abre conexão); por isso o botão de comparação chama duas vezes e exibe a segunda.

## 7. O que cada arquivo faz por dentro

### 7.1 `docker-compose.yml`

Define três serviços:

- **postgres** (versão 16): usuário `tads`, senha `tads`, banco `tads`, porta 5432.
- **mongo** (versão 7): sem senha, porta 27017.
- **neo4j** (versão 5): usuário `neo4j`, senha `tadspass123`, portas 7474 (navegador web do Neo4j) e 7687 (conexão Bolt).

É só para uso local e didático; não use essas senhas fora do seu computador.

### 7.2 `data/tads_2019.json`

Tem três blocos:

- `curso`: `chave` (identificador único, ex.: `TADS-2019`), `sigla`, `nome`, `instituicao`, `versao`.
- `disciplinas`: lista de objetos com `codigo`, `nome` e `creditos`.
- `prerequisitos`: lista de objetos com `disciplina` e `grupos` (lista de listas de códigos).

Exemplo:

```json
{ "disciplina": "TAD0156", "grupos": [["TAD0102"], ["TAD0012"], ["TAD0103"]] }
```

### 7.3 `backend/load.py`

Funções principais:

- `arestas(data)`: transforma os `grupos` em trios (disciplina, requisito, número do grupo), usados pelos três carregadores.
- `load_pg(data)`: cria as tabelas (se não existirem), apaga o curso e insere curso, disciplinas e pré-requisitos.
- `load_mongo(data)`: grava o curso na coleção `cursos` e cada disciplina na coleção `disciplinas`, com os pré-requisitos embutidos, além dos índices.
- `load_neo(data)`: cria a restrição de unicidade, apaga o curso, cria os nós `Curso` e `Disciplina` e as relações `TEM` e `REQUER`.

No final (`__main__`), percorre todos os arquivos `data/*.json` e carrega cada um nos três bancos.

### 7.4 `backend/main.py`

- Abre uma conexão com cada banco quando a aplicação inicia.
- Define quatro consultas por banco (`q_pg`, `q_mongo`, `q_neo`), cada uma com a técnica própria do banco:
  - **Busca:** `ILIKE` no PostgreSQL, expressão regular no MongoDB, `CONTAINS` no Neo4j.
  - **Pré-requisitos diretos:** junção de tabelas, leitura do documento e travessia de uma aresta.
  - **Disciplinas liberadas:** junção inversa, busca no índice `requisitos` e travessia no sentido contrário.
  - **Cadeia de pré-requisitos:** `WITH RECURSIVE`, `$graphLookup` e caminho de tamanho variável `[:REQUER*1..]`.
- Expõe dois endpoints:
  - `GET /api/cursos`: lista os cursos encontrados em `data/`.
  - `GET /api/query`: executa a consulta e devolve `db`, `tipo`, `total`, `tempo_ms` e `resultado`.
- Serve a pasta `frontend/` como página inicial.

Exemplo de chamada direta:

```
http://localhost:8000/api/query?db=neo4j&tipo=prereq_transitivo&curso=TADS-2019&q=TAD0157
```

Parâmetros de `/api/query`:

| Parâmetro | Valores |
|---|---|
| `db` | `postgres`, `mongo`, `neo4j` |
| `tipo` | `busca`, `prereq`, `dependentes`, `prereq_transitivo` |
| `curso` | Chave do curso, ex.: `TADS-2019` |
| `q` | Termo de busca ou código da disciplina |

A documentação interativa da API (gerada automaticamente pelo FastAPI) fica em `http://localhost:8000/docs`.

### 7.5 `frontend/index.html`

Página única sem dependências externas. Ela carrega a lista de cursos, monta a chamada para `/api/query`, mede o tempo total com `performance.now()` e desenha a tabela. O botão "Comparar os 3 bancos" chama os três bancos em sequência, duas vezes cada.

## 8. Os três modelos de dados em resumo

- **PostgreSQL (relacional):** três tabelas, `curso`, `disciplina` e `prerequisito`. A tabela `prerequisito` liga duas disciplinas e guarda o `grupo`. Há chaves estrangeiras e unicidade de (`curso_id`, `codigo`).
- **MongoDB (documentos):** um documento por disciplina, com `grupos` (regra E/OU) e `requisitos` (lista achatada, usada em índice e no `$graphLookup`).
- **Neo4j (grafo):** nós `Curso` e `Disciplina`; relação `TEM` do curso para cada disciplina; relação `REQUER` com a propriedade `grupo`, de uma disciplina para seu pré-requisito.

Os diagramas, as justificativas e a escolha final estão em `docs/modelos-logicos.md`.

## 9. Como cadastrar outro curso

1. Copie `data/tads_2019.json` para um novo arquivo, ex.: `data/outro_2024.json`.
2. Troque os dados de `curso` (a `chave` precisa ser única, ex.: `OUTRO-2024`).
3. Liste as disciplinas e os pré-requisitos no mesmo formato.
4. Rode `python load.py`.
5. Reinicie ou recarregue a página: o curso novo aparece na lista.

Nenhuma linha de código precisa mudar, e é isso que torna a abordagem genérica.

## 10. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| `address already in use` na porta 5432 | Há um PostgreSQL local usando a porta | Mude no compose para `"5433:5432"` e defina `PG_DSN` com a porta 5433. |
| Erro igual para 27017, 7474 ou 7687 | Outro serviço usa a porta | Mude o número da esquerda no compose e ajuste `MONGO_URI` ou `NEO_URI`. |
| `connection refused` ao rodar `load.py` | O banco ainda não terminou de subir | Espere alguns segundos (o Neo4j é o mais lento) e rode de novo. |
| Erro de autenticação no Neo4j | Senha diferente da configurada | Use `tadspass123` ou defina `NEO_PASS`. Se já havia um contêiner antigo do Neo4j, rode `docker compose down -v` e suba de novo. |
| A página abre mas as consultas dão erro | A carga de dados não foi feita ou a variável `PG_DSN` não está no terminal do `uvicorn` | Rode `python load.py` e confira a variável. |
| Consulta de código retorna vazio | Código digitado incorretamente | Use o código exato, ex.: `TAD0156`; confira com a busca por nome. |

## 11. Como parar e limpar tudo

| Objetivo | Comando |
|---|---|
| Parar a aplicação web | `Ctrl+C` no terminal do `uvicorn` |
| Parar os bancos, mantendo os dados | `docker compose stop` |
| Parar e remover os contêineres, mantendo os dados | `docker compose down` |
| Remover tudo, inclusive os dados | `docker compose down -v` |

Depois de um `down -v`, é preciso rodar `python load.py` de novo.

## 12. Limitações e cuidados

- Os pré-requisitos foram **lidos das setas do PDF** e devem ser conferidos antes da entrega, principalmente TAD0156, TAD0029 e TAD0204.
- Optativas (16 créditos) e atividades complementares (180 h) não estão cadastradas como disciplinas.
- A estrutura não registra o período (semestre) sugerido de cada disciplina.
- Senhas e portas do `docker-compose.yml` servem apenas para uso local e estudo.
- Com apenas 35 disciplinas, as diferenças de tempo entre os bancos são pequenas; para uma comparação mais forte, repita as medições várias vezes ou aumente o volume de dados.
