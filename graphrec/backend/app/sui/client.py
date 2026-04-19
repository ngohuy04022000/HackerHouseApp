"""
app/sui/client.py
=================
Client Python tương tác với SUI blockchain thông qua pysui.
"""

import os
import logging
import base64
from typing import Optional, Any

from pysui import SuiConfig, AsyncClient, ObjectID, SuiAddress
from pysui.sui.sui_txn import AsyncTransaction
from pysui.sui.sui_types.scalars import SuiU64, SuiU8
from pysui.sui.sui_types.collections import SuiArray

logger = logging.getLogger(__name__)

NETWORK_URLS = {
    "testnet": "https://fullnode.testnet.sui.io:443",
    "devnet":  "https://fullnode.devnet.sui.io:443",
    "mainnet": "https://fullnode.mainnet.sui.io:443",
}

CLOCK_OBJECT_ID = "0x0000000000000000000000000000000000000000000000000000000000000006"

_client: Optional["SuiBlockchainClient"] = None


def _normalize_private_key(key: str) -> str:
    """Chuyển đổi private key từ hex hoặc suiprivkey sang base64 44 ký tự."""
    key = key.strip()
    if key.startswith("0x"):
        key_bytes = bytes.fromhex(key[2:])
        combined = b"\x00" + key_bytes
        return base64.b64encode(combined).decode("ascii")
    if key.startswith("suiprivkey"):
        b64_part = key[11:]
        padding = 4 - (len(b64_part) % 4)
        if padding != 4:
            b64_part += "=" * padding
        decoded = base64.b64decode(b64_part)
        return base64.b64encode(decoded).decode("ascii")
    return key


def get_sui_client() -> "SuiBlockchainClient":
    global _client
    if _client is None:
        _client = SuiBlockchainClient()
    return _client


