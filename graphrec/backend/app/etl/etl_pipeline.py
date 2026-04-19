"""
app/etl/etl_pipeline.py
Pipeline nạp dữ liệu từ file CSV Kaggle vào ba hệ thống:
  - Neo4j (graph database)
  - MySQL (relational database)
  - Elasticsearch (search engine)

Ngoài dữ liệu sản phẩm thực, script sinh thêm người dùng và
hành vi (VIEWED/BOUGHT) giả lập để phục vụ demo truy vấn đề xuất.
"""
import os
import re
import csv
import random
import asyncio
import hashlib

import aiomysql
from neo4j import GraphDatabase
from elasticsearch import AsyncElasticsearch, helpers
from faker import Faker

# Import từ đúng package path
from app.db.elastic_client import PRODUCTS_INDEX, PRODUCTS_MAPPING

# ── Cấu hình kết nối ────────────────────────────────────────────────────────
NEO4J_URI  = os.getenv("NEO4J_URI",      "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER",     "neo4j")
NEO4J_PASS = os.getenv("NEO4J_PASSWORD", "graphrec123")

MYSQL_CFG = dict(
    host      = os.getenv("MYSQL_HOST",     "localhost"),
    port      = int(os.getenv("MYSQL_PORT", "3306")),
    user      = os.getenv("MYSQL_USER",     "root"),
    password  = os.getenv("MYSQL_PASSWORD", "graphrec123"),
    db        = os.getenv("MYSQL_DB",       "graphrec_db"),
    charset   = "utf8mb4",
    autocommit = True,
)

ES_HOST = os.getenv("ES_HOST", "http://localhost:9200")

faker  = Faker()
driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))

# Danh sách thương hiệu dùng để trích xuất từ tên sản phẩm
KNOWN_BRANDS = [
    "LG", "Samsung", "Daikin", "Voltas", "Blue Star", "Hitachi",
    "Lloyd", "Carrier", "Whirlpool", "Godrej", "Panasonic", "Haier",
    "O General", "Mitsubishi", "Fujitsu", "Toshiba", "Sharp", "Bosch",
]


# ── Hàm tiện ích ────────────────────────────────────────────────────────────

def parse_price(s: str) -> float:
    """Chuyển chuỗi giá dạng '₹32,999' sang float 32999.0"""
    if not s or s.strip() in ("", "Get"):
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", s.replace(",", ""))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def parse_rating(s: str) -> float:
    try:
        return float(str(s).strip())
    except ValueError:
        return 0.0


def parse_reviews(s: str) -> int:
    try:
        return int(re.sub(r"[^\d]", "", str(s)))
    except ValueError:
        return 0


def make_product_id(name: str, idx: int) -> str:
    """Tạo product_id duy nhất dựa trên hash tên + index."""
    h = hashlib.md5(name.encode()).hexdigest()[:6].upper()
    return f"P{idx:04d}{h}"


def extract_brand(name: str) -> str:
    """Trích xuất thương hiệu từ tên sản phẩm."""
    for b in KNOWN_BRANDS:
        if b.lower() in name.lower():
            return b
    return name.split()[0] if name else "Unknown"


# ── Đọc CSV ─────────────────────────────────────────────────────────────────

def parse_csv(filepath: str) -> list[dict]:
    """
    Đọc file CSV Kaggle Amazon (schema: name, main_category, sub_category,
    image, link, ratings, no_of_ratings, discount_price, actual_price).
    Trả về danh sách dict đã chuẩn hóa.
    """
    products = []
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            name = row.get("name", "").strip()
            if not name:
                continue
            products.append({
                "product_id":     make_product_id(name, i + 1),
                "title":          name,
                "sub_category":   row.get("sub_category",  "").strip(),
                "main_category":  row.get("main_category", "").strip(),
                "brand":          extract_brand(name),
                "price":          parse_price(row.get("discount_price", "")),
                "original_price": parse_price(row.get("actual_price",   "")),
                "rating":         parse_rating(row.get("ratings",       "0")),
                "review_count":   parse_reviews(row.get("no_of_ratings", "0")),
                "image_url":      row.get("image", "").strip(),
                "link":           row.get("link",  "").strip(),
            })
    return products


# ── Sinh dữ liệu giả lập ────────────────────────────────────────────────────

