import sys
import types

from fastapi import FastAPI
from fastapi.testclient import TestClient


if "pysui" not in sys.modules:
    pysui_module = types.ModuleType("pysui")
    pysui_module.SuiConfig = type("SuiConfig", (), {"user_config": staticmethod(lambda **_k: object())})
    pysui_module.AsyncClient = type("AsyncClient", (), {})
    pysui_module.ObjectID = lambda value: value
    pysui_module.SuiAddress = lambda value: value

    sui_txn_module = types.ModuleType("pysui.sui.sui_txn")
    sui_txn_module.AsyncTransaction = type("AsyncTransaction", (), {})

    scalars_module = types.ModuleType("pysui.sui.sui_types.scalars")
    scalars_module.SuiU64 = int
    scalars_module.SuiU8 = int

    collections_module = types.ModuleType("pysui.sui.sui_types.collections")
    collections_module.SuiArray = list

    sys.modules["pysui"] = pysui_module
    sys.modules["pysui.sui"] = types.ModuleType("pysui.sui")
    sys.modules["pysui.sui.sui_txn"] = sui_txn_module
    sys.modules["pysui.sui.sui_types"] = types.ModuleType("pysui.sui.sui_types")
    sys.modules["pysui.sui.sui_types.scalars"] = scalars_module
    sys.modules["pysui.sui.sui_types.collections"] = collections_module

from app.routers import sui as sui_router


class _FakeRow(dict):
    pass


class _FakeNeo4jSession:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def run(self, *_args, **_kwargs):
        return [
            _FakeRow(
                product_id="P001",
                title="Demo Product",
                brand="Demo",
                rating=45,
                image_url="",
                category="Air Conditioners",
                score=21,
            )
        ]


class _FakeNeo4jDriver:
    def session(self):
        return _FakeNeo4jSession()


class _FakeSuiClient:
    def __init__(self):
        self.network = "testnet"
        self.missing_config = []
        self.default_profile_id = ""
        self.admin_address = "0xabc"
        self.rpc_url = "https://fullnode.testnet.sui.io:443"
        self.simulated = False
        self._profile = None

    def is_configured(self):
        return True

    async def get_pool_stats(self):
        return {
            "balance_raw": 5_000_000,
            "balance_grec": "5.00",
            "tx_count": 2,
        }

    async def get_wallet_assets(self, address: str):
        return {
            "address": address,
            "grec_balance": 100_000_000,
            "grec_formatted": "100.00 GREC",
            "nft_count": 1,
            "nfts": [],
            "recommend_score": None,
            "default_profile_object_id": self._profile,
        }

    async def resolve_profile_object_id(self, _wallet_address: str):
        return self._profile

    async def register_user(self, _user_id: str):
        self._profile = "0xprofile001"
        return {"success": True, "digest": "0xtx_register"}

    async def reward_user(self, **_kwargs):
        return {"success": True, "digest": "0xtx_reward"}

    async def mint_product_nft(self, **_kwargs):
        return {"success": True, "digest": "0xtx_mint"}

    async def update_recommend_score(self, **_kwargs):
        return {"success": True, "digest": "0xtx_score"}

    async def fund_pool(self, _amount_grec: int):
        return {"success": True, "digest": "0xtx_fund"}


def _make_client(monkeypatch):
    fake_client = _FakeSuiClient()
    monkeypatch.setattr(sui_router, "get_sui_client", lambda: fake_client)
    monkeypatch.setattr(sui_router, "neo4j_driver", _FakeNeo4jDriver())

    app = FastAPI()
    app.include_router(sui_router.router, prefix="/sui")
    return TestClient(app), fake_client


def test_status_ok(monkeypatch):
    client, _ = _make_client(monkeypatch)
    res = client.get("/sui/status")
    assert res.status_code == 200
    body = res.json()
    assert body["configured"] is True
    assert body["network"] == "testnet"


def test_fund_pool_validation(monkeypatch):
    client, _ = _make_client(monkeypatch)
    res = client.post("/sui/fund-pool", json={"amount_grec": 0})
    assert res.status_code == 400
    assert "amount_grec" in res.text


def test_reward_invalid_action(monkeypatch):
    client, _ = _make_client(monkeypatch)
    res = client.post(
        "/sui/reward",
        json={
            "recipient_address": "0xabc",
            "profile_object_id": "0xprofile001",
            "product_id": "P001",
            "action": "INVALID",
        },
    )
    assert res.status_code == 400


def test_quick_actions_register_profile(monkeypatch):
    client, _ = _make_client(monkeypatch)
    res = client.get("/sui/quick-actions", params={"address": "0xabc"})
    assert res.status_code == 200
    actions = res.json()["actions"]
    codes = [a["code"] for a in actions]
    assert "REGISTER_PROFILE" in codes
    assert "FUND_POOL" in codes


def test_onboard_user_auto_register(monkeypatch):
    client, fake_client = _make_client(monkeypatch)
    fake_client._profile = None
    res = client.post(
        "/sui/onboard-user",
        json={"user_id": "U0001", "wallet_address": "0xabc", "auto_register": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["success"] is True
    assert body["profile_object_id"] == "0xprofile001"
    assert body["registration"]["digest"] == "0xtx_register"


def test_recommend_with_chain_returns_explorer(monkeypatch):
    client, _ = _make_client(monkeypatch)
    res = client.get(
        "/sui/recommend-with-chain/U0001",
        params={"wallet_address": "0xabc", "limit": 5},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["on_chain"] is True
    assert body["chain_update"]["digest"] == "0xtx_score"
    assert "explorer_link" in body["chain_update"]
