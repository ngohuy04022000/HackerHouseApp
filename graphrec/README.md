# GraphRec

GraphRec is a product recommendation platform that combines graph-based recommendation with blockchain proofs on SUI.

## Main components

- Backend: FastAPI service for search, recommendation, benchmark, and SUI APIs.
- Frontend: React application for search and recommendation workflows.
- Data services: Neo4j, MySQL, Elasticsearch.
- Smart contract: Move contract on SUI testnet.

## Project structure

- backend: FastAPI application and APIs.
- frontend: React web app.
- contracts: Move package and smart contract sources.
- data: CSV datasets.
- docs: project documents.
- scripts: helper scripts.

## Requirements

- Docker Desktop with Docker Compose.
- For local run (optional):
  - Python 3.11 or 3.12
  - Node.js 18+
  - npm

## Quick start with Docker

Run from the graphrec directory:

```bash
docker compose down
docker compose up --build -d
```

Check running services:

```bash
docker compose ps
```

Main URLs:

- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Neo4j Browser: http://localhost:7474
- Elasticsearch: http://localhost:9200

Stop services:

```bash
docker compose down
```

## Local run (without Docker)

### 1) Backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux/macOS:
# source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 2) Frontend

```bash
cd frontend
npm install
npm run dev
```

## Run tests

Backend tests:

```bash
cd backend
pytest -q
```

Inside Docker:

```bash
docker compose exec backend pytest -q
```

## SUI integration checks

Basic status:

```bash
curl http://localhost:8000/sui/status
```

Fund pool:

```bash
curl -X POST http://localhost:8000/sui/fund-pool \
  -H "Content-Type: application/json" \
  -d '{"amount_grec": 100000}'
```

More SUI setup and endpoint examples are in SUI_INTEGRATION_GUIDE.md.

## Environment and security

- Do not commit private keys or local .env files.
- Use secrets manager in production.
- Restrict access to backend admin wallet operations.
