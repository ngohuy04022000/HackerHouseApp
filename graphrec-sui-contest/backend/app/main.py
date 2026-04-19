import os
from contextlib import asynccontextmanager

import aiomysql
from fastapi import FastAPI, Query
from fastapi import HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.db.neo4j_client   import neo4j_driver
from app.db.mysql_client    import mysql_pool
from app.db.elastic_client  import es_client, PRODUCTS_INDEX

from app.routers import search, recommend, etl
from app.routers import sui


REVIEW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS product_reviews (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    product_id  VARCHAR(20)  NOT NULL,
    user_id     VARCHAR(20)  DEFAULT NULL,
    user_name   VARCHAR(200) NOT NULL,
    wallet_address VARCHAR(200) DEFAULT NULL,
    rating      TINYINT      NOT NULL,
    comment     TEXT         DEFAULT NULL,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_pr_product_created (product_id, created_at),
    INDEX idx_pr_rating (rating),
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
)
"""


class ProductReviewCreate(BaseModel):
    user_id: str = ""
    user_name: str = "Guest"
    wallet_address: str = ""
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""


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
    description="Nen tang thuong mai dien tu ket hop de xuat san pham va phan thuong blockchain SUI",
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
            "wallet":    "GET  /sui/wallet/{address}",
            "reward":    "POST /sui/reward",
            "mint_nft":  "POST /sui/mint-nft",
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
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            row = await cur.fetchone()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)


@app.get("/products/{product_id}/detail", tags=["Products"])
async def get_product_detail(product_id: str):
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(REVIEW_TABLE_SQL)

            await cur.execute("SELECT * FROM products WHERE product_id = %s", (product_id,))
            product = await cur.fetchone()
            if not product:
                raise HTTPException(404, "Product not found")

            await cur.execute(
                """
                SELECT id, product_id, user_id, user_name, wallet_address, rating, comment, created_at
                FROM product_reviews
                WHERE product_id = %s
                ORDER BY created_at DESC
                LIMIT 20
                """,
                (product_id,),
            )
            reviews = await cur.fetchall()

            await cur.execute(
                """
                SELECT AVG(rating) AS avg_rating, COUNT(*) AS total_reviews
                FROM product_reviews
                WHERE product_id = %s
                """,
                (product_id,),
            )
            summary = await cur.fetchone()

            await cur.execute(
                """
                SELECT product_id, title, brand, sub_category, price, original_price, rating, review_count, image_url
                FROM products
                WHERE sub_category = %s AND product_id != %s
                ORDER BY rating DESC, review_count DESC
                LIMIT 8
                """,
                (product.get("sub_category", ""), product_id),
            )
            related = await cur.fetchall()

    return {
        "product": dict(product),
        "reviews": list(reviews),
        "review_summary": {
            "avg_rating": round(float(summary.get("avg_rating") or 0), 2),
            "total_reviews": int(summary.get("total_reviews") or 0),
        },
        "related_products": list(related),
    }


@app.post("/products/{product_id}/reviews", tags=["Products"])
async def add_product_review(product_id: str, payload: ProductReviewCreate):
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(REVIEW_TABLE_SQL)
            await cur.execute("SELECT product_id FROM products WHERE product_id = %s", (product_id,))
            exists = await cur.fetchone()
            if not exists:
                raise HTTPException(404, "Product not found")

            user_name = (payload.user_name or "Guest").strip()[:200] or "Guest"
            comment = (payload.comment or "").strip()[:2000]
            wallet_address = (payload.wallet_address or "").strip()[:200]
            user_id = (payload.user_id or "").strip()[:20]

            # Anti-spam: chan review lien tiep trong thoi gian ngan cho cung actor + san pham.
            actor_where = ""
            actor_params: list[str] = []
            if user_id:
                actor_where = "user_id = %s"
                actor_params.append(user_id)
            elif wallet_address:
                actor_where = "wallet_address = %s"
                actor_params.append(wallet_address)
            else:
                actor_where = "user_name = %s"
                actor_params.append(user_name)

            await cur.execute(
                f"""
                SELECT id, rating, comment,
                       TIMESTAMPDIFF(SECOND, created_at, NOW()) AS diff_sec
                FROM product_reviews
                WHERE product_id = %s AND ({actor_where})
                ORDER BY created_at DESC
                LIMIT 1
                """,
                [product_id, *actor_params],
            )
            last_review = await cur.fetchone()

            if last_review and int(last_review.get("diff_sec") or 0) < 90:
                raise HTTPException(
                    429,
                    "Bạn vừa đánh giá sản phẩm này. Vui lòng chờ một lúc rồi thử lại.",
                )

            if (
                last_review
                and int(last_review.get("diff_sec") or 0) < 600
                and int(last_review.get("rating") or 0) == int(payload.rating)
                and (last_review.get("comment") or "").strip() == comment
            ):
                raise HTTPException(
                    429,
                    "Đánh giá trùng lặp trong thời gian ngắn đã bị chặn để tránh spam.",
                )

            await cur.execute(
                """
                INSERT INTO product_reviews (product_id, user_id, user_name, wallet_address, rating, comment)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (product_id, user_id or None, user_name, wallet_address or None, payload.rating, comment),
            )
            review_id = cur.lastrowid

            await conn.commit()

            await cur.execute(
                """
                SELECT AVG(rating) AS avg_rating, COUNT(*) AS total_reviews
                FROM product_reviews
                WHERE product_id = %s
                """,
                (product_id,),
            )
            summary = await cur.fetchone()

    return {
        "success": True,
        "review_id": review_id,
        "product_id": product_id,
        "rating": payload.rating,
        "review_summary": {
            "avg_rating": round(float(summary.get("avg_rating") or 0), 2),
            "total_reviews": int(summary.get("total_reviews") or 0),
        },
        "message": "Danh gia da duoc ghi nhan",
    }


@app.get("/users/{user_id}/reviews", tags=["Users"])
async def user_review_history(user_id: str, size: int = Query(20, ge=1, le=100)):
    pool = await mysql_pool()
    async with pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cur:
            await cur.execute(REVIEW_TABLE_SQL)
            await cur.execute(
                """
                SELECT
                    pr.id,
                    pr.product_id,
                    p.title,
                    p.brand,
                    p.image_url,
                    pr.rating,
                    pr.comment,
                    pr.created_at
                FROM product_reviews pr
                JOIN products p ON p.product_id = pr.product_id
                WHERE pr.user_id = %s
                ORDER BY pr.created_at DESC
                LIMIT %s
                """,
                (user_id, size),
            )
            rows = await cur.fetchall()

    return {"user_id": user_id, "total": len(rows), "items": list(rows)}


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
