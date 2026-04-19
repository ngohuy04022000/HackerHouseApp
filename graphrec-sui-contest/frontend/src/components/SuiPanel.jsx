// frontend/src/components/SuiPanel.jsx
//
// Tab SUI Blockchain — tích hợp ví, GREC token, Product NFT, on-chain score.
// Dùng @mysten/dapp-kit cho wallet connection; fallback input thủ công.
//
// Cài đặt: npm install @mysten/dapp-kit @mysten/sui.js @tanstack/react-query

import { useState, useEffect, useCallback } from "react";
import {
  BarChart3,
  BookOpenText,
  CheckCircle2,
  Coins,
  ExternalLink,
  Eye,
  Info,
  KeyRound,
  Link2,
  Palette,
  RefreshCw,
  ShoppingCart,
  Sparkles,
  Star,
  Tag,
  UserPlus,
  Wallet,
  Wrench,
  XCircle,
} from "lucide-react";
import { api } from "../api";

// ─── Optional: import SUI dApp Kit nếu đã cài ─────────────────────────────
// import { ConnectButton, useCurrentAccount, useSuiClientQuery } from "@mysten/dapp-kit";
// Nếu chưa cài, dùng manual address input bên dưới

// ─── Hooks helpers ─────────────────────────────────────────────────────────
function useSuiStatus() {
  const [status, setStatus] = useState(null);
  useEffect(() => {
    api.get("/sui/status").then(setStatus).catch(() => setStatus({ configured: false }));
  }, []);
  return status;
}

function parseApiError(error) {
  const raw = error?.message || "Unknown error";
  const marker = "{";
  const start = raw.indexOf(marker);
  if (start >= 0) {
    try {
      const payload = JSON.parse(raw.slice(start));
      if (payload?.detail) return payload.detail;
    } catch {
      // Keep original text when body is not valid JSON.
    }
  }
  return raw;
}

function useWalletAssets(address) {
  const [assets, setAssets] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const refresh = useCallback(async () => {
    if (!address) return;
    setLoading(true);
    setError(null);
    try {
      const d = await api.get(`/sui/wallet/${address}`);
      setAssets(d);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [address]);

  useEffect(() => { refresh(); }, [refresh]);
  return { assets, loading, error, refresh };
}

// ─── Sub-components ────────────────────────────────────────────────────────

// NFT Card
function NFTCard({ nft }) {
  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 10, overflow: "hidden", transition: "var(--t)",
    }}
      className="product-card"
    >
      <div className="product-img-wrap" style={{ height: 130 }}>
        {nft.image_url
          ? <img src={nft.image_url} alt={nft.name} loading="lazy" />
          : <div className="product-img-placeholder" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}><Tag size={16} />NFT #{nft.serial}</div>
        }
        <span className="discount-badge" style={{ background: "var(--acc)" }}>
          NFT #{nft.serial}
        </span>
      </div>
      <div className="product-info">
        <p className="product-title">{nft.name || nft.product_id}</p>
        <p className="product-brand">{nft.brand}</p>
        <span className="product-cat-tag">{nft.category}</span>
        <div style={{ fontSize: ".73rem", color: "var(--text-3)", marginTop: 4, fontFamily: "var(--mono)" }}>
          {nft.product_id}
        </div>
        <div style={{ fontSize: ".7rem", color: "var(--text-3)" }}>
          Mint: {nft.minted_at ? new Date(parseInt(nft.minted_at)).toLocaleDateString("vi-VN") : "—"}
        </div>
      </div>
    </div>
  );
}

