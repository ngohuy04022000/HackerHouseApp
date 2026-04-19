"""
app/routers/sui.py
==================
API endpoints cho tích hợp SUI blockchain.

Endpoints:
  GET  /sui/status                  — kiểm tra kết nối blockchain
  GET  /sui/pool-stats              — thống kê RewardPool
  GET  /sui/wallet/{address}        — tài sản ví (GREC + NFTs + score)
  POST /sui/reward                  — phát GREC token (admin/backend)
  POST /sui/mint-nft                — đúc Product NFT (admin/backend)
  POST /sui/update-score            — cập nhật điểm gợi ý on-chain
  POST /sui/register-user           — đăng ký user profile on-chain
  POST /sui/fund-pool               — nạp GREC vào pool (admin)
  GET  /sui/recommend-with-chain/{uid} — gợi ý kết hợp Neo4j + lưu score
  GET  /sui/explorer/{object_id}    — link explorer cho object bất kỳ
"""

import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.sui.client import get_sui_client
from app.db.neo4j_client import neo4j_driver

router = APIRouter()


# ── Request models ────────────────────────────────────────────────────────────


class RewardRequest(BaseModel):
    recipient_address: str
    profile_object_id: str = ""
    product_id: str
    action: str = "VIEWED"  # VIEWED | BOUGHT | REVIEWED
    simulated: bool = False

class MintNFTRequest(BaseModel):
    recipient_address: str
    product_id: str
    name: str
    description: str = ""
    image_url: str = ""
    brand: str = ""
    category: str = ""
    price_grec: int = 100_000_000
    rating: int = 0


class UpdateScoreRequest(BaseModel):
    owner_address: str
    top_products: list[str]
    scores: list[int]


class RegisterUserRequest(BaseModel):
    user_id: str
    wallet_address: str


class FundPoolRequest(BaseModel):
    amount_grec: int  # số GREC (đơn vị: 1 = 1_000_000 raw units)


class OnboardUserRequest(BaseModel):
    user_id: str
    wallet_address: str
    auto_register: bool = True


def _tx_explorer_link(digest: Optional[str]) -> Optional[str]:
    if not digest:
        return None
    network = os.getenv("SUI_NETWORK", "testnet")
    return f"https://suiexplorer.com/txblock/{digest}?network={network}"


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.get("/status")
async def sui_status():
    """Kiểm tra kết nối SUI blockchain và trạng thái contract."""
    client = get_sui_client()
    pool = await client.get_pool_stats()
    configured = client.is_configured()
    if configured:
        message = "SUI blockchain connected and ready"
    elif client.missing_config:
        message = f"SUI not configured — missing: {', '.join(client.missing_config)}"
    else:
        message = "SUI not configured — check private key, package ID, and pool IDs"
    return {
        "configured": configured,
        "network": client.network,
        "package_id": os.getenv("SUI_PACKAGE_ID", "not_set"),
        "pool_id": os.getenv("SUI_POOL_ID", "not_set"),
        "default_profile_id": client.default_profile_id or None,
        "admin_address": client.admin_address,
        "pool_stats": pool,
        "explorer_base": "https://suiexplorer.com",
        "rpc_url": client.rpc_url if configured else "N/A",
        "simulated": client.simulated,
        "missing_config": client.missing_config,
        "message": message,
    }


@router.get("/pool-stats")
async def pool_stats():
    """Thống kê RewardPool: số GREC còn lại, tổng đã phát, số giao dịch."""
    client = get_sui_client()
    return await client.get_pool_stats()


@router.get("/wallet/{address}")
async def wallet_assets(address: str):
    client = get_sui_client()
    result = await client.get_wallet_assets(address)
    return result


