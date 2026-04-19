// frontend/src/components/RecommendPanel.jsx
// Hiển thị gợi ý sản phẩm dùng Neo4j graph traversal.
// Ba chế độ: Collaborative (2-hop), Category-based (3-hop), Lịch sử

import { useState, useEffect } from "react";
import { api }         from "../api";
import ProductGrid     from "./ProductGrid";

const MODES = [
  {
    id:    "collaborative",
    label: "Người dùng tương tự (Collaborative)",
    desc:  "2-hop: User → Product ← User → Product",
  },
  {
    id:    "category",
    label: "Theo danh mục yêu thích (Category-based)",
    desc:  "3-hop: User → Product → Category ← Product",
  },
  {
    id:    "history",
    label: "Lịch sử xem / mua",
    desc:  "Các sản phẩm đã tương tác gần đây",
  },
];

// Chuẩn hóa trường category: backend có thể trả về 'category' hoặc 'sub_category'
function normalizeItem(p) {
  return { ...p, category: p.category || p.sub_category || "" };
}

export default function RecommendPanel({ userId }) {
  const [mode,    setMode]    = useState("collaborative");
  const [data,    setData]    = useState(null);
  const [similar, setSimilar] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);

  // Re-fetch khi userId hoặc mode thay đổi
  useEffect(() => {
    fetchData();
  }, [userId, mode]);

  async function fetchData() {
    setLoading(true);
    setData(null);
    setError(null);
    setSimilar([]);
    try {
      if (mode === "collaborative") {
        const [recsRes, simRes] = await Promise.allSettled([
          api.get(`/recommend/${userId}`),
          api.get(`/recommend/similar-users/${userId}`),
        ]);
        if (recsRes.status === "fulfilled") setData(recsRes.value);
        else throw new Error(recsRes.reason?.message);
        if (simRes.status === "fulfilled") setSimilar(simRes.value.similar_users || []);

      } else if (mode === "category") {
        const d = await api.get(`/recommend/category/${userId}`);
        setData(d);

      } else {
        const d = await api.get(`/recommend/history/${userId}`);
        setData({ method: "history", items: d.history || [] });
      }
    } catch (e) {
      setError(e.message || "Lỗi kết nối API");
    } finally {
      setLoading(false);
    }
  }

  const items = (data?.items || []).map(normalizeItem);

  return (
    <div className="recommend-panel">
      {/* Tiêu đề */}
      <div className="recommend-header">
        <h2>Gợi ý sản phẩm cho <strong>{userId}</strong></h2>
        <p className="rec-subtitle">
          Sử dụng Neo4j Graph Traversal — không cần JOIN phức tạp
        </p>
      </div>

      {/* Chon che do */}
      <div className="mode-tabs">
        {MODES.map(m => (
          <button
            key={m.id}
            className={`mode-tab ${mode === m.id ? "active" : ""}`}
            onClick={() => setMode(m.id)}
          >
            <span className="mode-tab-label">{m.label}</span>
            <span className="mode-tab-desc">{m.desc}</span>
          </button>
        ))}
      </div>

      {/* Người dùng có sở thích tương tự — chỉ hiển thị với Collaborative */}
      {mode === "collaborative" && similar.length > 0 && (
        <div className="similar-users">
          <div className="similar-users-title">Người dùng tương tự</div>
          <div className="similar-list">
            {similar.map(u => (
              <div key={u.user_id} className="similar-chip">
                <div>
                  <span className="similar-uid">{u.user_id}: </span>
                  <span className="similar-count">{u.common_products} sản phẩm chung</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <p>Đang truy vấn Neo4j ...</p>
        </div>
      )}

      {/* Lỗi */}
      {error && !loading && (
        <div className="badge-err">Lỗi: {error}</div>
      )}

      {/* Kết quả*/}
      {!loading && !error && (
        <>
          <div>
            {data?.method === "fallback_top_rated" ? (
              <span className="badge-warn">
                Dữ liệu phân tích không đủ — hiển thị top-rated thay thế
              </span>
            ) : (
              <span className="badge-ok">
                {mode === "history" ? "Lịch sử tương tác" : "Neo4j graph traversal"}
                {" — "}{items.length} kết quả
              </span>
            )}
          </div>
          <ProductGrid products={items} />
        </>
      )}
    </div>
  );
}
