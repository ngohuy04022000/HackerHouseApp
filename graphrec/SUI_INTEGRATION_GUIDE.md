# GraphRec × SUI Blockchain — Hướng dẫn tích hợp đầy đủ

## Tổng quan kiến trúc

```
┌──────────────────────────────────────────────────────────────────────┐
│                    GRAPHREC × SUI ARCHITECTURE                       │
│                                                                      │
│  React Frontend ──── dApp Kit ────────────────────┐                  │
│       ↕                                           ↕                  │
│  FastAPI Backend ── pysui (Python SDK) ───── SUI Testnet            │
│       ↕                                           ↕                  │
│  Neo4j / MySQL ←─── intelligence ────── Move Smart Contract         │
│  Elasticsearch                                                        │
│                                                                      │
│  Flow: Neo4j computes recommendations (off-chain)                   │
│        → FastAPI confirms action                                     │
│        → pysui calls Move contract                                   │
│        → SUI stores proof + distributes GREC token                  │
└──────────────────────────────────────────────────────────────────────┘
```

## Cấu trúc file cần thêm

```
graphrec/
├── contracts/                     # ← MỚI
│   ├── Move.toml
│   └── sources/
│       └── graphrec.move          # Smart contract
├── scripts/                       # ← MỚI
│   └── deploy_sui.sh
├── .env.sui                       # ← Auto-generated sau deploy
├── backend/
│   └── app/
│       ├── sui/                   # ← MỚI
│       │   ├── __init__.py
│       │   └── client.py          # Python SUI client
│       ├── routers/
│       │   └── sui.py             # ← MỚI: API endpoints
│       └── main.py                # ← EDIT: thêm router
└── frontend/
    └── src/
        ├── App.jsx                # ← EDIT: thêm SUI tab
        └── components/sui/       # ← MỚI
            └── SuiPanel.jsx
```

---

## BƯỚC 1 — Cài đặt SUI CLI

```bash
# Option A: Cargo (recommended)
curl https://sh.rustup.rs -sSf | sh
cargo install --locked --git https://github.com/MystenLabs/sui.git sui --branch testnet

# Option B: Homebrew (Mac)
brew install sui

# Kiểm tra
sui --version   # sui 1.26.x
```

---

## BƯỚC 2 — Tạo ví và nhận SUI testnet

```bash
# Tạo ví mới (hoặc import từ private key có sẵn)
sui client new-address secp256k1

# Xem địa chỉ
sui client active-address

# Nhận SUI từ faucet testnet
sui client faucet

# Kiểm tra balance
sui client balance
# → phải có ít nhất 0.1 SUI để deploy + gas
```

---

## BƯỚC 3 — Deploy Smart Contract

### Cách A: Script tự động (khuyến nghị)

```bash
cd graphrec
chmod +x scripts/deploy_sui.sh
./scripts/deploy_sui.sh
# → Tự động: build, deploy, parse IDs, tạo .env.sui, fund pool
```

### Cách B: Thủ công

```bash
cd contracts

# Build
sui move build

# Deploy lên testnet
sui client publish --gas-budget 150000000

# Từ output, lấy các IDs:
# - Published Objects → packageId    → SUI_PACKAGE_ID
# - Created Objects:
#     RewardPool object               → SUI_POOL_ID
#     Registry object                 → SUI_REGISTRY_ID
#     AdminCap object                 → SUI_ADMIN_CAP_ID
#     TreasuryCap<GRAPHREC> object    → SUI_TREASURY_ID
```

### Kiểm tra trên Explorer

```
https://suiexplorer.com/object/{SUI_PACKAGE_ID}?network=testnet
```
$SUI_PACKAGE_ID = "0xa388013751d3e3aada7864735d699549fa16d170742802afda4ef8dc7ad9cd4a"
$SUI_ADMIN_CAP_ID = "0xe378e24ae737cfe758f5ca66f4b50d58dabdbca157acdb0375d9f6a2ec79a767"
$SUI_TREASURY_ID = "0x72c1a06e8cca9994f6a067d7fa72ff061eae9b1edbe121e3f79d33e13f619709"
$SUI_POOL_ID = "0xb9bf726d557dd6e31934b78a8d912ddca718827016703a06472793df28de0a4a"
---