@router.get("/quick-actions")
async def quick_actions(address: Optional[str] = None):
    """Gợi ý bước tiếp theo để tích hợp SUI mượt hơn cho người dùng."""
    client = get_sui_client()
    pool = await client.get_pool_stats()

    actions = []
    if not client.is_configured():
        actions.append(
            {
                "code": "CONFIGURE_SUI",
                "priority": "high",
                "title": "Cấu hình SUI backend",
                "description": "Thiết lập SUI_PRIVATE_KEY, SUI_PACKAGE_ID, SUI_POOL_ID và các object ID bắt buộc.",
            }
        )

    pool_balance = 0
    try:
        pool_balance = int(pool.get("balance_raw", 0) or 0)
    except Exception:
        pool_balance = 0
    if pool_balance < 10_000_000:
        actions.append(
            {
                "code": "FUND_POOL",
                "priority": "medium",
                "title": "Nạp thêm GREC cho pool",
                "description": "RewardPool đang thấp, nên gọi /sui/fund-pool để tránh fail khi phát thưởng.",
            }
        )

    wallet_summary = None
    if address:
        wallet_summary = await client.get_wallet_assets(address)
        if not wallet_summary.get("default_profile_object_id"):
            actions.append(
                {
                    "code": "REGISTER_PROFILE",
                    "priority": "high",
                    "title": "Đăng ký UserProfile",
                    "description": "Ví chưa có UserProfile. Hãy gọi /sui/register-user hoặc /sui/onboard-user.",
                }
            )
        if not wallet_summary.get("recommend_score"):
            actions.append(
                {
                    "code": "SYNC_RECOMMEND_SCORE",
                    "priority": "low",
                    "title": "Đồng bộ điểm gợi ý on-chain",
                    "description": "Chạy /sui/recommend-with-chain/{uid} để lưu top-5 recommendation lên SUI.",
                }
            )

    if not actions:
        actions.append(
            {
                "code": "ALL_GOOD",
                "priority": "low",
                "title": "Hệ thống đã sẵn sàng",
                "description": "Bạn có thể phát reward, mint NFT, và cập nhật recommend score on-chain.",
            }
        )

    return {
        "network": client.network,
        "configured": client.is_configured(),
        "address": address,
        "pool_balance_grec": pool.get("balance_grec"),
        "actions": actions,
        "wallet_summary": wallet_summary,
    }


@router.post("/onboard-user")
async def onboard_user(req: OnboardUserRequest):
    """
    Onboarding nhanh cho SUI:
      1) Validate ví
      2) Lấy wallet assets
      3) Tự đăng ký UserProfile (tuỳ chọn)
      4) Trả về next actions để frontend hiển thị
    """
    user_id = req.user_id.strip()
    wallet = req.wallet_address.strip()
    if not user_id:
        raise HTTPException(400, "user_id không được để trống")
    if not wallet.startswith("0x"):
        raise HTTPException(400, "wallet_address phải bắt đầu bằng 0x")

    client = get_sui_client()
    registration = None
    profile_object_id = await client.resolve_profile_object_id(wallet)

    if req.auto_register and client.is_configured() and not profile_object_id:
        try:
            registration = await client.register_user(user_id)
        except ValueError as e:
            raise HTTPException(400, str(e)) from e
        except Exception as e:
            raise HTTPException(502, f"Onboard register runtime error: {e}") from e

        if not registration.get("success", False):
            raise HTTPException(502, registration.get("error", "Onboard register failed"))
        profile_object_id = await client.resolve_profile_object_id(wallet)

    wallet_assets_data = await client.get_wallet_assets(wallet)
    actions = await quick_actions(address=wallet)

    return {
        "success": True,
        "user_id": user_id,
        "wallet_address": wallet,
        "profile_object_id": profile_object_id,
        "registration": registration,
        "wallet_assets": wallet_assets_data,
        "quick_actions": actions.get("actions", []),
        "message": "Onboarding SUI hoàn tất",
    }


