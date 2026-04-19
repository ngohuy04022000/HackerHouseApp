#!/usr/bin/env bash
# =============================================================================
# GraphRec × SUI — Deploy Script
# Chạy: chmod +x scripts/deploy_sui.sh && ./scripts/deploy_sui.sh
# =============================================================================
set -e
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()    { echo -e "${CYAN}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $1"; }
error()   { echo -e "${RED}[ERR]${NC} $1"; exit 1; }

echo ""
echo "============================================================"
echo "  GraphRec × SUI Blockchain — Deploy"
echo "============================================================"
echo ""

# ── 1. Kiểm tra SUI CLI ──────────────────────────────────────────────────────
info "Kiểm tra SUI CLI..."
if ! command -v sui &>/dev/null; then
  warn "SUI CLI chưa được cài. Đang cài từ cargo..."
  if ! command -v cargo &>/dev/null; then
    error "Cần Rust/Cargo. Cài tại: https://rustup.rs/"
  fi
  cargo install --locked --git https://github.com/MystenLabs/sui.git sui --branch testnet
fi
SUI_VERSION=$(sui --version 2>/dev/null || echo "unknown")
success "SUI CLI: $SUI_VERSION"

# ── 2. Cấu hình network ──────────────────────────────────────────────────────
NETWORK="${SUI_NETWORK:-testnet}"
info "Network: $NETWORK"

sui client switch --env $NETWORK 2>/dev/null || {
  info "Tạo env $NETWORK..."
  case "$NETWORK" in
    testnet) RPC="https://fullnode.testnet.sui.io:443" ;;
    devnet)  RPC="https://fullnode.devnet.sui.io:443"  ;;
    mainnet) RPC="https://fullnode.mainnet.sui.io:443" ;;
    *) error "Network không hợp lệ: $NETWORK" ;;
  esac
  sui client new-env --alias $NETWORK --rpc $RPC
  sui client switch --env $NETWORK
}

# ── 3. Kiểm tra ví và SUI balance ────────────────────────────────────────────
info "Kiểm tra ví..."
ACTIVE_ADDRESS=$(sui client active-address 2>/dev/null)
if [ -z "$ACTIVE_ADDRESS" ]; then
  warn "Chưa có ví. Tạo ví mới..."
  sui client new-address secp256k1
  ACTIVE_ADDRESS=$(sui client active-address)
fi
success "Địa chỉ admin: $ACTIVE_ADDRESS"

# Kiểm tra balance trên testnet
if [ "$NETWORK" = "testnet" ] || [ "$NETWORK" = "devnet" ]; then
  info "Nhận SUI từ faucet (testnet)..."
  sui client faucet --address $ACTIVE_ADDRESS || warn "Faucet thất bại, có thể đã có SUI"
  sleep 3
fi