## BƯỚC 4 — Nạp GREC vào RewardPool

```bash
# Mint 100,000 GREC vào pool (100000 * 1_000_000 = 100_000_000_000 raw units)
sui client call \
  --package $SUI_PACKAGE_ID \
  --module graphrec \
  --function fund_pool \
  --args $SUI_ADMIN_CAP_ID $SUI_TREASURY_ID $SUI_POOL_ID 100000000000 \
  --gas-budget 10000000

# Hoặc qua API sau khi backend chạy:
curl -X POST http://localhost:8000/sui/fund-pool \
  -H "Content-Type: application/json" \
  -d '{"amount_grec": 100000}'
```

---

## BƯỚC 5 — Cài dependencies Python backend

```bash
# Thêm vào backend/requirements.txt:
pysui==0.50.0

# Cài
pip install pysui==0.50.0
# hoặc trong Docker: tự động khi rebuild
```

---

## BƯỚC 6 — Cấu hình environment variables

```bash
# Thêm vào backend/.env (hoặc docker-compose.yml):
SUI_NETWORK=testnet
SUI_PRIVATE_KEY=suiprivkey...   # từ: sui keytool list
SUI_PACKAGE_ID=0x...
SUI_POOL_ID=0x...
SUI_REGISTRY_ID=0x...
SUI_ADMIN_CAP_ID=0x...
SUI_TREASURY_ID=0x...
SUI_PROFILE_ID=0x...    # optional fallback cho /sui/reward
SUI_CLOCK_ID=0x0000000000000000000000000000000000000000000000000000000000000006
```

### Lấy private key từ keystore:

```bash
# Xem danh sách keys
sui keytool list

# Export private key (dạng suiprivkey...)
sui keytool export --key-identity <address>
```

---

## BƯỚC 7 — Cập nhật backend/app/main.py

Thêm SUI router vào FastAPI:

```python
# Thêm import
from app.routers import sui as sui_router

# Trong app setup, thêm:
app.include_router(sui_router.router, prefix="/sui", tags=["SUI Blockchain"])
```

---

## BƯỚC 8 — Cài dependencies Frontend

```bash
cd frontend

# Core SUI packages
npm install @mysten/sui.js @mysten/dapp-kit @tanstack/react-query

# Providers cần thêm vào main.jsx (tùy chọn, dùng khi muốn wallet connect đầy đủ):
# import { SuiClientProvider, WalletProvider } from "@mysten/dapp-kit";
# import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
# import { getFullnodeUrl } from "@mysten/sui.js/client";
```

---

## BƯỚC 9 — Cập nhật frontend/src/App.jsx

Thêm tab SUI:

```jsx
// Thêm import
import SuiPanel from "./components/sui/SuiPanel";

// Thêm vào TABS array:
{ id: "sui", label: "SUI Blockchain" }

// Thêm vào render:
{tab === "sui" && <SuiPanel userId={userId} />}
```

---

## BƯỚC 10 — Rebuild và kiểm tra

```bash
# Docker
docker compose down
docker compose up --build

# Hoặc local
# Backend: uvicorn app.main:app --reload
# Frontend: npm run dev

# Kiểm tra SUI integration
curl http://localhost:8000/sui/status

# Expected output:
# {
#   "configured": true,
#   "network": "testnet",
#   "package_id": "0x...",
#   "pool_stats": { "balance_grec": "100000.00", ... }
# }
```

---

## API Endpoints SUI

| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/sui/status` | Kiểm tra kết nối + pool stats |
| GET | `/sui/pool-stats` | GREC pool balance và thống kê |
| GET | `/sui/wallet/{address}` | Tài sản ví: GREC + NFTs + score |
| GET | `/sui/quick-actions?address=0x...` | Gợi ý bước tiếp theo theo trạng thái ví/pool |
| POST | `/sui/reward` | Phát GREC token |
| POST | `/sui/mint-nft` | Đúc Product NFT |
| POST | `/sui/update-score` | Cập nhật score on-chain |
| POST | `/sui/onboard-user` | Onboarding nhanh: kiểm tra ví + auto register profile |
| POST | `/sui/fund-pool` | Nạp GREC vào pool |
| GET | `/sui/recommend-with-chain/{uid}` | Neo4j + on-chain update |
| GET | `/sui/explorer/{id}` | Link SUI Explorer |

### Quy ước mã lỗi mới (đã chuẩn hóa)

- `400 Bad Request`: request sai dữ liệu đầu vào (validation).
- `502 Bad Gateway`: giao dịch on-chain lỗi ở runtime hoặc bị chain từ chối.
- `200 OK`: request hợp lệ và giao dịch xử lý thành công.

Ví dụ thực tế:

```bash
# 400: fund-pool amount <= 0
curl -i -X POST http://localhost:8000/sui/fund-pool \
  -H "Content-Type: application/json" \
  -d '{"amount_grec": 0}'

# 502: reward dùng profile_object_id không hợp lệ
curl -i -X POST http://localhost:8000/sui/reward \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_address": "0x<YOUR_WALLET>",
    "profile_object_id": "0x1",
    "product_id": "P0001",
    "action": "VIEWED"
  }'
```

---

## Test nhanh từng chức năng

```bash
# 1. Status
curl http://localhost:8000/sui/status | python3 -m json.tool

# 2. Phát GREC cho user
curl -X POST http://localhost:8000/sui/reward \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_address": "0x<YOUR_WALLET>",
    "profile_object_id": "0x<USER_PROFILE_OBJECT_ID>",
    "product_id": "P0001",
    "action": "BOUGHT"
  }'

# 3. Mint NFT
curl -X POST http://localhost:8000/sui/mint-nft \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_address": "0x<YOUR_WALLET>",
    "product_id": "P0001",
    "name": "LG 1.5 Ton Inverter AC",
    "brand": "LG",
    "category": "Air Conditioners",
    "price_grec": 100000000,
    "rating": 42
  }'

# 4. Gợi ý + lưu on-chain
curl "http://localhost:8000/sui/recommend-with-chain/U0001?wallet_address=0x<YOUR_WALLET>"

# 5. Xem tài sản ví
curl http://localhost:8000/sui/wallet/0x<YOUR_WALLET> | python3 -m json.tool

# 5.1. Gợi ý thao tác tiếp theo theo trạng thái ví/pool
curl "http://localhost:8000/sui/quick-actions?address=0x<YOUR_WALLET>" | python3 -m json.tool

# 5.2. Onboarding nhanh (auto register profile nếu cần)
curl -X POST http://localhost:8000/sui/onboard-user \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "U0001",
    "wallet_address": "0x<YOUR_WALLET>",
    "auto_register": true
  }'

# 6. Test lỗi 400: action không hợp lệ
curl -i -X POST http://localhost:8000/sui/reward \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_address": "0x<YOUR_WALLET>",
    "profile_object_id": "0x<USER_PROFILE_OBJECT_ID>",
    "product_id": "P0001",
    "action": "INVALID"
  }'

# 7. Test lỗi 400: top_products và scores lệch độ dài
curl -i -X POST http://localhost:8000/sui/update-score \
  -H "Content-Type: application/json" \
  -d '{
    "owner_address": "0x<YOUR_WALLET>",
    "top_products": ["P1", "P2"],
    "scores": [10]
  }'

# 8. Test lỗi 502: profile object sai (chain reject)
curl -i -X POST http://localhost:8000/sui/reward \
  -H "Content-Type: application/json" \
  -d '{
    "recipient_address": "0x<YOUR_WALLET>",
    "profile_object_id": "0x1",
    "product_id": "P0001",
    "action": "VIEWED"
  }'
