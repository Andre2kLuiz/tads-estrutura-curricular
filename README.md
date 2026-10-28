# Consulta de Estrutura Curricular (TADS 2019)

PostgreSQL + MongoDB + Neo4j, todos locais via Docker (mesmo ambiente, comparação justa), API FastAPI e UI web simples.

## Rodar
```bash
docker compose up -d                 # aguarde ~30 s o Neo4j subir
cd backend
pip install -r requirements.txt
python load.py                       # carrega data/*.json nos 3 bancos
uvicorn main:app --reload            # abra http://localhost:8000
```

## Cadastrar outro curso
Copie `data/tads_2019.json` para `data/<sigla>_<ano>.json`, troque `curso.chave`, as disciplinas e os pré-requisitos
(`grupos`: lista de grupos; grupos diferentes = E, dentro do grupo = OU), rode `python load.py` e escolha o curso na UI.
Nenhum código muda.

## Consultas da UI
Busca por nome/código, pré-requisitos diretos, pré-requisitos em cadeia, disciplinas liberadas. A resposta mostra o tempo da
consulta no servidor e o tempo total (ida e volta); "Comparar os 3 bancos" roda a mesma consulta nos três.

## Atenção
Os pré-requisitos em `data/tads_2019.json` foram lidos das setas do PDF; confiram com o PDF antes de entregar.
Optativas (16 cr.) e atividades complementares (180 h) não entram como disciplinas.


Passo a Passo Sequential

1. Derrubar os contêineres e remover os volumes (Limpeza Total):
O segredo aqui é o parâmetro -v (ou --volumes). Ele força o Docker a apagar os storages virtuais onde os dados do PostgreSQL, MongoDB e Neo4j ficam salvos no seu disco, garantindo que nada do estado anterior permaneça.
```bash

docker compose down -v
```

2. Subir os novos bancos limpos em segundo plano (Detached Mode):
```bash

docker compose up -d
```

3. Verificar se todos os serviços estão saudáveis e rodando:
```bash

docker compose ps
```

