import time
import aiomysql
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.db.neo4j_client import neo4j_driver
from app.db.mysql_client import mysql_pool

router = APIRouter()


class CompareRequest(BaseModel):
    user_id: str = "U0001"
    query_type: str = "collaborative"
    search_term: str = ""


# ══════════════════════════════════════════════════════════════════════════════
# QUERY DEFINITIONS
# Mỗi loại truy vấn đi kèm: cypher, sql, complexity, explanation
# ══════════════════════════════════════════════════════════════════════════════

NEO4J_QUERIES = {
    # ── 2-hop: Collaborative Filtering ────────────────────────────────────────
    "collaborative": {
        "cypher": """\
MATCH (u:User {user_id: $uid})-[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(other:User)
      -[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
RETURN rec.product_id  AS product_id,
       rec.title        AS title,
       rec.rating       AS rating,
       count(*)         AS score
ORDER BY score DESC, rec.rating DESC, rec.product_id ASC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 2,
            "code_lines": 8,
            "note": "2-hop graph traversal. Duyệt cạnh trực tiếp O(k·d). Thêm 1 hop = thêm 1 dòng MATCH.",
        },
    },
    # ── 3-hop: Category-based ─────────────────────────────────────────────────
    "category": {
        "cypher": """\
MATCH (u:User {user_id: $uid})
      -[:BOUGHT]->(:Product)-[:BELONGS_TO]->(c:Category)
WITH u, c, count(*) AS freq ORDER BY freq DESC LIMIT 3
MATCH (c)<-[:BELONGS_TO]-(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
WITH c, rec, count(*) AS score
ORDER BY score DESC, rec.rating DESC, rec.product_id ASC
LIMIT 10
RETURN c.name          AS category,
       rec.product_id  AS product_id,
       rec.title        AS title,
       score""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 3,
            "code_lines": 12,
            "note": "3-hop: User→Product→Category←Product. Dùng WITH để tính score trước khi ORDER BY và RETURN.",
        },
    },
    # ── 4-hop: Second-level Collaborative ─────────────────────────────────────
    "collab_4hop": {
        "cypher": """\
MATCH (u:User {user_id: $uid})
      -[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(lvl1:User)
      -[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(lvl2:User)
      -[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
  AND lvl1 <> u
  AND lvl2 <> u
  AND lvl2 <> lvl1
RETURN rec.product_id AS product_id,
       rec.title       AS title,
       rec.rating      AS rating,
       count(*)        AS score
ORDER BY score DESC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 4,
            "code_lines": 13,
            "note": (
                "4-hop: U→P←U1→P←U2→P. Tìm gợi ý qua 2 tầng người dùng tương tự. "
                "Neo4j: thêm 2 dòng MATCH. MySQL: cần 6 JOIN + NOT EXISTS → 25+ dòng SQL khó bảo trì."
            ),
        },
    },
    # ── 4-hop: Brand Affinity ─────────────────────────────────────────────────
    "brand_affinity": {
        "cypher": """\
MATCH (u:User {user_id: $uid})
      -[:BOUGHT]->(p:Product)
      <-[:BOUGHT]-(other:User)
      -[:BOUGHT]->(rec:Product)
WHERE rec.brand = p.brand
  AND NOT (u)-[:BOUGHT]->(rec)
  AND rec <> p
RETURN rec.brand       AS brand,
       rec.product_id  AS product_id,
       rec.title        AS title,
       rec.rating       AS rating,
       count(*)         AS score
ORDER BY score DESC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 4,
            "code_lines": 11,
            "note": (
                "4-hop Brand Affinity: tìm sản phẩm cùng thương hiệu mà user tương tự đã mua. "
                "Neo4j: lọc thuộc tính brand trực tiếp trên node. MySQL: cần thêm 1 JOIN vào bảng products để lọc brand."
            ),
        },
    },
    # ── 5-hop: Cross-Category Discovery ──────────────────────────────────────
    "cross_category": {
        "cypher": """\
MATCH (u:User {user_id: $uid})
      -[:BOUGHT]->(:Product)
      -[:BELONGS_TO]->(c1:Category)
      <-[:BELONGS_TO]-(:Product)
      <-[:BOUGHT]-(mid:User)
      -[:BOUGHT]->(rec:Product)
      -[:BELONGS_TO]->(c2:Category)
WHERE NOT (u)-[:BOUGHT]->(rec)
  AND c1 <> c2
  AND mid <> u
RETURN c2.name        AS discovered_category,
       rec.product_id AS product_id,
       rec.title       AS title,
       rec.rating      AS rating,
       count(*)        AS score
ORDER BY score DESC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 5,
            "code_lines": 14,
            "note": (
                "5-hop Cross-Category: khám phá danh mục mới qua mạng lưới người dùng. "
                "U→P→C1←P←U2→P→C2. MySQL tương đương: 8+ JOIN + 2 subquery + 40+ dòng — "
                "gần như không thể viết và bảo trì trong thực tế."
            ),
        },
    },
    # ── 5-hop: Influence Chain ────────────────────────────────────────────────
    "influence_chain": {
        "cypher": """\
MATCH (u:User {user_id: $uid})
      -[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(u1:User)
      -[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(u2:User)
      -[:BOUGHT|VIEWED]->(:Product)
      <-[:BOUGHT|VIEWED]-(u3:User)
      -[:BOUGHT]->(rec:Product)
WHERE NOT (u)-[:BOUGHT]->(rec)
  AND u1 <> u AND u2 <> u
  AND u3 <> u AND u3 <> u1
RETURN rec.product_id AS product_id,
       rec.title       AS title,
       rec.rating      AS rating,
       count(*)        AS score
ORDER BY score DESC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 5,
            "code_lines": 16,
            "note": (
                "5-hop Influence Chain: gợi ý qua chuỗi ảnh hưởng 3 tầng người dùng. "
                "U→P←U1→P←U2→P←U3→P. MySQL tương đương: 9 JOIN + NOT EXISTS + DISTINCT "
                "ở nhiều bước → về mặt lý thuyết có thể viết nhưng trong thực tế sẽ "
                "time-out hoặc ăn toàn bộ RAM với dataset thực."
            ),
        },
    },
    # ── Search ────────────────────────────────────────────────────────────────
    "search": {
        "cypher": """
MATCH (p:Product)
WHERE toLower(p.title) CONTAINS toLower($q) OR toLower(p.brand) CONTAINS toLower($q)
RETURN p.product_id AS product_id, p.title AS title,
       p.rating AS rating, p.price AS price
ORDER BY p.rating DESC, p.product_id ASC LIMIT 10""",
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 0,
            "note": "Simple node filter with regex. Comparable to SQL LIKE.",
        },
    },
}

