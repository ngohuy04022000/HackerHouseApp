import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "../api";

export default function ProductDetailPage({
  userId,
  walletAddress,
  profileObjectId,
  setWalletAddress,
  setProfileObjectId,
}) {
  const { productId } = useParams();
  const navigate = useNavigate();

  const [detail, setDetail] = useState(null);
  const [reviewHistory, setReviewHistory] = useState([]);
  const [walletSummary, setWalletSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);
  const [message, setMessage] = useState("");
  const [reviewForm, setReviewForm] = useState({ user_name: "", rating: 5, comment: "" });

  const loadDetail = async () => {
    if (!productId) return;
    setLoading(true);
    try {
      const data = await api.get(`/products/${productId}/detail`);
      setDetail(data);
    } catch (e) {
      setMessage(`Không tải được chi tiết: ${e.message}`);
      setDetail(null);
    } finally {
      setLoading(false);
    }
  };

  const loadUserReviewHistory = async () => {
    if (!userId) {
      setReviewHistory([]);
      return;
    }
    try {
      const data = await api.get(`/users/${userId}/reviews?size=20`);
      setReviewHistory(data.items || []);
    } catch {
      setReviewHistory([]);
    }
  };

  const refreshWallet = async () => {
    if (!walletAddress?.trim()) {
      setWalletSummary(null);
      return;
    }
    try {
      const d = await api.get(`/sui/wallet/${walletAddress.trim()}`);
      setWalletSummary(d);
      if (d?.default_profile_object_id && !profileObjectId?.trim()) {
        setProfileObjectId(d.default_profile_object_id);
      }
    } catch {
      setWalletSummary(null);
    }
  };

  const rewardProductAction = async (action) => {
    if (!walletAddress?.trim() || !detail?.product?.product_id) return null;
    return api.post("/sui/reward", {
      recipient_address: walletAddress.trim(),
      profile_object_id: profileObjectId?.trim() || "",
      product_id: detail.product.product_id,
      action,
    });
  };

  const buyNow = async () => {
    if (!walletAddress?.trim()) {
      setMessage("Vui lòng nhập địa chỉ ví SUI để mua + nhận thưởng.");
      return;
    }
    if (!detail?.product?.product_id) return;

    setActionLoading(true);
    setMessage("");
    try {
      const rewardRes = await rewardProductAction("BOUGHT");
      await api.post("/sui/mint-nft", {
        recipient_address: walletAddress.trim(),
        product_id: detail.product.product_id,
        name: detail.product.title || detail.product.product_id,
        description: `Đơn mua từ GraphRec Commerce - ${new Date().toLocaleDateString("vi-VN")}`,
        image_url: detail.product.image_url || "",
        brand: detail.product.brand || "",
        category: detail.product.sub_category || "",
        price_grec: 100000000,
        rating: Math.round((Number(detail.product.rating) || 0) * 10),
      });
      setMessage(`Mua hàng thành công${rewardRes?.grec_amount ? `, +${rewardRes.grec_amount} GREC` : ""}.`);
      await refreshWallet();
    } catch (e) {
      setMessage(`Mua hàng lỗi: ${e.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const submitReview = async (e) => {
    e.preventDefault();
    if (!detail?.product?.product_id) return;
    if (!reviewForm.comment.trim()) {
      setMessage("Vui lòng nhập nội dung đánh giá.");
      return;
    }

    setReviewLoading(true);
    setMessage("");
    try {
      await api.post(`/products/${detail.product.product_id}/reviews`, {
        user_id: userId,
        user_name: reviewForm.user_name.trim() || userId || "Guest",
        wallet_address: walletAddress?.trim() || "",
        rating: Number(reviewForm.rating),
        comment: reviewForm.comment.trim(),
      });

      let rewardText = "";
      if (walletAddress?.trim()) {
        try {
          const rewardRes = await rewardProductAction("REVIEWED");
          rewardText = rewardRes?.grec_amount ? `, +${rewardRes.grec_amount} GREC` : "";
          await refreshWallet();
        } catch (rwErr) {
          rewardText = ` (đã lưu đánh giá, chưa cộng điểm: ${rwErr.message})`;
        }
      }

      setMessage(`Đánh giá thành công${rewardText}.`);
      setReviewForm((prev) => ({ ...prev, comment: "" }));
      await loadDetail();
      await loadUserReviewHistory();
    } catch (e2) {
      setMessage(`Gửi đánh giá lỗi: ${e2.message}`);
    } finally {
      setReviewLoading(false);
    }
  };

  useEffect(() => {
    loadDetail();
    loadUserReviewHistory();
    refreshWallet();
  }, [productId, userId]);

  useEffect(() => {
    const autoViewedReward = async () => {
      if (!walletAddress?.trim() || !detail?.product?.product_id) return;
      const rewardKey = `viewed_reward:${walletAddress.trim()}:${detail.product.product_id}`;
      if (sessionStorage.getItem(rewardKey)) return;
      try {
        await rewardProductAction("VIEWED");
        sessionStorage.setItem(rewardKey, "1");
        await refreshWallet();
      } catch {
        // Silent fail: khong chan luong UX neu reward VIEWED gap loi.
      }
    };
    autoViewedReward();
  }, [walletAddress, detail?.product?.product_id, profileObjectId]);

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-inner" style={{ justifyContent: "space-between" }}>
          <div className="logo">
            <div>
              <h1>Product Detail</h1>
              <p>E-commerce + blockchain behavior rewards</p>
            </div>
          </div>
          <button className="btn-secondary" onClick={() => navigate(-1)}>← Quay lại cửa hàng</button>
        </div>
      </header>

      <main className="main-content" style={{ maxWidth: 1200, margin: "0 auto", width: "100%" }}>
        {loading && <div className="badge-info">Đang tải chi tiết sản phẩm...</div>}

        {!loading && !detail?.product && <div className="badge-err">Không tìm thấy sản phẩm.</div>}

        {!loading && detail?.product && (
          <div className="section-card">
            <div style={{ display: "grid", gridTemplateColumns: "minmax(260px, 320px) 1fr", gap: 18 }}>
              <div style={{ background: "var(--surface-2)", border: "1px solid var(--border)", borderRadius: 10, padding: 12 }}>
                {detail.product.image_url ? (
                  <img src={detail.product.image_url} alt={detail.product.title} style={{ width: "100%", height: 300, objectFit: "contain" }} />
                ) : (
                  <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--text-3)" }}>
                    Chưa có ảnh
                  </div>
                )}
              </div>

              <div>
                <h2 style={{ fontSize: "1.25rem", marginBottom: 8 }}>{detail.product.title}</h2>
                <div style={{ color: "var(--text-2)", marginBottom: 10 }}>{detail.product.brand || "No brand"} • {detail.product.sub_category || "General"}</div>

                <div style={{ display: "flex", gap: 20, flexWrap: "wrap", marginBottom: 12 }}>
                  <span>Giá: <strong>₹{Number(detail.product.price || 0).toLocaleString()}</strong></span>
                  <span>Rating data: <strong>{Number(detail.product.rating || 0).toFixed(1)}/5</strong></span>
                  <span>Review user: <strong>{Number(detail.review_summary?.avg_rating || 0).toFixed(2)}/5</strong></span>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, marginBottom: 12 }}>
                  <input
                    value={walletAddress}
                    onChange={(e) => setWalletAddress(e.target.value)}
                    placeholder="SUI wallet address (0x...)"
                    style={{ padding: "9px 10px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
                  />
                  <input
                    value={profileObjectId}
                    onChange={(e) => setProfileObjectId(e.target.value)}
                    placeholder="Profile object ID"
                    style={{ padding: "9px 10px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
                  />
                </div>

                <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 }}>
                  <button className="run-btn" disabled={actionLoading} onClick={buyNow}>
                    {actionLoading ? "Đang xử lý..." : "Mua ngay (+BOUGHT + NFT)"}
                  </button>
                  <button className="btn-secondary" disabled={actionLoading} onClick={refreshWallet}>Làm mới ví</button>
                </div>

                {walletSummary && (
                  <div style={{ color: "var(--text-2)", fontSize: ".83rem", marginBottom: 8 }}>
                    GREC: <strong style={{ color: "var(--acc)" }}>{walletSummary.grec_formatted || "0 GREC"}</strong> • NFT: <strong style={{ color: "var(--neo4j)" }}>{walletSummary.nft_count ?? 0}</strong> • Mode: <strong>{walletSummary.simulated ? "Demo" : "On-chain"}</strong>
                  </div>
                )}

                {message && <div className="badge-info">{message}</div>}
              </div>
            </div>
          </div>
        )}

        {detail?.product && (
          <div className="section-card">
            <div className="section-title">Đánh giá sản phẩm</div>
            <form onSubmit={submitReview} style={{ marginBottom: 14 }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 120px", gap: 8, marginBottom: 8 }}>
                <input
                  value={reviewForm.user_name}
                  onChange={(e) => setReviewForm((prev) => ({ ...prev, user_name: e.target.value }))}
                  placeholder="Tên hiển thị"
                  style={{ padding: "9px 10px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
                />
                <select
                  value={reviewForm.rating}
                  onChange={(e) => setReviewForm((prev) => ({ ...prev, rating: Number(e.target.value) }))}
                  style={{ padding: "9px 10px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
                >
                  <option value={5}>5 sao</option>
                  <option value={4}>4 sao</option>
                  <option value={3}>3 sao</option>
                  <option value={2}>2 sao</option>
                  <option value={1}>1 sao</option>
                </select>
              </div>
              <textarea
                value={reviewForm.comment}
                onChange={(e) => setReviewForm((prev) => ({ ...prev, comment: e.target.value }))}
                placeholder="Bạn thấy sản phẩm này như thế nào?"
                rows={3}
                style={{ width: "100%", resize: "vertical", padding: "9px 10px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none", marginBottom: 8 }}
              />
              <button type="submit" className="run-btn" disabled={reviewLoading || actionLoading}>
                {reviewLoading ? "Đang gửi..." : "Gửi đánh giá (+REVIEWED)"}
              </button>
            </form>

            <div style={{ marginBottom: 14 }}>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Review gần đây</div>
              {!(detail.reviews || []).length && <div style={{ color: "var(--text-3)" }}>Chưa có review.</div>}
              {(detail.reviews || []).map((rv) => (
                <div key={rv.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 8 }}>
                    <strong>{rv.user_name || "Guest"}</strong>
                    <span style={{ color: "var(--es)" }}>{"★".repeat(Number(rv.rating || 0))}{"☆".repeat(5 - Number(rv.rating || 0))}</span>
                  </div>
                  <div style={{ color: "var(--text-2)", fontSize: ".82rem" }}>{rv.comment || ""}</div>
                </div>
              ))}
            </div>

            <div>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Lịch sử đánh giá của bạn</div>
              {!reviewHistory.length && <div style={{ color: "var(--text-3)" }}>Chưa có lịch sử review cho user hiện tại.</div>}
              {reviewHistory.slice(0, 8).map((item) => (
                <div key={item.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0", fontSize: ".82rem" }}>
                  <strong>{item.title}</strong> • <span style={{ color: "var(--es)" }}>{"★".repeat(Number(item.rating || 0))}{"☆".repeat(5 - Number(item.rating || 0))}</span>
                  <div style={{ color: "var(--text-2)" }}>{item.comment || ""}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}