```

### Ví dụ response chuẩn

```json
{
  "success": true,
  "digest": "<TX_DIGEST>",
  "error": null,
  "funded_grec": 2,
  "funded_raw": 2000000
}
```

```json
{
  "detail": "amount_grec phải > 0"
}
```

```json
{
  "detail": "Error checking transaction input objects: A move object is expected, instead a move package is passed: 0x000...001"
}
```

---

## Test API trên Windows PowerShell

PowerShell có alias `curl` khác với curl Linux/Mac, nên nên dùng `Invoke-RestMethod`:

```powershell
# Status
Invoke-RestMethod -Uri "http://localhost:8000/sui/status" -Method Get

# Fund pool
Invoke-RestMethod -Uri "http://localhost:8000/sui/fund-pool" -Method Post -ContentType "application/json" -Body '{"amount_grec": 100000}'

# Onboard user
Invoke-RestMethod -Uri "http://localhost:8000/sui/onboard-user" -Method Post -ContentType "application/json" -Body '{"user_id":"U0001","wallet_address":"0x<YOUR_WALLET>","auto_register":true}'
```

---

## docker-compose.yml — thêm SUI env vars

```yaml
backend:
  environment:
    # ... các env hiện tại ...
    SUI_NETWORK:      testnet
    SUI_PRIVATE_KEY:  ${SUI_PRIVATE_KEY}      # từ .env file
    SUI_PACKAGE_ID:   ${SUI_PACKAGE_ID}
    SUI_POOL_ID:      ${SUI_POOL_ID}
    SUI_REGISTRY_ID:  ${SUI_REGISTRY_ID}
    SUI_ADMIN_CAP_ID: ${SUI_ADMIN_CAP_ID}
    SUI_TREASURY_ID:  ${SUI_TREASURY_ID}
    SUI_PROFILE_ID:   ${SUI_PROFILE_ID}
    SUI_CLOCK_ID:     "0x0000000000000000000000000000000000000000000000000000000000000006"
```

---

## Lưu ý bảo mật quan trọng

**KHÔNG bao giờ commit private key vào git!**

```bash
# .gitignore
.env
.env.*
*.key
```

Trong production:
- Dùng AWS Secrets Manager / HashiCorp Vault để quản lý private key
- Backend là "hot wallet" admin — cần bảo vệ nghiêm ngặt
- Cân nhắc dùng multi-sig cho các operation quan trọng

---

## Troubleshooting

### "SUI not configured" trong /sui/status
→ Kiểm tra env vars trong docker-compose.yml hoặc .env

### "Thiếu profile_object_id" khi gọi /sui/reward
→ Tạo UserProfile trước bằng API:

```bash
curl -X POST http://localhost:8000/sui/register-user \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "U0001",
    "wallet_address": "0x<ADMIN_WALLET>"
  }'
```

→ Sau đó gọi `/sui/wallet/{address}` để lấy `default_profile_object_id` hoặc gửi trực tiếp `profile_object_id` khi reward.
→ Lưu ý: trong cấu hình hiện tại, `register-user` dùng sender từ private key backend, nên `wallet_address` phải trùng `admin_address` của backend.

### "Insufficient gas" khi deploy
→ Chạy `sui client faucet` để nhận thêm SUI testnet

### pysui import error
→ `pip install pysui==0.50.0 --force-reinstall`

### Move build failed
→ Kiểm tra `sui --version` phải là testnet build
→ Xóa `contracts/build/` và build lại

### NFT không xuất hiện trong wallet
→ Đợi 5-10 giây (SUI checkpoint finality)
→ Refresh trang hoặc gọi lại `/sui/wallet/{address}`

### Endpoint trả 502
→ Kiểm tra object IDs truyền vào request (`profile_object_id`, `pool_id`, `admin_cap_id`, `treasury_id`)
→ Kiểm tra object còn tồn tại trên SUI Explorer và đúng type của Move contract
→ Kiểm tra log backend để xem chain reject message chi tiết