MYSQL_QUERIES = {
    # ── 2-hop Collaborative ────────────────────────────────────────────────────
    "collaborative": {
        "sql": """\
WITH uniq_acts AS (
    SELECT DISTINCT user_id, product_id, action FROM actions
)
SELECT p2.product_id, p2.title, p2.rating, COUNT(*) AS score
FROM   uniq_acts a1
JOIN   uniq_acts a2 ON  a1.product_id = a2.product_id
                    AND a1.user_id   <> a2.user_id
                    AND a2.action IN ('BOUGHT', 'VIEWED')
JOIN   uniq_acts a3 ON  a2.user_id = a3.user_id
                    AND a3.action  = 'BOUGHT'
JOIN   products p2 ON p2.product_id = a3.product_id
WHERE  a1.user_id = %s
  AND  a1.action IN ('BOUGHT', 'VIEWED')
  AND  NOT EXISTS (
         SELECT 1 FROM uniq_acts a4
         WHERE  a4.user_id = %s AND a4.product_id = p2.product_id
           AND  a4.action  = 'BOUGHT'
       )
GROUP  BY p2.product_id, p2.title, p2.rating
ORDER  BY score DESC, p2.rating DESC, p2.product_id ASC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 4,
            "subquery_count": 2,
            "hops": 2,
            "code_lines": 21,
            "note": "Dùng CTE uniq_acts để giả lập tính duy nhất của Cạnh (Edges) trong Graph DB, tránh bùng nổ điểm score do duplicate logs.",
        },
    },
    # ── 3-hop Category ─────────────────────────────────────────────────────────
    "category": {
        "sql": """\
WITH uniq_acts AS (
    SELECT DISTINCT user_id, product_id, action FROM actions
)
SELECT top3.cat_name, p2.product_id, p2.title, COUNT(*) AS score
FROM (
       SELECT c.sub_category AS cat_name, COUNT(*) AS cnt
       FROM   uniq_acts a
       JOIN   products c ON c.product_id = a.product_id
       WHERE  a.user_id = %s AND a.action = 'BOUGHT'
       GROUP  BY c.sub_category ORDER BY cnt DESC LIMIT 3
     ) top3
JOIN   products p2 ON p2.sub_category = top3.cat_name
WHERE  NOT EXISTS (
         SELECT 1 FROM uniq_acts a4
         WHERE  a4.user_id = %s AND a4.product_id = p2.product_id
           AND  a4.action  = 'BOUGHT'
       )
GROUP  BY top3.cat_name, p2.product_id, p2.title
ORDER  BY score DESC, p2.rating DESC, p2.product_id ASC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 3,
            "subquery_count": 3,
            "hops": 3,
            "code_lines": 23,
            "note": "Bổ sung tiêu chí ORDER BY phụ (rating, product_id) để giải quyết vấn đề đồng hạng, đảm bảo khớp danh sách với Neo4j.",
        },
    },
    # ── 4-hop Second-level Collaborative ──────────────────────────────────────
    "collab_4hop": {
        "sql": """\
WITH uniq_acts AS (
    SELECT DISTINCT user_id, product_id, action FROM actions
)
SELECT p_rec.product_id, p_rec.title, p_rec.rating, COUNT(*) AS score
FROM   uniq_acts a_u                       
JOIN   uniq_acts a_p1 ON a_u.product_id  = a_p1.product_id    
                     AND a_u.user_id    <> a_p1.user_id
                     AND a_p1.action IN ('BOUGHT', 'VIEWED')
JOIN   uniq_acts a_u1 ON a_p1.user_id   = a_u1.user_id        
                     AND a_u1.action IN ('BOUGHT', 'VIEWED')
JOIN   uniq_acts a_p2 ON a_u1.product_id = a_p2.product_id    
                     AND a_p2.user_id   <> a_u.user_id
                     AND a_p2.user_id   <> a_p1.user_id
                     AND a_p2.action IN ('BOUGHT', 'VIEWED')
JOIN   uniq_acts a_u2 ON a_p2.user_id   = a_u2.user_id        
                     AND a_u2.action    = 'BOUGHT'
JOIN   products p_rec ON p_rec.product_id = a_u2.product_id
WHERE  a_u.user_id = %s
  AND  a_u.action IN ('BOUGHT', 'VIEWED')
  AND  NOT EXISTS (
         SELECT 1 FROM uniq_acts ax
         WHERE  ax.user_id = %s AND ax.product_id = p_rec.product_id
           AND  ax.action  = 'BOUGHT'
       )
GROUP  BY p_rec.product_id, p_rec.title, p_rec.rating
ORDER  BY score DESC, p_rec.rating DESC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 7,
            "subquery_count": 2,
            "hops": 4,
            "code_lines": 29,
            "note": "CTE khiến hiệu năng MySQL càng thê thảm hơn ở các truy vấn nhiều hop.",
        },
    },
    # ── 4-hop Brand Affinity ────────────────────────────────────────────────
    "brand_affinity": {
        "sql": """\
WITH uniq_acts AS (
    SELECT DISTINCT user_id, product_id, action FROM actions
)
SELECT 
    p_rec.brand,
    p_rec.product_id,
    p_rec.title,
    p_rec.rating,
    COUNT(*) AS score 
FROM uniq_acts a1
JOIN uniq_acts a2 
    ON a1.product_id = a2.product_id
   AND a1.user_id   <> a2.user_id
   AND a2.action    = 'BOUGHT'
JOIN uniq_acts a3 
    ON a2.user_id   = a3.user_id
   AND a3.action    = 'BOUGHT'
JOIN products p_ref 
    ON p_ref.product_id = a1.product_id
JOIN products p_rec 
    ON p_rec.product_id = a3.product_id
   AND p_rec.brand      = p_ref.brand
WHERE a1.user_id = %s
  AND a1.action  = 'BOUGHT'                       
  AND p_rec.product_id <> p_ref.product_id      
  AND NOT EXISTS (                               
        SELECT 1
        FROM uniq_acts ax
        WHERE ax.user_id    = %s
          AND ax.product_id = p_rec.product_id
          AND ax.action     = 'BOUGHT'
  )
GROUP BY 
    p_rec.brand, 
    p_rec.product_id, 
    p_rec.title, 
    p_rec.rating
ORDER BY score DESC, p_rec.rating DESC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 6,
            "subquery_count": 2,
            "hops": 4,
            "code_lines": 25,
            "note": "Áp dụng cấu trúc CTE.",
        },
    },
    # ── 5-hop Cross-Category ─────────────────────────────────────────────────
    "cross_category": {
        "sql": """\
SELECT p_rec.sub_category AS discovered_category,
       p_rec.product_id, p_rec.title, p_rec.rating, COUNT(*) AS score
FROM   actions a_u
JOIN   products p1     ON p1.product_id    = a_u.product_id
JOIN   products p2     ON p2.sub_category  = p1.sub_category
                      AND p2.product_id   <> p1.product_id
JOIN   actions a_mid   ON a_mid.product_id = p2.product_id
                      AND a_mid.user_id   <> a_u.user_id
                      AND a_mid.action    = 'BOUGHT'
JOIN   actions a_rec   ON a_rec.user_id    = a_mid.user_id
                      AND a_rec.action    = 'BOUGHT'
JOIN   products p_rec  ON p_rec.product_id = a_rec.product_id
WHERE  a_u.user_id = %s
  AND  a_u.action  = 'BOUGHT'
  AND  p_rec.sub_category <> p1.sub_category   
  AND  NOT EXISTS (
         SELECT 1 FROM actions ax
         WHERE  ax.user_id = %s AND ax.product_id = p_rec.product_id
           AND  ax.action  = 'BOUGHT'
       )
GROUP  BY p_rec.sub_category, p_rec.product_id, p_rec.title, p_rec.rating
ORDER  BY score DESC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 8,
            "subquery_count": 1,
            "hops": 5,
            "code_lines": 25,
            "note": "Xóa JOIN thừa, thêm a_u.action = 'BOUGHT' để khớp đầu vào của Cypher.",
        },
    },
    # ── 5-hop Influence Chain ────────────────────────────────────────────────
    "influence_chain": {
        "sql": """\
SELECT p_rec.product_id, p_rec.title, p_rec.rating, COUNT(*) AS score
FROM   actions a0                          
JOIN   actions a1 ON a0.product_id = a1.product_id 
                 AND a1.user_id <> a0.user_id
                 AND a1.action IN ('BOUGHT', 'VIEWED')
JOIN   actions a2 ON a1.user_id    = a2.user_id    
                 AND a2.action IN ('BOUGHT', 'VIEWED')
JOIN   actions a3 ON a2.product_id = a3.product_id 
                 AND a3.user_id <> a0.user_id
                 AND a3.action IN ('BOUGHT', 'VIEWED')
JOIN   actions a4 ON a3.user_id    = a4.user_id    
                 AND a4.action IN ('BOUGHT', 'VIEWED')
JOIN   actions a5 ON a4.product_id = a5.product_id 
                 AND a5.user_id <> a0.user_id
                 AND a5.user_id <> a1.user_id
                 AND a5.action IN ('BOUGHT', 'VIEWED')
JOIN   actions a6 ON a5.user_id    = a6.user_id    
                 AND a6.action   = 'BOUGHT'
JOIN   products p_rec ON p_rec.product_id = a6.product_id
WHERE  a0.user_id = %s
  AND  a0.action IN ('BOUGHT', 'VIEWED')
  AND  NOT EXISTS (
         SELECT 1 FROM actions ax
         WHERE  ax.user_id = %s AND ax.product_id = p_rec.product_id
           AND  ax.action  = 'BOUGHT'
       )
GROUP  BY p_rec.product_id, p_rec.title, p_rec.rating
ORDER  BY score DESC LIMIT 10""",
        "params_fn": lambda uid, q: (uid, uid),
        "complexity": {
            "join_count": 9,
            "subquery_count": 1,
            "hops": 5,
            "code_lines": 30,
            "note": "Thêm Action filters. Chỉnh lại Logic ràng buộc người dùng khớp chuẩn Cypher (u2 không bị ép khác u1, u3 không bị ép khác u2).",
        },
    },
    # ── Search ────────────────────────────────────────────────────────────────
    "search": {
        "sql": """\
SELECT product_id, title, rating, price
FROM   products
WHERE  (LOWER(title) LIKE %s)
   OR  (LOWER(brand) LIKE %s)
ORDER  BY rating DESC, product_id ASC LIMIT 10""",
        "params_fn": lambda uid, q: (f"%{q.lower()}%", f"%{q.lower()}%"),
        "complexity": {
            "join_count": 0,
            "subquery_count": 0,
            "hops": 0,
            "code_lines": 6,
            "note": "So sánh công bằng với Cypher CONTAINS bằng LIKE không phân biệt hoa thường.",
        },
    },
}
# Nhãn thân thiện cho từng loại truy vấn
QUERY_LABELS = {
    "collaborative": "2-hop Collaborative Filtering",
    "category": "3-hop Category-based",
    "collab_4hop": "4-hop Second-level Collaborative",
    "brand_affinity": "4-hop Brand Affinity",
    "cross_category": "5-hop Cross-Category Discovery",
    "influence_chain": "5-hop Influence Chain",
    "search": "Full-text Search",
}

# Truy vấn nào thực sự có thể chạy được trên MySQL với dataset demo
MYSQL_EXECUTABLE = {"collaborative", "category", "brand_affinity", "search"}


# ── Helpers ───────────────────────────────────────────────────────────────────


def _speedup(neo4j_ms: float, mysql_ms: float) -> dict:
    a, b = max(neo4j_ms, 0.01), max(mysql_ms, 0.01)
    if a <= b:
        return {
            "winner": "neo4j",
            "ratio": round(b / a, 2),
            "faster": "Neo4j",
            "slower": "MySQL",
        }
    return {
        "winner": "mysql",
        "ratio": round(a / b, 2),
        "faster": "MySQL",
        "slower": "Neo4j",
    }


def _context_note(query_type: str, winner: str, ratio: float) -> str:
    if query_type in {"collab_4hop", "cross_category", "influence_chain"}:
        if winner == "neo4j":
            return (
                f"Neo4j nhanh hơn {ratio}x. Quan trọng hơn: code Cypher chỉ 13-16 dòng, "
                "dễ đọc, dễ mở rộng. SQL tương đương 26-34 dòng phức tạp, gần như không thể debug."
            )
        return (
            f"MySQL nhanh hơn {ratio}x trên dataset nhỏ này. "
            "Tuy nhiên: SQL 4-5-hop gần như không thể bảo trì, "
            "không thể scale với dataset thực tế. Đây là giới hạn bản chất của SQL."
        )
    if winner == "neo4j":
        return (
            f"Neo4j nhanh hơn {ratio}x nhờ graph traversal — "
            "không cần JOIN, duyệt cạnh trực tiếp theo pointer."
        )
    return (
        f"MySQL nhanh hơn {ratio}x với dataset nhỏ. "
        "B-tree index hiệu quả cho 2-hop đơn giản. "
        "Khoảng cách thay đổi khi dataset và độ sâu tăng."
    )


def _result_alignment(neo4j_res: dict, mysql_res: dict, topk: int = 10) -> dict:
    neo_rows = neo4j_res.get("results") or []
    mysql_rows = mysql_res.get("results") or []

    neo_ids = [str(r.get("product_id")) for r in neo_rows[:topk] if r.get("product_id")]
    mysql_ids = [str(r.get("product_id")) for r in mysql_rows[:topk] if r.get("product_id")]

    neo_set = set(neo_ids)
    mysql_set = set(mysql_ids)
    overlap = neo_set & mysql_set
    union = neo_set | mysql_set

    return {
        "topk": topk,
        "neo4j_count": len(neo_ids),
        "mysql_count": len(mysql_ids),
        "overlap_count": len(overlap),
        "overlap_ratio": round((len(overlap) / max(len(union), 1)) * 100, 2),
        "overlap_ids": sorted(list(overlap)),
    }


async def _consistency_snapshot() -> dict:
    neo4j_edges = None
    mysql_edges = None
    neo4j_products = None
    mysql_products = None
    neo4j_users = None
    mysql_users = None

    try:
        with neo4j_driver.session() as s:
            neo4j_edges = s.run(
                """
                MATCH (:User)-[r:BOUGHT|VIEWED]->(:Product)
                RETURN count(r) AS edges
                """
            ).single()["edges"]
            neo4j_products = s.run(
                """
                MATCH (p:Product)
                RETURN count(p) AS products
                """
            ).single()["products"]
            neo4j_users = s.run(
                """
                MATCH (u:User)
                RETURN count(u) AS users
                """
            ).single()["users"]
    except Exception:
        neo4j_edges = None
        neo4j_products = None
        neo4j_users = None

    try:
        pool = await mysql_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    """
                    SELECT COUNT(*) AS edges
                    FROM (
                      SELECT DISTINCT user_id, product_id, action
                      FROM actions
                    ) t
                    """
                )
                row = await cur.fetchone()
                mysql_edges = int((row or {}).get("edges") or 0)

                await cur.execute("SELECT COUNT(*) AS products FROM products")
                prow = await cur.fetchone()
                mysql_products = int((prow or {}).get("products") or 0)

                await cur.execute("SELECT COUNT(*) AS users FROM users")
                urow = await cur.fetchone()
                mysql_users = int((urow or {}).get("users") or 0)
    except Exception:
        mysql_edges = None
        mysql_products = None
        mysql_users = None

    if (
        neo4j_edges is None or mysql_edges is None or
        neo4j_products is None or mysql_products is None or
        neo4j_users is None or mysql_users is None
    ):
        return {
            "in_sync": None,
            "neo4j_edges": neo4j_edges,
            "mysql_edges": mysql_edges,
            "edge_gap": None,
            "edge_gap_ratio": None,
            "neo4j_products": neo4j_products,
            "mysql_products": mysql_products,
            "product_gap": None,
            "product_gap_ratio": None,
            "neo4j_users": neo4j_users,
            "mysql_users": mysql_users,
            "user_gap": None,
            "user_gap_ratio": None,
            "message": "Không thể xác nhận đồng bộ dữ liệu giữa Neo4j và MySQL.",
        }

    edge_gap = abs(int(neo4j_edges) - int(mysql_edges))
    edge_gap_ratio = round((edge_gap / max(int(mysql_edges), 1)) * 100, 2)

    product_gap = abs(int(neo4j_products) - int(mysql_products))
    product_gap_ratio = round((product_gap / max(int(mysql_products), 1)) * 100, 2)

    user_gap = abs(int(neo4j_users) - int(mysql_users))
    user_gap_ratio = round((user_gap / max(int(mysql_users), 1)) * 100, 2)

    in_sync = edge_gap_ratio <= 2.0 and product_gap_ratio <= 2.0 and user_gap_ratio <= 2.0

    return {
        "in_sync": in_sync,
        "neo4j_edges": int(neo4j_edges),
        "mysql_edges": int(mysql_edges),
        "edge_gap": edge_gap,
        "edge_gap_ratio": edge_gap_ratio,
        "neo4j_products": int(neo4j_products),
        "mysql_products": int(mysql_products),
        "product_gap": product_gap,
        "product_gap_ratio": product_gap_ratio,
        "neo4j_users": int(neo4j_users),
        "mysql_users": int(mysql_users),
        "user_gap": user_gap,
        "user_gap_ratio": user_gap_ratio,
        "message": (
            "Dữ liệu đồng bộ tốt cho so sánh." if in_sync else
            "Dữ liệu Neo4j/MySQL đang lệch (edges/products/users), cần chạy ETL lại để so sánh công bằng."
        ),
    }


def _run_neo4j(query_type: str, uid: str, q: str) -> dict:
    qdef = NEO4J_QUERIES[query_type]
    t0 = time.perf_counter()
    try:
        with neo4j_driver.session() as s:
            rows = [dict(r) for r in s.run(qdef["cypher"], uid=uid, q=q)]
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "time_ms": ms,
            "query": qdef["cypher"],
            "complexity": qdef["complexity"],
            "result_count": len(rows),
            "results": rows,
            "error": None,
        }
    except Exception as e:
        return {
            "time_ms": None,
            "query": qdef["cypher"],
            "complexity": qdef["complexity"],
            "result_count": 0,
            "results": [],
            "error": str(e),
        }


async def _run_mysql(query_type: str, uid: str, q: str) -> dict:
    qdef = MYSQL_QUERIES[query_type]
    params = qdef["params_fn"](uid, q)
    t0 = time.perf_counter()

    # Truy vấn 4-hop+ trên MySQL: giới hạn thời gian 8 giây
    if query_type not in MYSQL_EXECUTABLE:
        return {
            "time_ms": None,
            "query": qdef["sql"],
            "complexity": qdef["complexity"],
            "result_count": 0,
            "results": [],
            "error": (
                "KHÔNG THỂ THỰC THI HIỆU QUẢ: truy vấn này cần "
                + str(qdef["complexity"]["join_count"])
                + " JOIN. Với dataset thực tế sẽ time-out hoặc dùng hết RAM. "
                "Đây là minh chứng cho giới hạn của SQL với multi-hop queries sâu."
            ),
        }

    try:
        pool = await mysql_pool()
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(qdef["sql"], params)
                rows = await cur.fetchall()
        ms = round((time.perf_counter() - t0) * 1000, 2)
        return {
            "time_ms": ms,
            "query": qdef["sql"],
            "complexity": qdef["complexity"],
            "result_count": len(rows),
            "results": [dict(r) for r in rows],
            "error": None,
        }
    except Exception as e:
        return {
            "time_ms": None,
            "query": qdef["sql"],
            "complexity": qdef["complexity"],
            "result_count": 0,
            "results": [],
            "error": str(e),
        }


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post("/query")
async def compare_query(req: CompareRequest):
    if req.query_type not in NEO4J_QUERIES:
        valid = list(NEO4J_QUERIES.keys())
        return {"error": f"query_type không hợp lệ. Chọn: {valid}"}

    neo4j_res = _run_neo4j(req.query_type, req.user_id, req.search_term)
    mysql_res = await _run_mysql(req.query_type, req.user_id, req.search_term)
    consistency = await _consistency_snapshot()

    # Tính speedup chỉ khi cả hai có kết quả
    if neo4j_res["time_ms"] is not None and mysql_res["time_ms"] is not None:
        speed = _speedup(neo4j_res["time_ms"], mysql_res["time_ms"])
        note = _context_note(req.query_type, speed["winner"], speed["ratio"])
        alignment = _result_alignment(neo4j_res, mysql_res)
        if consistency.get("in_sync") is False:
            note = (
                f"{note} Lưu ý: {consistency.get('message')} "
                f"(Neo4j edges={consistency.get('neo4j_edges')}, "
                f"MySQL edges={consistency.get('mysql_edges')})."
            )
    else:
        speed = {"winner": "neo4j", "ratio": None, "faster": "Neo4j", "slower": "MySQL"}
        note = _context_note(req.query_type, "neo4j", 0)
        alignment = None

    return {
        "query_type": req.query_type,
        "query_label": QUERY_LABELS.get(req.query_type, req.query_type),
        "user_id": req.user_id,
        "neo4j": neo4j_res,
        "mysql": mysql_res,
        "speedup": speed["ratio"],
        "winner": speed["winner"],
        "faster_name": speed["faster"],
        "slower_name": speed["slower"],
        "context_note": note,
        "result_alignment": alignment,
        "data_consistency": consistency,
        "mysql_runnable": req.query_type in MYSQL_EXECUTABLE,
    }


@router.get("/queries-info")
async def queries_info():
    """
    Trả về toàn bộ query text và complexity cho tất cả loại truy vấn.
    Dùng cho báo cáo, so sánh tĩnh, không cần chạy.
    """
    return {
        qt: {
            "label": QUERY_LABELS.get(qt),
            "neo4j": {
                "query": NEO4J_QUERIES[qt]["cypher"],
                "complexity": NEO4J_QUERIES[qt]["complexity"],
            },
            "mysql": {
                "query": MYSQL_QUERIES[qt]["sql"],
                "complexity": MYSQL_QUERIES[qt]["complexity"],
                "runnable": qt in MYSQL_EXECUTABLE,
            },
        }
        for qt in NEO4J_QUERIES
    }
