import time
import aiomysql
from fastapi import APIRouter, Query
from elasticsearch import NotFoundError

from app.db.elastic_client import es_client, PRODUCTS_INDEX
from app.db.mysql_client    import mysql_pool

router = APIRouter()


# ── Elasticsearch ────────────────────────────────────────────────────────────

async def _es_search(q: str, category: str = "", size: int = 24) -> dict:
    t0 = time.perf_counter()

    must    = [{"multi_match": {
        "query":     q,
        "fields":    ["title^3", "brand^2", "sub_category"],
        "type":      "best_fields",
        "fuzziness": "AUTO",   # tự động chọn khoảng cách edit distance
    }}]
    filters = [{"term": {"sub_category": category}}] if category else []

    body = {
        "query":     {"bool": {"must": must, "filter": filters}},
        "highlight": {"fields": {"title": {"number_of_fragments": 1}}},
        "size":      size,
    }
    resp = await es_client.search(index=PRODUCTS_INDEX, body=body)
    took = (time.perf_counter() - t0) * 1000

    items = []
    for hit in resp["hits"]["hits"]:
        src = hit["_source"].copy()
        src["_score"] = hit["_score"]
        if "highlight" in hit:
            src["_highlight"] = hit["highlight"].get("title", [src["title"]])
        items.append(src)

    return {
        "engine":  "elasticsearch",
        "query":   q,
        "total":   resp["hits"]["total"]["value"],
        "took_ms": round(took, 2),
        "items":   items,
    }


# ── MySQL FULLTEXT fallback ──────────────────────────────────────────────────

async def _mysql_search(q: str, category: str = "", size: int = 24) -> dict:
    """
    Tìm kiếm MySQL dùng FULLTEXT index kết hợp LIKE để tăng recall.
    Không có fuzzy matching – nhược điểm so với ES.
    """
    t0   = time.perf_counter()
    pool = await mysql_pool()

    async with pool.acquire() as conn:
        # Dùng DictCursor để fetchall() trả về list[dict] thay vì list[tuple]
        async with conn.cursor(aiomysql.DictCursor) as cur:
            if category:
                await cur.execute("""
                    SELECT * FROM products
                    WHERE (MATCH(title) AGAINST(%s IN BOOLEAN MODE) OR title LIKE %s)
                      AND sub_category = %s
                    ORDER BY rating DESC
                    LIMIT %s
                """, (q, f"%{q}%", category, size))
            else:
                await cur.execute("""
                    SELECT * FROM products
                    WHERE MATCH(title) AGAINST(%s IN BOOLEAN MODE)
                       OR title LIKE %s
                    ORDER BY rating DESC
                    LIMIT %s
                """, (q, f"%{q}%", size))
            rows = await cur.fetchall()

    took  = (time.perf_counter() - t0) * 1000
    items = [dict(r) for r in rows]
    return {
        "engine":  "mysql_fulltext",
        "query":   q,
        "total":   len(items),
        "took_ms": round(took, 2),
        "items":   items,
    }


# ── Routes ───────────────────────────────────────────────────────────────────

@router.get("")
async def search(
    q:        str = Query(..., min_length=1),
    category: str = Query(""),
    size:     int = Query(24, ge=1, le=100),
    engine:   str = Query("auto"),  # auto | elasticsearch | mysql
):
    """
    Tìm kiếm sản phẩm.
    - auto: ES truoc, fallback MySQL nếu ES lỗi hoặc rỗng
    - elasticsearch: ep buoc dung ES
    - mysql: ep buoc dung MySQL FULLTEXT
    """
    if engine == "mysql":
        return await _mysql_search(q, category, size)

    if engine == "elasticsearch":
        return await _es_search(q, category, size)

    # auto: thử ES, fallback MySQL
    try:
        result = await _es_search(q, category, size)
        if result["total"] > 0:
            return result
        return await _mysql_search(q, category, size)
    except (NotFoundError, Exception):
        return await _mysql_search(q, category, size)

