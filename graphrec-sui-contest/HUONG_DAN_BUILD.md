# GraphRec — Huong dan cai dat va chay du an

## Cau truc thu muc

```
graphrec/
├── docker-compose.yml
├── data/
│   └── Air_Conditioners.csv        # Dataset mac dinh
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── sql/
│   │   └── init.sql                # Schema MySQL (tu dong chay khi container khoi dong)
│   └── app/
│       ├── __init__.py
│       ├── main.py                 # FastAPI entry point
│       ├── db/
│       │   ├── neo4j_client.py
│       │   ├── mysql_client.py
│       │   └── elastic_client.py
│       ├── routers/
│       │   ├── search.py           # GET /search
│       │   ├── recommend.py        # GET /recommend/{user_id}
│       │   ├── compare.py          # POST /compare/query
│       │   ├── benchmark.py        # GET /benchmark/run
│       │   └── etl.py              # POST /etl/upload
│       └── etl/
│           └── etl_pipeline.py     # Pipeline nap du lieu
└── frontend/
    ├── Dockerfile
    ├── nginx.conf
    ├── package.json
    ├── vite.config.js
    ├── index.html
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── api.js
        ├── index.css
        └── components/
            ├── Sidebar.jsx
            ├── SearchBar.jsx
            ├── ProductGrid.jsx
            ├── RecommendPanel.jsx
            ├── QueryComparison.jsx
            └── BenchmarkChart.jsx
```

---

## Yeu cau he thong

- Docker Desktop >= 24 (hoac Docker Engine + Compose v2)
- (Tuy chon) Python 3.11 + Node 20 neu muon chay local khong dung Docker

---

## Cach 1: Chay bang Docker (khuyen nghi)

### Buoc 1 — Khoi dong tat ca dich vu

```bash
cd graphrec

# Build va khoi dong 5 container: Neo4j, MySQL, Elasticsearch, Backend, Frontend
docker compose up --build
```

Lan dau build mat ~3-5 phut (tai image va cai package).
Kiem tra trang thai:

```bash
docker compose ps
# Tat ca container phai o trang thai "healthy" hoac "running"
```

### Buoc 2 — Nap du lieu (ETL)

Sau khi container healthy, nap dataset vao ca 3 he thong:

```bash
# Cach A: Chay ETL script truc tiep trong container backend
docker exec -it graphrec_backend python -m app.etl.etl_pipeline data/Air_Conditioners.csv

# Cach B: Goi API endpoint (tu may host)
curl -X POST "http://localhost:8000/etl/run-existing" \
  -H "Content-Type: application/json" \
  -d '{"filenames": ["Air_Conditioners.csv"], "n_users": 200, "n_actions": 5000}'

# Theo doi trang thai ETL
curl http://localhost:8000/etl/status
```

### Buoc 3 — Mo trinh duyet

| Dich vu          | URL                        |
|------------------|---------------------------|
| Web App (React)  | http://localhost:5173      |
| Backend API Docs | http://localhost:8000/docs |
| Neo4j Browser    | http://localhost:7474      |
| Elasticsearch    | http://localhost:9200      |

Dang nhap Neo4j Browser: username `neo4j`, password `graphrec123`

---

## Cach 2: Chay local (khong Docker)

