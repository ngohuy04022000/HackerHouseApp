# GraphRec Commerce + SUI Rewards

Tai lieu nay mo ta ban da tai cau truc theo mo hinh web ban hang thong thuong ket hop blockchain.

## Muc tieu san pham

- Tim kiem va duyet san pham nhu ecommerce.
- Hien thi de xuat san pham ca nhan hoa.
- Thuong token GREC khi user xem, mua, danh gia.
- Mint Product NFT khi mua hang.

## Chay bang Docker

```bash
copy .env.example .env
docker compose up --build
```

## URL sau khi chay

- Frontend: http://localhost:5173
- Backend docs: http://localhost:8000/docs
- Neo4j Browser: http://localhost:7474
- Elasticsearch: http://localhost:9200

## Endpoint quan trong

```bash
# Kiem tra he thong
curl http://localhost:8000/health

# Cua hang va de xuat
curl "http://localhost:8000/search?q=LG"
curl "http://localhost:8000/recommend/U0001"
curl "http://localhost:8000/recommend/category/U0001"

# Blockchain
curl http://localhost:8000/sui/status
curl "http://localhost:8000/sui/wallet/0x..."
```

## Luong thuong blockchain

1. User chon san pham trong cua hang.
2. User bam hanh dong VIEWED / BOUGHT / REVIEWED.
3. Backend goi `/sui/reward` de cap GREC.
4. Neu BOUGHT, backend goi `/sui/mint-nft` de mint Product NFT.
5. Frontend cap nhat so du GREC va so NFT trong vi.
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