@router.post("/reward")
async def reward_user(req: RewardRequest):
    if req.action not in ("VIEWED", "BOUGHT", "REVIEWED"):
        raise HTTPException(400, "action phải là VIEWED, BOUGHT, hoặc REVIEWED")

    client = get_sui_client()
    profile_object_id = req.profile_object_id.strip() or client.default_profile_id
    if client.is_configured() and not profile_object_id:
        profile_object_id = await client.resolve_profile_object_id(req.recipient_address)
    if client.is_configured() and not profile_object_id:
        profile_object_id = await client.resolve_profile_object_id(client.admin_address)
    if client.is_configured() and not profile_object_id:
        raise HTTPException(
            400,
            (
                "Thiếu profile_object_id. Có thể gửi trực tiếp trong request, cấu hình env "
                "SUI_PROFILE_ID, hoặc gọi /sui/wallet/{address} để lấy UserProfile object_id."
            ),
        )
    try:
        result = await client.reward_user(
            recipient_address=req.recipient_address,
            profile_object_id=profile_object_id,
            product_id=req.product_id,
            action=req.action,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Reward transaction runtime error: {e}") from e
    if not result.get("success", False):
        raise HTTPException(502, result.get("error", "Reward transaction failed"))

    reward_amounts = {"VIEWED": 10, "BOUGHT": 100, "REVIEWED": 50}
    return {
        **result,
        "grec_amount": reward_amounts[req.action],
        "product_id": req.product_id,
        "action": req.action,
        "explorer_link": _tx_explorer_link(result.get("digest")),
    }


@router.post("/mint-nft")
async def mint_nft(req: MintNFTRequest):
    """
    Đúc Product NFT cho user sau khi mua sản phẩm.
    NFT sẽ được transfer đến ví của user.
    """
    client = get_sui_client()
    try:
        result = await client.mint_product_nft(
            recipient_address=req.recipient_address,
            product_id=req.product_id,
            name=req.name,
            description=req.description or f"Product NFT: {req.name}",
            image_url=req.image_url,
            brand=req.brand,
            category=req.category,
            price_grec=req.price_grec,
            rating=req.rating,
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Mint NFT transaction runtime error: {e}") from e
    if not result.get("success", False):
        raise HTTPException(502, result.get("error", "Mint NFT transaction failed"))
    return {
        **result,
        "explorer_link": _tx_explorer_link(result.get("digest")),
    }


@router.post("/update-score")
async def update_score(req: UpdateScoreRequest):
    """
    Cập nhật RecommendScore on-chain cho user.
    Thường gọi sau khi chạy Neo4j collaborative query.
    """
    if len(req.top_products) != len(req.scores):
        raise HTTPException(400, "top_products và scores phải cùng độ dài")

    client = get_sui_client()
    try:
        result = await client.update_recommend_score(
            owner_address=req.owner_address,
            top_products=req.top_products[:5],
            scores=req.scores[:5],
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Update score transaction runtime error: {e}") from e
    if not result.get("success", False):
        raise HTTPException(502, result.get("error", "Update score transaction failed"))
    return {
        **result,
        "top_products_count": len(req.top_products[:5]),
        "explorer_link": _tx_explorer_link(result.get("digest")),
    }


@router.post("/fund-pool")
async def fund_pool(req: FundPoolRequest):
    """
    Nạp GREC vào RewardPool. Chỉ admin được gọi.
    amount_grec: số GREC (ví dụ 1000 = 1000 GREC = 1_000_000_000 raw units).
    """
    if req.amount_grec <= 0:
        raise HTTPException(400, "amount_grec phải > 0")

    raw_amount = req.amount_grec * 1_000_000
    client = get_sui_client()
    try:
        result = await client.fund_pool(raw_amount)
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Fund pool transaction runtime error: {e}") from e
    if not result.get("success", False):
        raise HTTPException(502, result.get("error", "Fund pool transaction failed"))
    return {
        **result,
        "funded_grec": req.amount_grec,
        "funded_raw": raw_amount,
    }


@router.post("/register-user")
async def register_user(req: RegisterUserRequest):
    """Đăng ký UserProfile on-chain để dùng cho reward/update-score."""
    if not req.user_id.strip():
        raise HTTPException(400, "user_id không được để trống")
    if not req.wallet_address.strip().startswith("0x"):
        raise HTTPException(400, "wallet_address phải bắt đầu bằng 0x")

    client = get_sui_client()
    if client.is_configured() and req.wallet_address.strip().lower() != client.admin_address.lower():
        raise HTTPException(
            400,
            (
                "wallet_address phải trùng admin_address hiện tại do register_user dùng sender "
                "trên private key backend."
            ),
        )

    existing_profile = await client.resolve_profile_object_id(req.wallet_address.strip())
    if existing_profile:
        return {
            "success": True,
            "already_exists": True,
            "wallet_address": req.wallet_address.strip(),
            "profile_object_id": existing_profile,
            "message": "UserProfile đã tồn tại, không cần đăng ký lại",
        }

    try:
        result = await client.register_user(req.user_id.strip())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, f"Register user transaction runtime error: {e}") from e

    if not result.get("success", False):
        raise HTTPException(502, result.get("error", "Register user transaction failed"))

    profile_object_id = await client.resolve_profile_object_id(req.wallet_address.strip())
    return {
        **result,
        "wallet_address": req.wallet_address.strip(),
        "profile_object_id": profile_object_id,
        "explorer_link": _tx_explorer_link(result.get("digest")),
    }


@router.get("/recommend-with-chain/{user_id}")
async def recommend_with_blockchain(
    user_id: str,
    wallet_address: Optional[str] = None,
    limit: int = 10,
):
    """
    Gợi ý kết hợp:
      1. Chạy Neo4j collaborative query
      2. Nếu có wallet_address → cập nhật RecommendScore on-chain (background)
      3. Trả về recommendations + chain metadata

    Đây là luồng tích hợp chính: off-chain intelligence + on-chain proof.
    """
    # Bước 1: Chạy Neo4j query (logic gợi ý chính)
    COLLAB_QUERY = """
    MATCH (u:User {user_id: $uid})-[:BOUGHT|VIEWED]->(:Product)
          <-[:BOUGHT|VIEWED]-(other:User)-[:BOUGHT]->(rec:Product)
    WHERE NOT (u)-[:BOUGHT]->(rec)
    RETURN rec.product_id AS product_id,
           rec.title       AS title,
           rec.brand       AS brand,
           rec.rating      AS rating,
           rec.image_url   AS image_url,
           rec.sub_category AS category,
           count(*)         AS score
    ORDER BY score DESC LIMIT $limit
    """
    recommendations = []
    try:
        with neo4j_driver.session() as s:
            rows = s.run(COLLAB_QUERY, uid=user_id, limit=limit)
            recommendations = [dict(r) for r in rows]
    except Exception:
        recommendations = []

    # Bước 2: Cập nhật on-chain nếu có wallet (fire-and-forget)
    chain_tx = None
    if wallet_address and recommendations:
        client = get_sui_client()
        top_pids = [r["product_id"] for r in recommendations[:5]]
        top_scores = [int(r["score"]) for r in recommendations[:5]]
        try:
            chain_tx = await client.update_recommend_score(
                owner_address=wallet_address,
                top_products=top_pids,
                scores=top_scores,
            )
            if chain_tx.get("success"):
                chain_tx["explorer_link"] = _tx_explorer_link(chain_tx.get("digest"))
        except Exception as e:
            chain_tx = {"success": False, "error": str(e)}

    return {
        "user_id": user_id,
        "method": "neo4j_collaborative_2hop",
        "items": recommendations,
        "chain_update": chain_tx,
        "wallet_address": wallet_address,
        "on_chain": chain_tx is not None and chain_tx.get("success"),
        "message": (
            "Recommendations computed by Neo4j, top-5 scores stored on SUI blockchain"
            if chain_tx and chain_tx.get("success")
            else (
                "Recommendations by Neo4j (on-chain update failed)"
                if chain_tx and not chain_tx.get("success")
                else "Recommendations by Neo4j (no wallet connected for on-chain update)"
            )
        ),
    }


@router.get("/explorer/{object_id}")
async def explorer_link(object_id: str):
    """Trả về link SUI Explorer cho một object bất kỳ."""
    network = os.getenv("SUI_NETWORK", "testnet")
    return {
        "object_id": object_id,
        "network": network,
        "object_url": f"https://suiexplorer.com/object/{object_id}?network={network}",
        "tx_url": f"https://suiexplorer.com/txblock/{object_id}?network={network}",
    }
