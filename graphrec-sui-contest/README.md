# GraphRec SUI Contest Project

This folder is the contest submission version of GraphRec. It keeps the SUI wallet, reward, Product NFT, and on-chain recommendation flows together with the search/recommendation stack.

## What is included

- FastAPI backend for search, recommendation, compare, benchmark, ETL, and SUI APIs.
- React frontend with the SUI wallet and reward panel.
- Neo4j, MySQL, Elasticsearch, and SUI integration.
- Move smart contract and deployment scripts.

## Run with Docker

```bash
copy .env.example .env
docker compose up --build
```

Main URLs:

- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs
- Frontend: http://localhost:5173
- Neo4j Browser: http://localhost:7474
- Elasticsearch: http://localhost:9200

## Run locally

Backend:

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

## SUI checks

```bash
curl http://localhost:8000/sui/status
curl "http://localhost:8000/sui/quick-actions?address=0x..."
```