def generate_users(n: int = 200) -> list[dict]:
    return [
        {"user_id": f"U{i:04d}", "name": faker.name(), "email": faker.email()}
        for i in range(1, n + 1)
    ]


def generate_actions(products: list, users: list, n: int = 5000) -> list[dict]:
    """
    Sinh hành vi ngẫu nhiên.
    Tỷ lệ: 65% VIEWED, 35% BOUGHT – phản ánh hành vi thực tế e-commerce.
    """
    actions = []
    for _ in range(n):
        u   = random.choice(users)
        p   = random.choice(products)
        act = random.choices(["VIEWED", "BOUGHT"], weights=[0.65, 0.35])[0]
        actions.append({
            "user_id":    u["user_id"],
            "product_id": p["product_id"],
            "action":     act,
        })
    return actions


# ── Nạp vào Neo4j ────────────────────────────────────────────────────────────

def neo4j_load(products: list, users: list, actions: list) -> None:
    """
    Nạp dữ liệu vào Neo4j dùng Cypher MERGE để tránh trùng lặp.
    Mô hình graph:
      (User)-[:BOUGHT|VIEWED]->(Product)-[:BELONGS_TO]->(Category)
    """
    print("  [Neo4j] Loading ...")
    with driver.session() as s:
        # Đồng bộ tuyệt đối với MySQL strategy: thay toàn bộ dataset mỗi lần ETL.
        # Nếu không xóa node cũ, Neo4j sẽ giữ lại sản phẩm/user/category từ các lần import trước,
        # dẫn đến compare lệch dù query đã chuẩn hóa.
        s.run("MATCH (u:User) DETACH DELETE u")
        s.run("MATCH (p:Product) DETACH DELETE p")
        s.run("MATCH (c:Category) DETACH DELETE c")

        # Tạo constraint đảm bảo tính duy nhất
        for stmt in [
            "CREATE CONSTRAINT IF NOT EXISTS FOR (p:Product)  REQUIRE p.product_id IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (u:User)     REQUIRE u.user_id    IS UNIQUE",
            "CREATE CONSTRAINT IF NOT EXISTS FOR (c:Category) REQUIRE c.name       IS UNIQUE",
        ]:
            s.run(stmt)

        # Nạp Product + Category + quan hệ BELONGS_TO
        for p in products:
            s.run("""
                MERGE (cat:Category {name: $sub})
                  SET cat.main_category = $main
                MERGE (pr:Product {product_id: $pid})
                  SET pr.title = $title, pr.brand = $brand,
                      pr.price = $price, pr.original_price = $orig,
                      pr.rating = $rating, pr.review_count = $rc,
                      pr.image_url = $img, pr.link = $link,
                      pr.sub_category = $sub, pr.main_category = $main
                MERGE (pr)-[:BELONGS_TO]->(cat)
            """,
                pid=p["product_id"], title=p["title"], brand=p["brand"],
                price=p["price"], orig=p["original_price"],
                rating=p["rating"], rc=p["review_count"],
                img=p["image_url"], link=p["link"],
                sub=p["sub_category"] or "General",
                main=p["main_category"] or "General",
            )

        # Nạp User
        for u in users:
            s.run(
                "MERGE (u:User {user_id:$uid}) SET u.name=$name, u.email=$email",
                uid=u["user_id"], name=u["name"], email=u["email"],
            )

        # Nạp hành vi theo batch để tránh timeout
        BATCH = 500
        for i in range(0, len(actions), BATCH):
            batch = actions[i: i + BATCH]
            s.run("""
                UNWIND $rows AS row
                MATCH (u:User    {user_id:    row.user_id})
                MATCH (p:Product {product_id: row.product_id})
                FOREACH (_ IN CASE WHEN row.action='BOUGHT' THEN [1] ELSE [] END |
                    MERGE (u)-[:BOUGHT]->(p))
                FOREACH (_ IN CASE WHEN row.action='VIEWED' THEN [1] ELSE [] END |
                    MERGE (u)-[:VIEWED]->(p))
            """, rows=batch)

    print(f"  [Neo4j] Done: {len(products)} products, {len(users)} users, {len(actions)} actions")


# ── Nạp vào MySQL ────────────────────────────────────────────────────────────