BALANCE=$(sui client balance --json 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    total = sum(int(c.get('totalBalance', 0)) for c in data)
    print(total)
except:
    print(0)
" 2>/dev/null || echo "0")
info "SUI Balance: $BALANCE MIST"

if [ "$BALANCE" -lt 50000000 ] 2>/dev/null; then
  warn "Balance thấp (<0.05 SUI). Có thể thiếu gas."
  warn "Truy cập: https://faucet.testnet.sui.io/ để nhận SUI"
fi

# ── 4. Build & Deploy contract ────────────────────────────────────────────────
CONTRACTS_DIR="$(dirname "$0")/../contracts"
if [ ! -f "$CONTRACTS_DIR/Move.toml" ]; then
  error "Không tìm thấy $CONTRACTS_DIR/Move.toml"
fi

info "Build Move contract..."
cd "$CONTRACTS_DIR"
sui move build --skip-fetch-latest-git-deps 2>&1 | tail -5

info "Deploy lên $NETWORK..."
DEPLOY_OUTPUT=$(sui client publish \
  --gas-budget 150000000 \
  --skip-fetch-latest-git-deps \
  --json 2>&1)

if echo "$DEPLOY_OUTPUT" | grep -q '"status":"success"'; then
  success "Deploy thành công!"
else
  echo "$DEPLOY_OUTPUT" | tail -20
  error "Deploy thất bại. Xem log trên."
fi

# ── 5. Parse output để lấy Object IDs ────────────────────────────────────────
info "Trích xuất Object IDs..."

PACKAGE_ID=$(echo "$DEPLOY_OUTPUT" | python3 -c "
import sys, json, re
data = json.load(sys.stdin)
for effect in data.get('objectChanges', []):
    if effect.get('type') == 'published':
        print(effect['packageId'])
        break
" 2>/dev/null)

POOL_ID=$(echo "$DEPLOY_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for effect in data.get('objectChanges', []):
    if effect.get('type') == 'created':
        t = effect.get('objectType', '')
        if 'RewardPool' in t:
            print(effect['objectId'])
            break
" 2>/dev/null)

REGISTRY_ID=$(echo "$DEPLOY_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for effect in data.get('objectChanges', []):
    if effect.get('type') == 'created':
        t = effect.get('objectType', '')
        if 'Registry' in t:
            print(effect['objectId'])
            break
" 2>/dev/null)

ADMIN_CAP_ID=$(echo "$DEPLOY_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for effect in data.get('objectChanges', []):
    if effect.get('type') == 'created':
        t = effect.get('objectType', '')
        if 'AdminCap' in t:
            print(effect['objectId'])
            break
" 2>/dev/null)

TREASURY_ID=$(echo "$DEPLOY_OUTPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for effect in data.get('objectChanges', []):
    if effect.get('type') == 'created':
        t = effect.get('objectType', '')
        if 'TreasuryCap' in t:
            print(effect['objectId'])
            break
" 2>/dev/null)

# Lấy private key
PRIVATE_KEY=$(sui keytool list --json 2>/dev/null | python3 -c "
import sys, json
data = json.load(sys.stdin)
keys = data if isinstance(data, list) else data.get('keys', [])
for k in keys:
    if k.get('suiAddress', '') == '$ACTIVE_ADDRESS':
        print(k.get('privateKey', ''))
        break
" 2>/dev/null || echo "")

# ── 6. Tạo file .env ─────────────────────────────────────────────────────────
ENV_FILE="$(dirname "$0")/../.env.sui"
cat > "$ENV_FILE" << EOF
# GraphRec × SUI — Auto-generated by deploy_sui.sh
# $(date)

SUI_NETWORK=$NETWORK
SUI_PRIVATE_KEY=$PRIVATE_KEY
SUI_PACKAGE_ID=$PACKAGE_ID
SUI_POOL_ID=$POOL_ID
SUI_REGISTRY_ID=$REGISTRY_ID
SUI_ADMIN_CAP_ID=$ADMIN_CAP_ID
SUI_TREASURY_ID=$TREASURY_ID
SUI_ADMIN_ADDRESS=$ACTIVE_ADDRESS
SUI_CLOCK_ID=0x0000000000000000000000000000000000000000000000000000000000000006
EOF

success ".env.sui đã tạo"

# ── 7. In kết quả ────────────────────────────────────────────────────────────
echo ""
echo "============================================================"
echo "  Deploy hoàn thành!"
echo "============================================================"
echo ""
echo "  Package ID  : $PACKAGE_ID"
echo "  RewardPool  : $POOL_ID"
echo "  Registry    : $REGISTRY_ID"
echo "  AdminCap    : $ADMIN_CAP_ID"
echo "  Treasury    : $TREASURY_ID"
echo "  Admin Wallet: $ACTIVE_ADDRESS"
echo ""
echo "  Explorer: https://suiexplorer.com/object/$PACKAGE_ID?network=$NETWORK"
echo ""

# ── 8. Nạp token vào pool ────────────────────────────────────────────────────
info "Nạp 100,000 GREC vào RewardPool..."
# Mint 100M GREC (100,000 * 1_000_000 raw units = 100_000_000_000 raw)
FUND_CMD="sui client call \
  --package $PACKAGE_ID \
  --module graphrec \
  --function fund_pool \
  --args $ADMIN_CAP_ID $TREASURY_ID $POOL_ID 100000000000 \
  --gas-budget 10000000"
eval $FUND_CMD 2>/dev/null && success "Pool đã được nạp 100,000 GREC" || warn "Fund pool thất bại"

# ── 9. Hướng dẫn tiếp theo ───────────────────────────────────────────────────
echo ""
info "Bước tiếp theo:"
echo "  1. Copy .env.sui vào backend/.env"
echo "  2. Restart backend: docker compose restart backend"
echo "  3. Kiểm tra: curl http://localhost:8000/sui/status"
echo ""
echo "  Hoặc chạy tất cả:"
echo "  cat .env.sui >> backend/.env && docker compose restart backend"
echo ""