class SuiBlockchainClient:
    def __init__(self):
        network = os.getenv("SUI_NETWORK", "testnet")
        self.network = network
        private_key_raw = os.getenv("SUI_PRIVATE_KEY", "")

        self.package_id   = os.getenv("SUI_PACKAGE_ID", "")
        self.pool_id      = os.getenv("SUI_POOL_ID", "")
        self.registry_id  = os.getenv("SUI_REGISTRY_ID", "")
        self.admin_cap_id = os.getenv("SUI_ADMIN_CAP_ID", "")
        self.treasury_id  = os.getenv("SUI_TREASURY_ID", "")
        self.default_profile_id = os.getenv("SUI_PROFILE_ID", "")
        self.rpc_url      = NETWORK_URLS.get(network, NETWORK_URLS["testnet"])
        self.missing_config = [
            key for key, value in {
                "SUI_PRIVATE_KEY": private_key_raw,
                "SUI_PACKAGE_ID": self.package_id,
                "SUI_POOL_ID": self.pool_id,
                "SUI_ADMIN_CAP_ID": self.admin_cap_id,
            }.items()
            if not value
        ]

        self._configured = len(self.missing_config) == 0
        self.simulated = False
        self.client = None
        self.admin_address = os.getenv("SUI_ADMIN_ADDRESS", "0xd644df0c8b70f758e6b14e0b51bf13855a2b2fafa5b7ea3804bb662bb3710c5e")

        if self._configured:
            try:
                private_key = _normalize_private_key(private_key_raw)
                self.cfg = SuiConfig.user_config(
                    rpc_url=self.rpc_url,
                    prv_keys=[private_key],
                )
                self.client = AsyncClient(self.cfg)
                self.admin_address = self.cfg.active_address.address
                logger.info(f"[SUI] Client configured for {network} — admin: {self.admin_address}")
                # Thử kết nối thực tế bằng cách gọi một API đơn giản (sẽ thực hiện ở lần gọi đầu tiên)
            except Exception as e:
                logger.warning(f"[SUI] Init failed, falling back to simulated mode: {e}")
                self._configured = False
                self.simulated = True
                self.client = None
        else:
            logger.warning(f"[SUI] Not configured — missing {', '.join(self.missing_config)}")
            self._configured = False
            self.simulated = True

    def is_configured(self) -> bool:
        return self._configured and not self.simulated and self.client is not None

    @staticmethod
    def _to_u8_bytes(value: str) -> SuiArray:
        return SuiArray([SuiU8(b) for b in value.encode()])

    @staticmethod
    def _as_address(value: str) -> SuiAddress:
        return SuiAddress(value)

    @staticmethod
    def _as_object_id(value: str) -> ObjectID:
        return ObjectID(value)

    @staticmethod
    def _maybe_get(source: Any, key: str, default: Any = None) -> Any:
        if isinstance(source, dict):
            return source.get(key, default)
        return getattr(source, key, default)

    def _extract_digest(self, result_data: Any) -> Optional[str]:
        digest = self._maybe_get(result_data, "digest")
        if digest:
            return str(digest)

        effects = self._maybe_get(result_data, "effects")
        tx_digest = self._maybe_get(effects, "transactionDigest")
        if tx_digest:
            return str(tx_digest)

        if isinstance(result_data, dict):
            for key in ("digest", "transactionDigest", "txDigest"):
                if key in result_data:
                    return str(result_data[key])
        return None

    @staticmethod
    def _to_int(value: Any, default: int = 0) -> int:
        if value is None:
            return default
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return default
        if isinstance(value, dict):
            if "value" in value:
                return SuiBlockchainClient._to_int(value.get("value"), default)
            if "fields" in value:
                return SuiBlockchainClient._to_int(value.get("fields"), default)
        inner_value = getattr(value, "value", None)
        if inner_value is not None and inner_value is not value:
            return SuiBlockchainClient._to_int(inner_value, default)
        inner_fields = getattr(value, "fields", None)
        if inner_fields is not None and inner_fields is not value:
            return SuiBlockchainClient._to_int(inner_fields, default)
        return default

    @staticmethod
    def _normalize_fields(fields: Any) -> dict:
        if isinstance(fields, dict):
            return fields
        if hasattr(fields, "__dict__"):
            return vars(fields)
        return {}

    @classmethod
    def _find_pool_fields(cls, payload: Any) -> dict:
        """Recursively find the dict that contains RewardPool numeric fields."""
        visited = set()

        def _walk(node: Any) -> Optional[dict]:
            node_id = id(node)
            if node_id in visited:
                return None
            visited.add(node_id)

            if isinstance(node, dict):
                if any(k in node for k in ("balance", "total_distributed", "tx_count")):
                    return node
                for value in node.values():
                    found = _walk(value)
                    if found:
                        return found
                return None

            if isinstance(node, (list, tuple, set)):
                for item in node:
                    found = _walk(item)
                    if found:
                        return found
                return None

            if hasattr(node, "__dict__"):
                return _walk(vars(node))

            return None

        return _walk(payload) or {}

    async def _ensure_client_ready(self):
        """Kiểm tra kết nối thực tế lần đầu và fallback nếu lỗi."""
        if self.simulated or not self.client:
            return
        try:
            # Gọi một API đơn giản để kiểm tra kết nối
            res = await self.client.get_object(self._as_object_id(self.pool_id))
            if not res.is_ok():
                raise Exception("Pool object not accessible")
        except Exception as e:
            logger.warning(f"[SUI] Real connection failed, switching to simulated: {e}")
            self.simulated = True
            self.client = None

    async def _execute_tx(self, txb: AsyncTransaction) -> dict:
        try:
            result = await txb.execute(gas_budget="10000000")
            if result.is_ok():
                digest = self._extract_digest(result.result_data)
                logger.info(f"[SUI] TX success: {digest}")
                return {"success": True, "digest": digest, "error": None}
            else:
                err = str(result.result_string)
                logger.error(f"[SUI] TX failed: {err}")
                return {"success": False, "digest": None, "error": err}
        except Exception as e:
            logger.exception(f"[SUI] TX exception: {e}")
            return {"success": False, "digest": None, "error": str(e)}

    # ── Public functions ──────────────────────────────────────────────────────

    async def reward_user(
        self,
        recipient_address: str,
        profile_object_id: str,
        product_id: str,
        action: str,
    ) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "success": True,
                "simulated": True,
                "digest": f"simulated_tx_{product_id}_{action}",
                "amount": {"VIEWED": 10, "BOUGHT": 100, "REVIEWED": 50}.get(action, 10),
                "recipient": recipient_address,
                "action": action,
                "product_id": product_id,
            }
        if not profile_object_id:
            raise ValueError("profile_object_id is required for on-chain reward_user")

        txb = AsyncTransaction(client=self.client)
        await txb.move_call(
            target=f"{self.package_id}::graphrec::reward_user",
            arguments=[
                self._as_object_id(self.admin_cap_id),
                self._as_object_id(self.pool_id),
                self._as_object_id(profile_object_id),
                self._as_address(recipient_address),
                self._to_u8_bytes(product_id),
                self._to_u8_bytes(action),
                self._as_object_id(CLOCK_OBJECT_ID),
            ],
        )
        result = await self._execute_tx(txb)
        result["action"] = action
        result["product_id"] = product_id
        result["recipient"] = recipient_address
        return result

    async def register_user(self, user_id: str) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "success": True,
                "simulated": True,
                "digest": f"simulated_register_{user_id}",
                "user_id": user_id,
            }

        txb = AsyncTransaction(client=self.client)
        await txb.move_call(
            target=f"{self.package_id}::graphrec::register_user",
            arguments=[
                self._as_object_id(self.registry_id),
                self._to_u8_bytes(user_id),
                self._as_object_id(CLOCK_OBJECT_ID),
            ],
        )
        result = await self._execute_tx(txb)
        result["user_id"] = user_id
        return result

    async def mint_product_nft(
        self,
        recipient_address: str,
        product_id: str,
        name: str,
        description: str,
        image_url: str,
        brand: str,
        category: str,
        price_grec: int,
        rating: int,
    ) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "success": True,
                "simulated": True,
                "nft_id": f"simulated_nft_{product_id}",
                "product_id": product_id,
                "recipient": recipient_address,
                "message": "Simulated NFT mint successful",
            }

        def to_bytes(s: str):
            return SuiArray([SuiU8(b) for b in s.encode()])

        txb = AsyncTransaction(client=self.client)
        await txb.move_call(
            target=f"{self.package_id}::graphrec::mint_product_nft",
            arguments=[
                self._as_object_id(self.admin_cap_id),
                self._as_object_id(self.registry_id),
                self._as_address(recipient_address),
                to_bytes(product_id),
                to_bytes(name[:64]),
                to_bytes(description[:128]),
                to_bytes(image_url[:256]),
                to_bytes(brand[:32]),
                to_bytes(category[:64]),
                SuiU64(price_grec),
                SuiU8(min(rating, 50)),
                self._as_object_id(CLOCK_OBJECT_ID),
            ],
        )
        result = await self._execute_tx(txb)
        result["product_id"] = product_id
        result["recipient"] = recipient_address
        return result

    async def update_recommend_score(
        self,
        owner_address: str,
        top_products: list[str],
        scores: list[int],
    ) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "success": True,
                "simulated": True,
                "owner": owner_address,
                "top_products": top_products[:5],
                "scores": scores[:5],
            }

        def to_bytes_array(lst: list[str]):
            return [list(s.encode()) for s in lst[:5]]

        txb = AsyncTransaction(client=self.client)
        await txb.move_call(
            target=f"{self.package_id}::graphrec::update_recommend_score",
            arguments=[
                self._as_object_id(self.admin_cap_id),
                self._as_address(owner_address),
                to_bytes_array(top_products),
                [int(s) for s in scores[:5]],
                self._as_object_id(CLOCK_OBJECT_ID),
            ],
        )
        result = await self._execute_tx(txb)
        result["owner"] = owner_address
        return result

    async def fund_pool(self, amount_grec: int) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "success": True,
                "simulated": True,
                "funded_grec": amount_grec,
            }

        txb = AsyncTransaction(client=self.client)
        await txb.move_call(
            target=f"{self.package_id}::graphrec::fund_pool",
            arguments=[
                self._as_object_id(self.admin_cap_id),
                self._as_object_id(self.treasury_id),
                self._as_object_id(self.pool_id),
                SuiU64(amount_grec),
            ],
        )
        return await self._execute_tx(txb)

    # ── Read functions ────────────────────────────────────────────────────────

    async def get_wallet_assets(self, address: str) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return self._mock_wallet_assets(address)

        try:
            grec_type = f"{self.package_id}::grec::GREC"
            coins_res = await self.client.get_coin(
                coin_type=grec_type,
                address=self._as_address(address),
                fetch_all=True,
            )
            grec_balance = 0
            if coins_res.is_ok() and coins_res.result_data:
                for coin in (self._maybe_get(coins_res.result_data, "data", []) or []):
                    grec_balance += self._to_int(self._maybe_get(coin, "balance", 0))

            owned_res = await self.client.get_objects(
                address=self._as_address(address),
                fetch_all=True,
            )
            nfts = []
            score_candidates = []
            user_profiles = []
            owned_objects = []
            if owned_res.is_ok() and owned_res.result_data:
                owned_objects = self._maybe_get(owned_res.result_data, "data", []) or []
            for obj in owned_objects:
                obj_type = str(self._maybe_get(obj, "object_type", "") or "")
                content = self._maybe_get(obj, "content", None)
                fields = self._normalize_fields(self._maybe_get(content, "fields", {}))
                if obj_type.endswith("::ProductNFT"):
                    image_field = fields.get("image_url")
                    image_url = (
                        image_field.get("url")
                        if isinstance(image_field, dict)
                        else self._maybe_get(image_field, "url", image_field)
                    )
                    nfts.append({
                        "object_id":  self._maybe_get(obj, "object_id"),
                        "product_id": fields.get("product_id"),
                        "name":       fields.get("name"),
                        "brand":      fields.get("brand"),
                        "category":   fields.get("category"),
                        "rating":     fields.get("rating"),
                        "serial":     fields.get("serial"),
                        "image_url":  image_url,
                        "minted_at":  fields.get("minted_at"),
                    })
                elif obj_type.endswith("::RecommendScore"):
                    score_candidates.append((obj, fields))
                elif obj_type.endswith("::UserProfile"):
                    user_profiles.append({
                        "object_id": self._maybe_get(obj, "object_id"),
                        "user_id": fields.get("user_id"),
                        "wallet": fields.get("wallet"),
                        "viewed_count": self._to_int(fields.get("viewed_count"), 0),
                        "bought_count": self._to_int(fields.get("bought_count"), 0),
                        "review_count": self._to_int(fields.get("review_count"), 0),
                        "total_earned": self._to_int(fields.get("total_earned"), 0),
                    })

            recommend_score = None
            if score_candidates:
                obj, fields = score_candidates[0]
                recommend_score = {
                    "object_id":   self._maybe_get(obj, "object_id"),
                    "top_products": fields.get("top_products", []),
                    "scores":       fields.get("scores", []),
                    "version":      fields.get("version"),
                    "updated_at":   fields.get("updated_at"),
                }

            return {
                "address":         address,
                "grec_balance":    grec_balance,
                "grec_formatted":  f"{grec_balance / 1_000_000:.2f} GREC",
                "nfts":            nfts,
                "nft_count":       len(nfts),
                "user_profiles":   user_profiles,
                "default_profile_object_id": user_profiles[0]["object_id"] if user_profiles else None,
                "recommend_score": recommend_score,
                "network":         self.network,
                "explorer_url":    f"https://suiexplorer.com/address/{address}?network={self.network}",
            }
        except Exception as e:
            logger.error(f"[SUI] get_wallet_assets error: {e}")
            return self._mock_wallet_assets(address)

    async def resolve_profile_object_id(self, wallet_address: str) -> Optional[str]:
        """Find first UserProfile object owned by wallet_address."""
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return None

        try:
            owned_res = await self.client.get_objects(
                address=self._as_address(wallet_address),
                fetch_all=True,
            )
            if not owned_res.is_ok() or not owned_res.result_data:
                return None

            owned_objects = self._maybe_get(owned_res.result_data, "data", []) or []
            for obj in owned_objects:
                obj_type = str(self._maybe_get(obj, "object_type", "") or "")
                if obj_type.endswith("::UserProfile"):
                    object_id = self._maybe_get(obj, "object_id")
                    if object_id:
                        return str(object_id)
            return None
        except Exception:
            return None

    async def get_pool_stats(self) -> dict:
        await self._ensure_client_ready()
        if self.simulated or not self.client:
            return {
                "configured": self.is_configured(),
                "pool_id": self.pool_id,
                "balance_raw": 100_000_000_000,
                "balance_grec": "100000.00",
                "total_distributed_raw": 0,
                "total_distributed_grec": "0.00",
                "tx_count": 0,
                "network": self.network,
                "simulated": True,
            }

        try:
            res = await self.client.get_object(self._as_object_id(self.pool_id))
            if res.is_ok():
                fields = self._find_pool_fields(res.result_data)
                bal = self._to_int(fields.get("balance"), 0)
                dist = self._to_int(fields.get("total_distributed"), 0)
                txc = self._to_int(fields.get("tx_count"), 0)
                return {
                    "configured":             self.is_configured(),
                    "pool_id":                self.pool_id,
                    "balance_raw":            bal,
                    "balance_grec":           f"{bal / 1_000_000:.2f}",
                    "total_distributed_raw":  dist,
                    "total_distributed_grec": f"{dist / 1_000_000:.2f}",
                    "tx_count":               txc,
                    "network":                self.network,
                }
            return {
                "configured": self.is_configured(),
                "pool_id": self.pool_id,
                "balance_grec": "0.00",
                "error": str(res.result_string),
            }
        except Exception as e:
            logger.error(f"[SUI] get_pool_stats error: {e}")
            return {
                "configured": self.is_configured(),
                "pool_id": self.pool_id,
                "balance_grec": "0.00",
                "error": str(e),
            }

    def _mock_wallet_assets(self, address: str) -> dict:
        return {
            "address":          address,
            "grec_balance":     1_500_000_000,
            "grec_formatted":   "1500.00 GREC (simulated)",
            "nft_count":        3,
            "user_profiles": [
                {
                    "object_id": "0xsimulated_profile_001",
                    "user_id": "U0001",
                    "wallet": address,
                    "viewed_count": 12,
                    "bought_count": 3,
                    "review_count": 2,
                    "total_earned": 420000000,
                }
            ],
            "default_profile_object_id": "0xsimulated_profile_001",
            "nfts": [
                {"product_id": "P001", "name": "LG 1.5 Ton Inverter AC", "brand": "LG",
                 "category": "Air Conditioners", "rating": 42, "serial": 7,
                 "image_url": "https://m.media-amazon.com/images/I/51JFb7FctDL._AC_UL320_.jpg",
                 "minted_at": 1714000000000},
                {"product_id": "P002", "name": "Samsung Split AC 2 Ton", "brand": "Samsung",
                 "category": "Air Conditioners", "rating": 44, "serial": 15,
                 "image_url": None, "minted_at": 1714100000000},
                {"product_id": "P003", "name": "Daikin 1 Ton 5 Star", "brand": "Daikin",
                 "category": "Air Conditioners", "rating": 46, "serial": 23,
                 "image_url": None, "minted_at": 1714200000000},
            ],
            "recommend_score": {
                "top_products": ["P010", "P023", "P047"],
                "scores":       [42, 35, 28],
                "version":      3,
                "updated_at":   1714300000000,
            },
            "network":          f"{self.network} (simulated)",
            "explorer_url":     f"https://suiexplorer.com/address/{address}?network={self.network}",
            "simulated":        True,
        }