// GREC Balance display
function GrecBalance({ balance, formatted, simulated }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(108,99,255,.15), rgba(0,180,216,.1))",
      border: "1px solid rgba(108,99,255,.3)", borderRadius: 12,
      padding: "16px 20px",
      display: "flex", justifyContent: "space-between", alignItems: "center",
    }}>
      <div>
        <div style={{ fontSize: ".72rem", color: "var(--text-3)", fontWeight: 700, marginBottom: 4, textTransform: "uppercase", letterSpacing: ".7px" }}>
          GREC Token Balance {simulated && "(Demo)"}
        </div>
        <div style={{ fontSize: "2rem", fontWeight: 800, color: "var(--acc)", fontFamily: "var(--mono)" }}>
          {formatted || `${(balance / 1_000_000).toFixed(2)} GREC`}
        </div>
      </div>
      <div style={{
        width: 52, height: 52, borderRadius: "50%",
        background: "linear-gradient(135deg, var(--acc), var(--neo4j))",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Coins size={24} color="#fff" />
      </div>
    </div>
  );
}

// Reward action button
function RewardButton({ label, action, Icon, grec, loading, onReward }) {
  return (
    <button
      onClick={() => onReward(action)}
      disabled={loading}
      style={{
        flex: 1, minWidth: 120,
        padding: "10px 14px", borderRadius: 8,
        border: "1px solid var(--border-2)",
        background: "var(--surface)", color: "var(--text)",
        display: "flex", flexDirection: "column", alignItems: "center",
        gap: 4, cursor: "pointer", transition: "var(--t)",
        opacity: loading ? .5 : 1,
      }}
    >
      <span style={{ lineHeight: 0 }}><Icon size={22} /></span>
      <span style={{ fontSize: ".82rem", fontWeight: 700 }}>{label}</span>
      <span style={{
        fontSize: ".73rem", color: "var(--acc)", fontWeight: 600,
        background: "var(--acc-light)", padding: "1px 7px", borderRadius: 8,
      }}>
        +{grec} GREC
      </span>
    </button>
  );
}

// On-chain score visualization
function OnChainScore({ score }) {
  if (!score) return null;
  return (
    <div style={{
      background: "var(--neo4j-bg)", border: "1px solid rgba(0,180,216,.2)",
      borderRadius: 10, padding: 14,
    }}>
      <div style={{ fontSize: ".75rem", color: "var(--neo4j)", fontWeight: 700, marginBottom: 10, textTransform: "uppercase", letterSpacing: ".6px", display: "flex", alignItems: "center", gap: 6 }}>
        <Link2 size={14} /> Điểm gợi ý on-chain (v{score.version})
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
        {(score.top_products || []).slice(0, 5).map((pid, i) => (
          <div key={i} style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "5px 9px", background: "var(--surface)", borderRadius: 6,
          }}>
            <span style={{ fontSize: ".8rem", fontFamily: "var(--mono)", color: "var(--neo4j)" }}>
              #{i + 1} {pid}
            </span>
            <span style={{
              fontSize: ".75rem", fontWeight: 700, color: "var(--acc)",
              background: "var(--acc-light)", padding: "1px 8px", borderRadius: 8,
            }}>
              {(score.scores || [])[i] ?? "—"}
            </span>
          </div>
        ))}
      </div>
      <div style={{ fontSize: ".72rem", color: "var(--text-3)", marginTop: 8 }}>
        Cập nhật: {score.updated_at ? new Date(parseInt(score.updated_at)).toLocaleString("vi-VN") : "—"}
      </div>
    </div>
  );
}

