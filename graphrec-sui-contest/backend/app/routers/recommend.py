from fastapi import APIRouter
from app.db.neo4j_client import neo4j_driver

router = APIRouter()


# ── Cypher queries ────────────────────────────────────────────────────────────

# 2-hop Collaborative Filtering
# Luong traversal: (u)-[BOUGHT|VIEWED]->(p)<-[BOUGHT|VIEWED]-(other)-[BOUGHT]->(rec)
COLLAB_QUERY = """
MATCH (u:User {user_id: $uid})-[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(other:User)-[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
RETURN rec.product_id  AS product_id,
       rec.title        AS title,
       rec.brand        AS brand,
       rec.sub_category AS category,
       rec.price        AS price,
       rec.original_price AS original_price,
       rec.rating       AS rating,
       rec.review_count AS review_count,
       rec.image_url    AS image_url,
       count(*)         AS score
ORDER BY score DESC
LIMIT 12
"""

# 3-hop Category-based
# Luong: (u)-[BOUGHT]->(p)-[BELONGS_TO]->(c)<-[BELONGS_TO]-(rec)
CATEGORY_QUERY = """
MATCH (u:User {user_id: $uid})-[:BOUGHT]->(:Product)-[:BELONGS_TO]->(c:Category)
WITH u, c, count(*) AS freq ORDER BY freq DESC LIMIT 3
MATCH (c)<-[:BELONGS_TO]-(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
RETURN c.name          AS category,
       rec.product_id  AS product_id,
       rec.title        AS title,
       rec.brand        AS brand,
       rec.price        AS price,
       rec.original_price AS original_price,
       rec.rating       AS rating,
       rec.review_count AS review_count,
       rec.image_url    AS image_url,
       count(*)         AS score
ORDER BY score DESC
LIMIT 12
"""

# Fallback khi user chua co lich su mua hang
TOP_RATED_QUERY = """
MATCH (p:Product)
RETURN p.product_id   AS product_id,
       p.title         AS title,
       p.brand         AS brand,
       p.sub_category  AS category,
       p.price         AS price,
       p.original_price AS original_price,
       p.rating        AS rating,
       p.review_count  AS review_count,
       p.image_url     AS image_url,
       (p.rating * p.review_count) AS score
ORDER BY score DESC
LIMIT 12
"""

# Tim nguoi dung co nhieu san pham chung nhat (dung de hien thi trong UI)
SIMILAR_USERS_QUERY = """
MATCH (u:User {user_id: $uid})-[:BOUGHT|VIEWED]->(p:Product)
      <-[:BOUGHT|VIEWED]-(other:User)
WHERE other.user_id <> $uid
WITH other, count(DISTINCT p) AS common
ORDER BY common DESC
LIMIT 5
RETURN other.user_id AS user_id,
       other.name    AS name,
       common        AS common_products
"""


def _to_list(result) -> list[dict]:
    return [dict(r) for r in result]


# ── Routes – thứ tự quan trọng ──────────────────────────────────────────────

@router.get("/category/{user_id}")
async def recommend_by_category(user_id: str):
    """Goi y 3-hop: User -> Product -> Category <- Product."""
    with neo4j_driver.session() as s:
        items  = _to_list(s.run(CATEGORY_QUERY, uid=user_id))
        method = "category"
        if not items:
            items  = _to_list(s.run(TOP_RATED_QUERY))
            method = "fallback_top_rated"
    return {"user_id": user_id, "method": method, "items": items, "query": CATEGORY_QUERY}


@router.get("/similar-users/{user_id}")
async def similar_users(user_id: str):
    """Tim nguoi dung co so thich tuong tu (nhieu san pham chung nhat)."""
    with neo4j_driver.session() as s:
        users = _to_list(s.run(SIMILAR_USERS_QUERY, uid=user_id))
    return {"user_id": user_id, "similar_users": users}


@router.get("/history/{user_id}")
async def user_history(user_id: str):
    """Lay lich su VIEWED/BOUGHT cua user."""
    query = """
    MATCH (u:User {user_id: $uid})-[r:BOUGHT|VIEWED]->(p:Product)
    RETURN type(r)       AS action,
           p.product_id  AS product_id,
           p.title        AS title,
           p.brand        AS brand,
           p.price        AS price,
           p.rating       AS rating,
           p.image_url    AS image_url,
           p.sub_category AS category
    ORDER BY action DESC
    LIMIT 20
    """
    with neo4j_driver.session() as s:
        items = _to_list(s.run(query, uid=user_id))
    return {"user_id": user_id, "history": items}


# ── Route dong – phai o CUOI ────────────────────────────────────────────────

@router.get("/{user_id}")
async def recommend_collaborative(user_id: str):
    """
    Goi y 2-hop Collaborative Filtering.
    Neu user chua co lich su -> fallback top-rated.
    """
    with neo4j_driver.session() as s:
        items  = _to_list(s.run(COLLAB_QUERY, uid=user_id))
        method = "collaborative"
        if not items:
            items  = _to_list(s.run(TOP_RATED_QUERY))
            method = "fallback_top_rated"
    return {"user_id": user_id, "method": method, "items": items, "query": COLLAB_QUERY}