async def mysql_load(products: list, users: list, actions: list) -> None:
    """
    Nạp dữ liệu vào MySQL. Xóa sạch trước để tránh conflict FK.
    Dùng executemany cho actions để tối ưu tốc độ insert hàng loạt.
    """
    print("  [MySQL] Loading ...")
    pool = await aiomysql.create_pool(**MYSQL_CFG)
    async with pool.acquire() as conn:
        async with conn.cursor() as cur:
            # Reload nhanh và sạch: dùng TRUNCATE thay vì DELETE toàn bảng.
            await cur.execute("SET FOREIGN_KEY_CHECKS = 0")
            await cur.execute("TRUNCATE TABLE actions")
            await cur.execute("TRUNCATE TABLE products")
            await cur.execute("TRUNCATE TABLE users")
            await cur.execute("SET FOREIGN_KEY_CHECKS = 1")

            for p in products:
                await cur.execute("""
                    INSERT IGNORE INTO products
                      (product_id, title, sub_category, main_category, brand,
                       price, original_price, rating, review_count, image_url, link)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    p["product_id"], p["title"][:500],
                    p["sub_category"], p["main_category"], p["brand"],
                    p["price"], p["original_price"],
                    p["rating"], p["review_count"],
                    (p["image_url"] or "")[:500],
                    (p["link"]     or "")[:500],
                ))

            for u in users:
                await cur.execute(
                    "INSERT IGNORE INTO users (user_id, name, email) VALUES (%s,%s,%s)",
                    (u["user_id"], u["name"], u["email"]),
                )

            rows = [(a["user_id"], a["product_id"], a["action"]) for a in actions]
            await cur.executemany(
                "INSERT INTO actions (user_id, product_id, action) VALUES (%s,%s,%s)",
                rows,
            )

    pool.close()
    await pool.wait_closed()
    print(f"  [MySQL] Done: {len(products)} products, {len(users)} users, {len(actions)} actions")


# ── Nạp vào Elasticsearch ────────────────────────────────────────────────────

async def es_load(products: list) -> None:
    """
    Tạo lại ES index (xóa nếu tồn tại) rồi nạp toàn bộ sản phẩm.
    helpers.async_bulk giúp gửi dữ liệu theo batch, hiệu quả hơn insert từng document.
    """
    print("  [ES] Loading ...")
    es = AsyncElasticsearch(ES_HOST)

    if await es.indices.exists(index=PRODUCTS_INDEX):
        await es.indices.delete(index=PRODUCTS_INDEX)
    await es.indices.create(index=PRODUCTS_INDEX, body=PRODUCTS_MAPPING)

    docs = [
        {"_index": PRODUCTS_INDEX, "_id": p["product_id"], "_source": p}
        for p in products
    ]
    await helpers.async_bulk(es, docs)
    await es.indices.refresh(index=PRODUCTS_INDEX)
    await es.close()
    print(f"  [ES] Done: {len(products)} documents indexed")


# ── Entry point ──────────────────────────────────────────────────────────────

async def run_etl(
    csv_paths: list[str],
    n_users:   int = 200,
    n_actions: int = 5000,
) -> dict:
    """
    Hàm chính của ETL pipeline.
    Nhận một hoặc nhiều file CSV (cùng schema Kaggle Amazon),
    hợp nhất, sinh dữ liệu giả, rồi nạp vào cả ba hệ thống.
    """
    all_products: list[dict] = []
    for path in csv_paths:
        print(f"  Parsing {path} ...")
        all_products.extend(parse_csv(path))

    # Loại bỏ trùng lặp theo product_id (khi merge nhiều CSV)
    deduped = {p["product_id"]: p for p in all_products}
    all_products = list(deduped.values())
    print(f"  Total unique products: {len(all_products)}")

    users   = generate_users(n_users)
    actions = generate_actions(all_products, users, n_actions)
    print(f"  Generated {len(users)} users, {len(actions)} actions")

    neo4j_load(all_products, users, actions)
    await mysql_load(all_products, users, actions)
    await es_load(all_products)

    driver.close()
    print("ETL complete.")
    return {
        "products": len(all_products),
        "users":    len(users),
        "actions":  len(actions),
    }


if __name__ == "__main__":
    import sys
    paths = sys.argv[1:] if len(sys.argv) > 1 else ["data/Air_Conditioners.csv"]
    asyncio.run(run_etl(paths))