// Tx result display
function TxResult({ result }) {
  if (!result) return null;
  const ok = result.success !== false;
  const StatusIcon = ok ? CheckCircle2 : XCircle;
  return (
    <div style={{
      padding: "10px 14px", borderRadius: 8, marginTop: 10,
      background: ok ? "var(--good-bg)" : "var(--bad-bg)",
      border: `1px solid ${ok ? "rgba(34,197,94,.25)" : "rgba(239,68,68,.25)"}`,
      fontSize: ".82rem", color: ok ? "var(--good)" : "var(--bad)",
    }}>
      <StatusIcon size={14} style={{ verticalAlign: "text-bottom", marginRight: 6 }} />
      {result.simulated ? "(Demo) " : ""}
      {ok
        ? `Thành công${result.digest ? ` — TX: ${result.digest.substring(0, 16)}...` : ""}`
        : `Lỗi: ${result.error}`}
      {ok && result.explorer_link && (
        <a href={result.explorer_link} target="_blank" rel="noopener noreferrer"
          style={{ marginLeft: 8, color: "var(--neo4j)", fontSize: ".75rem", display: "inline-flex", alignItems: "center", gap: 4 }}>
          Xem Explorer <ExternalLink size={12} />
        </a>
      )}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────

export default function SuiPanel({ userId }) {
  const suiStatus = useSuiStatus();
  const suiNetwork = suiStatus?.network || "testnet";

  // Wallet address — có thể dùng dApp Kit hoặc nhập thủ công
  const [walletAddress, setWalletAddress] = useState("");
  const [inputAddr, setInputAddr] = useState("");
  const [profileObjectId, setProfileObjectId] = useState("");

  const { assets, loading: assetsLoading, error: assetsError, refresh } = useWalletAssets(walletAddress);

  // Demo product để test reward/mint
  const [demoProduct] = useState({
    product_id: "P0001DEMO",
    name: "LG 1.5 Ton Inverter AC",
    brand: "LG",
    category: "Air Conditioners",
    image_url: "https://m.media-amazon.com/images/I/51JFb7FctDL._AC_UL320_.jpg",
    rating: 42,
  });

  const [rewardLoading, setRewardLoading] = useState(false);
  const [mintLoading, setMintLoading] = useState(false);
  const [scoreLoading, setScoreLoading] = useState(false);
  const [onboardLoading, setOnboardLoading] = useState(false);
  const [quickActionsLoading, setQuickActionsLoading] = useState(false);
  const [lastTx, setLastTx] = useState(null);
  const [lastMintTx, setLastMintTx] = useState(null);
  const [lastScoreTx, setLastScoreTx] = useState(null);
  const [recommendPreview, setRecommendPreview] = useState([]);
  const [quickActions, setQuickActions] = useState([]);
  const [txHistory, setTxHistory] = useState([]);
  const [activeSection, setActiveSection] = useState("wallet");

  const pushTxHistory = useCallback((entry) => {
    setTxHistory(prev => [
      {
        id: `${Date.now()}_${Math.random().toString(16).slice(2, 8)}`,
        at: new Date().toLocaleString("vi-VN"),
        ...entry,
      },
      ...prev,
    ].slice(0, 8));
  }, []);

  const loadQuickActions = useCallback(async (address) => {
    if (!address) {
      setQuickActions([]);
      return;
    }
    setQuickActionsLoading(true);
    try {
      const data = await api.get(`/sui/quick-actions?address=${encodeURIComponent(address)}`);
      setQuickActions(data.actions || []);
    } catch {
      setQuickActions([]);
    } finally {
      setQuickActionsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (assets?.default_profile_object_id && !profileObjectId.trim()) {
      setProfileObjectId(assets.default_profile_object_id);
    }
  }, [assets, profileObjectId]);

  useEffect(() => {
    loadQuickActions(walletAddress);
  }, [walletAddress, loadQuickActions]);

  const connectAddress = () => {
    if (inputAddr.trim().startsWith("0x")) {
      setWalletAddress(inputAddr.trim());
    }
  };

  const handleOnboard = async () => {
    if (!walletAddress) return alert("Nhập địa chỉ ví trước");
    setOnboardLoading(true);
    try {
      const res = await api.post("/sui/onboard-user", {
        user_id: userId,
        wallet_address: walletAddress,
        auto_register: true,
      });
      if (res.profile_object_id) {
        setProfileObjectId(res.profile_object_id);
      }
      pushTxHistory({
        type: "onboard",
        ok: true,
        digest: res.registration?.digest || null,
        note: "Onboard user thành công",
      });
      await refresh();
      await loadQuickActions(walletAddress);
    } catch (e) {
      const msg = parseApiError(e);
      pushTxHistory({ type: "onboard", ok: false, note: msg });
      alert(`Onboard lỗi: ${msg}`);
    } finally {
      setOnboardLoading(false);
    }
  };

  const handleReward = async (action) => {
    if (!walletAddress) return alert("Nhập địa chỉ ví trước");
    setRewardLoading(true);
    setLastTx(null);
    try {
      const payload = {
        recipient_address: walletAddress,
        profile_object_id: profileObjectId.trim(),
        product_id: demoProduct.product_id,
        action: action,
      };
      const r = await api.post("/sui/reward", payload);
      setLastTx(r);
      pushTxHistory({
        type: `reward_${action.toLowerCase()}`,
        ok: true,
        digest: r.digest,
        note: `Reward ${action} +${r.grec_amount ?? "?"} GREC`,
      });
      setTimeout(refresh, 2000);
      setTimeout(() => loadQuickActions(walletAddress), 1000);
    } catch (e) {
      const msg = parseApiError(e);
      setLastTx({ success: false, error: msg });
      pushTxHistory({ type: `reward_${action.toLowerCase()}`, ok: false, note: msg });
    } finally {
      setRewardLoading(false);
    }
  };

  const handleMintNFT = async () => {
    if (!walletAddress) return alert("Nhập địa chỉ ví trước");
    setMintLoading(true);
    setLastMintTx(null);
    try {
      const payload = {
        recipient_address: walletAddress,
        product_id: demoProduct.product_id,
        name: demoProduct.name,
        description: `Mua tại GraphRec — ${new Date().toLocaleDateString("vi-VN")}`,
        image_url: demoProduct.image_url,
        brand: demoProduct.brand,
        category: demoProduct.category,
        price_grec: 100000000,
        rating: demoProduct.rating,
      };
      const r = await api.post("/sui/mint-nft", payload);
      setLastMintTx(r);
      pushTxHistory({
        type: "mint_nft",
        ok: true,
        digest: r.digest,
        note: `Mint NFT ${demoProduct.product_id}`,
      });
      setTimeout(refresh, 2000);
    } catch (e) {
      const msg = parseApiError(e);
      setLastMintTx({ success: false, error: msg });
      pushTxHistory({ type: "mint_nft", ok: false, note: msg });
    } finally {
      setMintLoading(false);
    }
  };

  const handleUpdateScore = async () => {
    if (!walletAddress) return alert("Nhập địa chỉ ví trước");
    setScoreLoading(true);
    setLastScoreTx(null);
    try {
      // Lấy gợi ý từ Neo4j rồi cập nhật on-chain
      const walletParam = encodeURIComponent(walletAddress);
      const r = await api.get(
        `/sui/recommend-with-chain/${userId}?wallet_address=${walletParam}&limit=5`
      );
      setRecommendPreview(r.items || []);
      setLastScoreTx(r.chain_update || { success: true, simulated: true });
      pushTxHistory({
        type: "update_score",
        ok: r.chain_update?.success !== false,
        digest: r.chain_update?.digest,
        note: `Đồng bộ ${Math.min((r.items || []).length, 5)} gợi ý lên chain`,
      });
      setTimeout(refresh, 2000);
    } catch (e) {
      const msg = parseApiError(e);
      setLastScoreTx({ success: false, error: msg });
      pushTxHistory({ type: "update_score", ok: false, note: msg });
    } finally {
      setScoreLoading(false);
    }
  };

  const sections = [
    { id: "wallet", label: "Ví và Token" },
    { id: "nft", label: "NFT Collection" },
    { id: "actions", label: "Thao tác" },
    { id: "info", label: "Hướng dẫn" },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      {/* Header */}
      <div className="panel-header">
        <h2>SUI Blockchain Integration</h2>
        <p>
          GREC Loyalty Token · Product NFT · On-chain Recommendation Score.
          Kết nối ví để nhận thưởng khi tương tác với hệ thống.
        </p>
      </div>

      {/* Network status */}
      {suiStatus && (
        <div style={{
          display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap",
          padding: "10px 14px", background: "var(--surface)",
          border: "1px solid var(--border)", borderRadius: 8, fontSize: ".82rem",
        }}>
          <span className={`status-dot ${suiStatus.configured ? "ok" : "err"}`}>
            <span className="dot" />
            {suiStatus.configured ? "SUI Connected" : "SUI Not Configured (Demo Mode)"}
          </span>
          <span style={{ color: "var(--text-3)" }}>|</span>
          <span style={{ color: "var(--text-2)" }}>
            Network: <strong style={{ color: "var(--neo4j)" }}>{suiStatus.network || "testnet"}</strong>
          </span>
          {suiStatus.pool_stats?.balance_grec && (
            <>
              <span style={{ color: "var(--text-3)" }}>|</span>
              <span style={{ color: "var(--text-2)" }}>
                Pool: <strong style={{ color: "var(--acc)" }}>{suiStatus.pool_stats.balance_grec} GREC</strong>
              </span>
            </>
          )}
        </div>
      )}

      {/* Wallet connect */}
      <div className="section-card">
        <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><KeyRound size={16} /> Kết nối ví SUI</div>

        {/* Manual input (dùng khi chưa cài dApp Kit) */}
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input
            value={inputAddr}
            onChange={e => setInputAddr(e.target.value)}
            placeholder="Nhập SUI wallet address (0x...)"
            style={{
              flex: 1, padding: "9px 12px", borderRadius: 8,
              border: "1px solid var(--border-2)", background: "var(--bg)",
              color: "var(--text)", fontSize: ".87rem", fontFamily: "var(--mono)",
              outline: "none",
            }}
            onKeyDown={e => e.key === "Enter" && connectAddress()}
          />
          <button
            onClick={connectAddress}
            style={{
              padding: "9px 18px", borderRadius: 8,
              background: "var(--acc)", color: "#fff",
              fontWeight: 700, fontSize: ".87rem", cursor: "pointer",
              border: "none",
            }}
          >
            Kết nối
          </button>
          {/* Demo address */}
          <button
            onClick={() => {
              const demo = "0x1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef";
              setInputAddr(demo);
              setWalletAddress(demo);
            }}
            style={{
              padding: "9px 14px", borderRadius: 8,
              border: "1px solid var(--border-2)", background: "var(--surface-2)",
              color: "var(--text-2)", fontSize: ".82rem", cursor: "pointer",
            }}
          >
            Demo
          </button>
        </div>

        {walletAddress && (
          <div style={{
            padding: "8px 12px", background: "var(--good-bg)", borderRadius: 7,
            fontSize: ".8rem", color: "var(--good)", fontFamily: "var(--mono)",
            wordBreak: "break-all",
            display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap",
          }}>
            <CheckCircle2 size={14} /> {walletAddress}
            <a
              href={`https://suiexplorer.com/address/${walletAddress}?network=${suiNetwork}`}
              target="_blank" rel="noopener noreferrer"
              style={{ marginLeft: 8, color: "var(--neo4j)", fontSize: ".73rem", display: "inline-flex", alignItems: "center", gap: 4 }}
            >
              Explorer <ExternalLink size={12} />
            </a>
          </div>
        )}

        {walletAddress && (
          <div style={{ marginTop: 10, display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              className="run-btn"
              onClick={handleOnboard}
              disabled={onboardLoading}
              style={{ display: "inline-flex", alignItems: "center", gap: 6 }}
            >
              <UserPlus size={14} /> {onboardLoading ? "Đang onboard..." : "Onboard nhanh cho user"}
            </button>
            <button
              onClick={() => loadQuickActions(walletAddress)}
              disabled={quickActionsLoading}
              style={{
                padding: "9px 12px", borderRadius: 8,
                border: "1px solid var(--border-2)", background: "var(--surface)",
                color: "var(--text-2)", fontSize: ".82rem", cursor: "pointer",
              }}
            >
              {quickActionsLoading ? "Đang tải gợi ý..." : "Làm mới gợi ý thao tác"}
            </button>
          </div>
        )}
      </div>

      {/* Section nav */}
      {walletAddress && (
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {sections.map(s => (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              style={{
                padding: "7px 14px", borderRadius: 7, fontSize: ".83rem", fontWeight: 600,
                border: "1px solid var(--border)", cursor: "pointer",
                background: activeSection === s.id ? "var(--acc-light)" : "var(--surface)",
                color: activeSection === s.id ? "var(--acc)" : "var(--text-2)",
                transition: "var(--t)",
              }}
            >
              {s.label}
            </button>
          ))}
        </div>
      )}

      {/* ── WALLET SECTION ─────────────────────────────────── */}
      {walletAddress && activeSection === "wallet" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {assetsLoading && <div className="spinner-wrap"><div className="spinner" /><p>Đang tải tài sản...</p></div>}
          {assetsError && <div className="badge-err">Lỗi: {assetsError}</div>}

          {assets && !assetsLoading && (
            <>
              <GrecBalance balance={assets.grec_balance} formatted={assets.grec_formatted} simulated={assets.simulated} />

              <div className="section-card" style={{ margin: 0 }}>
                <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><Sparkles size={16} /> Gợi ý bước tiếp theo</div>
                {quickActionsLoading ? (
                  <div style={{ fontSize: ".82rem", color: "var(--text-3)" }}>Đang phân tích trạng thái ví/pool...</div>
                ) : (
                  <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                    {quickActions.map((a, idx) => (
                      <div key={`${a.code}_${idx}`} style={{
                        padding: "9px 10px", borderRadius: 8,
                        border: "1px solid var(--border)", background: "var(--bg)",
                      }}>
                        <div style={{ fontSize: ".82rem", fontWeight: 700, color: "var(--text)" }}>{a.title}</div>
                        <div style={{ fontSize: ".77rem", color: "var(--text-2)" }}>{a.description}</div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10 }}>
                {[
                  ["NFTs sở hữu", assets.nft_count, Palette, "var(--acc)"],
                  ["GREC earned", assets.grec_formatted?.split(" ")[0] ?? "0", Coins, "var(--es)"],
                  ["On-chain score", assets.recommend_score ? `v${assets.recommend_score.version}` : "—", BarChart3, "var(--neo4j)"],
                ].map(([label, val, Icon, color]) => (
                  <div key={label} style={{
                    background: "var(--surface)", border: "1px solid var(--border)",
                    borderRadius: 10, padding: "12px 14px", textAlign: "center",
                  }}>
                    <div style={{ display: "flex", justifyContent: "center", marginBottom: 4 }}><Icon size={22} /></div>
                    <div style={{ fontSize: "1.3rem", fontWeight: 800, color, fontFamily: "var(--mono)" }}>{val}</div>
                    <div style={{ fontSize: ".74rem", color: "var(--text-3)" }}>{label}</div>
                  </div>
                ))}
              </div>

              <OnChainScore score={assets.recommend_score} />

              <button onClick={refresh} style={{
                padding: "8px 16px", borderRadius: 7, border: "1px solid var(--border-2)",
                background: "var(--surface)", color: "var(--text-2)", fontSize: ".83rem",
                cursor: "pointer", alignSelf: "flex-start",
                display: "inline-flex", alignItems: "center", gap: 6,
              }}>
                <RefreshCw size={14} /> Làm mới
              </button>
            </>
          )}
        </div>
      )}

      {/* ── NFT SECTION ────────────────────────────────────── */}
      {walletAddress && activeSection === "nft" && (
        <div>
          {assets?.nfts?.length > 0 ? (
            <>
              <div style={{ marginBottom: 12, color: "var(--text-2)", fontSize: ".85rem" }}>
                {assets.nft_count} Product NFT{assets.simulated ? " (demo)" : ""}
              </div>
              <div className="product-grid">
                {assets.nfts.map((nft, i) => <NFTCard key={i} nft={nft} />)}
              </div>
            </>
          ) : (
            <div className="empty-state">
              Chưa có Product NFT. Thực hiện mua hàng để nhận NFT!
            </div>
          )}
        </div>
      )}

      {/* ── ACTIONS SECTION ─────────────────────────────────── */}
      {walletAddress && activeSection === "actions" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Reward actions */}
          <div className="section-card">
            <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><Sparkles size={16} /> Nhận GREC Token</div>
            <p style={{ fontSize: ".83rem", color: "var(--text-2)", marginBottom: 12 }}>
              Demo sản phẩm: <strong>{demoProduct.name}</strong> ({demoProduct.product_id})
            </p>
            <input
              value={profileObjectId}
              onChange={e => setProfileObjectId(e.target.value)}
              placeholder="Profile object ID (bắt buộc khi chạy on-chain thật)"
              style={{
                width: "100%",
                marginBottom: 12,
                padding: "9px 12px",
                borderRadius: 8,
                border: "1px solid var(--border-2)",
                background: "var(--bg)",
                color: "var(--text)",
                fontSize: ".82rem",
                fontFamily: "var(--mono)",
                outline: "none",
              }}
            />
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <RewardButton label="Xem sản phẩm" action="VIEWED" Icon={Eye} grec={10} loading={rewardLoading} onReward={handleReward} />
              <RewardButton label="Mua sản phẩm" action="BOUGHT" Icon={ShoppingCart} grec={100} loading={rewardLoading} onReward={handleReward} />
              <RewardButton label="Đánh giá" action="REVIEWED" Icon={Star} grec={50} loading={rewardLoading} onReward={handleReward} />
            </div>
            {rewardLoading && <div style={{ marginTop: 10, color: "var(--text-3)", fontSize: ".83rem" }}>Đang gửi giao dịch...</div>}
            <TxResult result={lastTx} />
          </div>

          {/* Mint NFT */}
          <div className="section-card">
            <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><Palette size={16} /> Đúc Product NFT</div>
            <p style={{ fontSize: ".83rem", color: "var(--text-2)", marginBottom: 12 }}>
              Mint NFT cho sản phẩm <strong>{demoProduct.name}</strong> vào ví của bạn.
            </p>
            <button className="run-btn" onClick={handleMintNFT} disabled={mintLoading}>
              {mintLoading ? "Đang đúc NFT..." : "Mint Product NFT"}
            </button>
            <TxResult result={lastMintTx} />
          </div>

          {/* Update on-chain score */}
          <div className="section-card">
            <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><BarChart3 size={16} /> Cập nhật điểm gợi ý on-chain</div>
            <p style={{ fontSize: ".83rem", color: "var(--text-2)", marginBottom: 12 }}>
              Chạy Neo4j collaborative query cho user <strong>{userId}</strong>,
              lưu top-5 gợi ý lên SUI blockchain.
            </p>
            <button className="run-btn" onClick={handleUpdateScore} disabled={scoreLoading}>
              {scoreLoading ? "Đang cập nhật..." : "Lưu Score On-chain"}
            </button>
            <TxResult result={lastScoreTx} />
            {recommendPreview.length > 0 && (
              <div style={{ marginTop: 10, display: "flex", flexDirection: "column", gap: 6 }}>
                <div style={{ fontSize: ".79rem", color: "var(--text-3)", fontWeight: 700 }}>Top gợi ý vừa đồng bộ</div>
                {recommendPreview.slice(0, 5).map((item, idx) => (
                  <div key={`${item.product_id}_${idx}`} style={{
                    padding: "7px 10px", borderRadius: 7,
                    border: "1px solid var(--border)", background: "var(--bg)",
                    display: "flex", justifyContent: "space-between", gap: 8,
                  }}>
                    <span style={{ fontSize: ".8rem", color: "var(--text-2)" }}>{item.product_id} - {item.title || "(No title)"}</span>
                    <span style={{ fontSize: ".78rem", color: "var(--acc)", fontWeight: 700 }}>{item.score ?? 0}</span>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="section-card">
            <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><Wallet size={16} /> Lịch sử giao dịch gần đây</div>
            {txHistory.length === 0 ? (
              <div style={{ fontSize: ".82rem", color: "var(--text-3)" }}>Chưa có giao dịch trong phiên hiện tại.</div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {txHistory.map(row => (
                  <div key={row.id} style={{
                    border: "1px solid var(--border)", background: "var(--bg)", borderRadius: 8,
                    padding: "8px 10px", fontSize: ".8rem",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", gap: 8, marginBottom: 3 }}>
                      <strong style={{ color: row.ok ? "var(--good)" : "var(--bad)" }}>{row.type}</strong>
                      <span style={{ color: "var(--text-3)" }}>{row.at}</span>
                    </div>
                    <div style={{ color: "var(--text-2)" }}>{row.note}</div>
                    {row.digest && (
                      <a
                        href={`https://suiexplorer.com/txblock/${row.digest}?network=${suiNetwork}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        style={{ color: "var(--neo4j)", fontSize: ".75rem", display: "inline-flex", alignItems: "center", gap: 4, marginTop: 4 }}
                      >
                        Explorer <ExternalLink size={12} />
                      </a>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── INFO SECTION ──────────────────────────────────────── */}
      {activeSection === "info" && (
        <div className="section-card">
          <div className="section-title" style={{ display: "flex", alignItems: "center", gap: 6 }}><BookOpenText size={16} /> Kiến trúc tích hợp SUI</div>
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {[
              { Icon: Coins, title: "GREC Token", desc: "Fungible token SUI. User nhận khi: xem (10), mua (100), đánh giá (50 GREC). Mint từ TreasuryCap → RewardPool → User." },
              { Icon: Palette, title: "Product NFT", desc: "SUI Object đại diện sản phẩm đã mua. Gắn metadata: product_id, brand, category, rating. Hiển thị trong SUI Explorer." },
              { Icon: BarChart3, title: "On-chain Score", desc: "RecommendScore object lưu top-5 gợi ý từ Neo4j. Cập nhật mỗi khi chạy collaborative query. Immutable proof on-chain." },
              { Icon: Link2, title: "Flow tích hợp", desc: "Neo4j tính toán gợi ý (off-chain intelligence) → FastAPI xác nhận → pysui gọi Move contract → SUI lưu bằng chứng (on-chain proof)." },
              { Icon: Wrench, title: "Smart Contract", desc: "Move language trên SUI. File: contracts/sources/graphrec.move. Deploy: sui client publish --gas-budget 100000000." },
            ].map(({ Icon, title, desc }) => (
              <div key={title} style={{
                display: "flex", gap: 12,
                padding: "10px 12px", background: "var(--bg)",
                border: "1px solid var(--border)", borderRadius: 8,
              }}>
                <span style={{ flexShrink: 0, lineHeight: 0 }}><Icon size={20} /></span>
                <div>
                  <div style={{ fontWeight: 700, fontSize: ".87rem", marginBottom: 3 }}>{title}</div>
                  <div style={{ fontSize: ".8rem", color: "var(--text-2)", lineHeight: 1.5 }}>{desc}</div>
                </div>
              </div>
            ))}
          </div>

          {/* Quick commands */}
          <div style={{ marginTop: 14, padding: 12, background: "#050A14", borderRadius: 8 }}>
            <div style={{ fontSize: ".73rem", color: "var(--text-3)", marginBottom: 8, fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px" }}>
              Quick Deploy Commands
            </div>
            {[
              "# 1. Cài SUI CLI",
              "cargo install --locked --git https://github.com/MystenLabs/sui.git sui",
              "",
              "# 2. Deploy contract lên testnet",
              "cd contracts && sui client publish --gas-budget 100000000",
              "",
              "# 3. Cập nhật .env với các ID từ output",
              "# SUI_PACKAGE_ID=0x... (từ Published Objects)",
              "# SUI_POOL_ID=0x...    (từ Created Objects - RewardPool)",
              "",
              "# 4. Nạp token vào pool",
              "curl -X POST http://localhost:8000/sui/fund-pool \\",
              '  -H "Content-Type: application/json" \\',
              '  -d \'{"amount_grec": 10000}\'',
            ].map((line, i) => (
              <div key={i} style={{
                fontFamily: "var(--mono)", fontSize: ".75rem",
                color: line.startsWith("#") ? "#4A6FA5" : "#7DD3FC",
                minHeight: "1.4em",
              }}>
                {line}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
