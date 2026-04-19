import os
from contextlib import asynccontextmanager

import aiomysql
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware

from app.db.neo4j_client   import neo4j_driver
from app.db.mysql_client    import mysql_pool
from app.db.elastic_client  import es_client, PRODUCTS_INDEX

from app.routers import search, recommend, compare, benchmark, etl
from app.routers import sui


# ── Lifespan: khoi dong va tat server ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("GraphRec API starting ...")

    # Kiem tra ket noi MySQL
    try:
        pool = await mysql_pool()
        print("  MySQL pool ready")
    except Exception as e:
        print(f"  MySQL unavailable: {e}")

    # Kiem tra ket noi Neo4j
    try:
        neo4j_driver.verify_connectivity()
        print("  Neo4j connected")
    except Exception as e:
        print(f"  Neo4j unavailable: {e}")

    # Kiem tra ket noi Elasticsearch
    try:
        if await es_client.ping():
            print("  Elasticsearch connected")
        else:
            print("  Elasticsearch not available (MySQL fulltext fallback active)")
    except Exception:
        print("  Elasticsearch not available (MySQL fulltext fallback active)")

    yield

    print("GraphRec API shutting down ...")
    neo4j_driver.close()


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="GraphRec API",
    description="So sanh Neo4j (Graph DB) vs MySQL (Relational DB) cho he thong de xuat san pham",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Mount routers ─────────────────────────────────────────────────────────────

app.include_router(search.router,    prefix="/search",    tags=["Search"])
app.include_router(recommend.router, prefix="/recommend", tags=["Recommend"])
app.include_router(compare.router,   prefix="/compare",   tags=["Compare"])
app.include_router(benchmark.router, prefix="/benchmark", tags=["Benchmark"])
app.include_router(etl.router,       prefix="/etl",       tags=["ETL"])
app.include_router(sui.router,       prefix="/sui", tags=["Sui Blockchain"])


# ── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Info"])
async def root():
    return {
        "api":  "GraphRec v2.0",
        "docs": "/docs",
        "endpoints": {
            "search":    "GET  /search?q=LG&engine=auto",
            "recommend": "GET  /recommend/{user_id}",
            "category":  "GET  /recommend/category/{user_id}",
            "compare":   "POST /compare/query",
            "benchmark": "GET  /benchmark/run?iterations=10",
            "etl":       "POST /etl/upload",
        },
    }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Info"])
async def health():
    """Kiem tra trang thai ket noi ca ba he thong."""
    result: dict = {}

    # Neo4j
    try:
        neo4j_driver.verify_connectivity()
        with neo4j_driver.session() as s:
            row = s.run("MATCH (p:Product) RETURN count(p) AS cnt").single()
        result.update(neo4j=True, neo4j_products=row["cnt"] if row else 0)
    except Exception as e:
        result.update(neo4j=False, neo4j_error=str(e))

    # MySQL
    try:
        pool = await mysql_pool()
        async with pool.acquire() as conn:
            async with conn.cursor() as cur:
                await cur.execute("SELECT COUNT(*) FROM products")
                (cnt,) = await cur.fetchone()
        result.update(mysql=True, mysql_products=cnt)
    except Exception as e:
        result.update(mysql=False, mysql_error=str(e))

    # Elasticsearch
    try:
        if await es_client.ping():
            r = await es_client.count(index=PRODUCTS_INDEX)
            result.update(elastic=True, elastic_products=r.get("count", 0))
        else:
            result.update(elastic=False)
    except Exception:
        result.update(elastic=False)
    
    # Sui
    try:
        from app.sui.client import get_sui_client
        sui_client = get_sui_client()
        result["sui"] = sui_client.is_configured()
    except Exception:
        result["sui"] = False

    return result


# ── Products ──────────────────────────────────────────────────────────────────

@app.get("/products", tags=["Products"])
async def list_products(
    category:  str   = Query(""),
    brand:     str   = Query(""),
    min_rating: float = Query(0),
    max_price:  float = Query(9_999_999),
    page: int  = Query(1, ge=1),
    size: int  = Query(24, ge=1, le=100),
):
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            sql    = "SELECT * FROM products WHERE rating >= %s AND (price = 0 OR price <= %s)"
            params = [min_rating, max_price]

            if category:
                sql += " AND sub_category = %s"; params.append(category)
            if brand:
                sql += " AND brand = %s";        params.append(brand)

            # Dem tong so ket qua (paging)
            count_sql = sql.replace("SELECT *", "SELECT COUNT(*) AS cnt")
            await cur.execute(count_sql, params)
            total = (await cur.fetchone())["cnt"]

            sql += " ORDER BY rating DESC LIMIT %s OFFSET %s"
            params += [size, (page - 1) * size]
            await cur.execute(sql, params)
            items = await cur.fetchall()

    return {"total": total, "page": page, "size": size, "items": list(items)}


@app.get("/products/{product_id}", tags=["Products"])
async def get_product(product_id: str):
    from fastapi import HTTPException
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)


# ── Categories ────────────────────────────────────────────────────────────────

@app.get("/categories", tags=["Products"])
async def list_categories():
    """Danh sach danh muc kem so luong san pham, sap xep giam dan."""
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("""
                SELECT sub_category AS category, COUNT(*) AS count
                FROM   products
                WHERE  sub_category IS NOT NULL AND sub_category != ''
                GROUP  BY sub_category
                ORDER  BY count DESC, sub_category
            """)
            rows = await cur.fetchall()
    return list(rows)


# ── Users ─────────────────────────────────────────────────────────────────────

@app.get("/users", tags=["Users"])
async def list_users(limit: int = Query(50, ge=1, le=200)):
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(
                "SELECT user_id, name AS user_name FROM users LIMIT %s", (limit,)
            )
            rows = await cur.fetchall()
    return list(rows)