### Yeu cau them
- Neo4j 5.x dang chay (bolt://localhost:7687, user neo4j/graphrec123)
- MySQL 8.x dang chay (root/graphrec123, database graphrec_db)
- Elasticsearch 8.x dang chay (localhost:9200, security disabled)

### Backend

```bash
cd graphrec/backend

# Tao moi truong ao
python -m venv .venv
source .venv/bin/activate    # Linux/Mac
# .venv\Scripts\activate     # Windows

# Cai thu vien
pip install -r requirements.txt

# Khoi tao schema MySQL (chi can chay lan dau)
mysql -u root -pgraphrec123 < sql/init.sql

# Nap du lieu
python -m app.etl.etl_pipeline ../data/Air_Conditioners.csv

# Chay server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd graphrec/frontend

npm install

# Chay dev server (proxy /api -> localhost:8000 tu dong)
npm run dev
```

Mo http://localhost:5173

---

## Upload them dataset Kaggle

Du an ho tro moi file CSV co cung schema Amazon Kaggle:
`name, main_category, sub_category, image, link, ratings, no_of_ratings, discount_price, actual_price`

### Cach A: Qua giao dien web
1. Dat file CSV vao thu muc `graphrec/data/`
2. Goi API:

```bash
curl -X POST "http://localhost:8000/etl/run-existing" \
  -H "Content-Type: application/json" \
  -d '{"filenames": ["Air_Conditioners.csv", "Televisions.csv"], "n_users": 300, "n_actions": 8000}'
```

```bash
curl -X POST "http://localhost:8000/etl/run-existing" \
  -H "Content-Type: application/json" \
  -d '{"filenames": ["Air Conditioners.csv", "All Appliances.csv", "All Car and Motorbike Products.csv", "All Electronics.csv", "All Electronics.csv", "All Exercise and Fitness.csv"], "n_users": 1000, "n_actions": 50000}'
```

### Cach B: Upload file moi qua API
```bash
curl -X POST "http://localhost:8000/etl/upload" \
  -F "files=@/duong/dan/toi/file.csv" \
  -F "n_users=200" \
  -F "n_actions=5000"
```

### Cach C: Script Python truc tiep
```bash
docker exec -it graphrec_backend python -m app.etl.etl_pipeline \
  data/Air_Conditioners.csv data/Televisions.csv
```

---

## Kiem tra he thong

```bash
# Health check
curl http://localhost:8000/health

# Tim kiem san pham
curl "http://localhost:8000/search?q=LG+Inverter"

# Goi y collaborative
curl "http://localhost:8000/recommend/U0001"

# Goi y theo category
curl "http://localhost:8000/recommend/category/U0001"

# So sanh Neo4j vs MySQL (collaborative query)
curl -X POST "http://localhost:8000/compare/query" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "U0001", "query_type": "collaborative"}'

# Benchmark 10 lan
curl "http://localhost:8000/benchmark/run?user_id=U0001&iterations=10"
```

---

## Truy van Cypher minh hoa trong Neo4j Browser

Mo http://localhost:7474 va chay cac lenh sau de kiem tra du lieu:

```cypher
-- Dem node
MATCH (p:Product)  RETURN count(p) AS san_pham;
MATCH (u:User)     RETURN count(u) AS nguoi_dung;
MATCH (c:Category) RETURN count(c) AS danh_muc;
MATCH ()-->()      RETURN count(*) AS tong_canh;

-- Xem do thi quan he
MATCH path = (u:User {user_id:'U0001'})-[:BOUGHT|VIEWED]->(:Product)
             -[:BELONGS_TO]->(c:Category)
RETURN path LIMIT 20;

-- Truy van goi y 2-hop (Collaborative Filtering)
MATCH (u:User {user_id:'U0001'})-[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(other:User)-[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
RETURN rec.product_id, rec.title, count(*) AS score
ORDER BY score DESC LIMIT 10;

-- PROFILE: phan tich hieu nang graph traversal
PROFILE
MATCH (u:User {user_id:'U0001'})-[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(other:User)-[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
RETURN rec.product_id, rec.title, count(*) AS score
ORDER BY score DESC LIMIT 10;
```

---

## Truy van MySQL minh hoa (SQL tuong duong)

```sql
-- Ket noi MySQL
docker exec -it graphrec_mysql mysql -u root -pgraphrec123 graphrec_db

-- Xem du lieu
SELECT COUNT(*) FROM products;
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM actions;

-- EXPLAIN ANALYZE: phan tich ke hoach thuc thi SQL
EXPLAIN ANALYZE
SELECT p2.product_id, p2.title, COUNT(*) AS score
FROM   actions a1
JOIN   actions a2 ON a1.product_id = a2.product_id AND a1.user_id <> a2.user_id
JOIN   actions a3 ON a2.user_id = a3.user_id AND a3.action = 'BOUGHT'
JOIN   products p2 ON p2.product_id = a3.product_id
WHERE  a1.user_id = 'U0001'
  AND  NOT EXISTS (
         SELECT 1 FROM actions a4
         WHERE  a4.user_id = 'U0001'
           AND  a4.product_id = p2.product_id
           AND  a4.action = 'BOUGHT'
       )
GROUP  BY p2.product_id, p2.title
ORDER  BY score DESC
LIMIT  10;
```

---

## Xoa va reset du lieu

```bash
# Xoa tat ca du lieu, giu cau truc container
docker compose down -v

# Khoi dong lai tu dau
docker compose up --build
# Chay lai ETL sau khi container healthy
```

---

## Cau hinh bien moi truong

File `.env` (dat canh docker-compose.yml):

```env
NEO4J_AUTH=neo4j/graphrec123
MYSQL_ROOT_PASSWORD=graphrec123
MYSQL_DATABASE=graphrec_db
VITE_API_URL=http://localhost:8000
```

---

## Xem log

```bash
docker compose logs -f backend       # Log FastAPI
docker compose logs -f neo4j         # Log Neo4j
docker compose logs -f mysql         # Log MySQL
docker compose logs -f elasticsearch # Log ES
