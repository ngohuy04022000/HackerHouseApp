// frontend/src/components/SearchBar.jsx
import { useState } from "react";

// Icon tìm kiếm đơn giản bằng SVG (không dùng emoji)
function SearchIcon() {
  return (
    <svg viewBox="0 0 20 20" fill="none" stroke="currentColor" strokeWidth="2"
         strokeLinecap="round" strokeLinejoin="round">
      <circle cx="8.5" cy="8.5" r="5.5" />
      <line x1="13" y1="13" x2="18" y2="18" />
    </svg>
  );
}

// Các từ khóa gợi ý nhanh cho dataset Air Conditioners
const QUICK_TERMS = ["Inverter", "LG", "Samsung", "1.5 Ton", "5 Star", "Split AC", "Daikin"];

export default function SearchBar({ onSearch, categories, loading, initialQuery }) {
  const [q,   setQ]   = useState(initialQuery || "");
  const [cat, setCat] = useState("");

  const submit = e => {
    e.preventDefault();
    if (q.trim()) onSearch(q.trim(), cat);
  };

  return (
    <div className="search-bar-wrap">
      <form className="search-form" onSubmit={submit}>
        <div className="search-input-group">
          {/* Icon search */}
          <span className="search-icon"><SearchIcon /></span>

          <input
            className="search-input"
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder="Tìm sản phẩm... (vd: LG , Split AC 1.5 Ton)"
            autoFocus
          />

          {/* Bộ lọc danh mục */}
          <select
            className="search-cat-select"
            value={cat}
            onChange={e => setCat(e.target.value)}
          >
            <option value="">Tất cả danh mục</option>
            {categories.map(c => (
              <option key={c.category} value={c.category}>{c.category}</option>
            ))}
          </select>

          <button className="search-btn" type="submit" disabled={loading}>
            {loading ? "..." : "Tìm kiếm"}
          </button>
        </div>
      </form>

      {/* Phím tắt tìm kiếm nhanh */}
      <div className="quick-search">
        {QUICK_TERMS.map(t => (
          <button
            key={t}
            className="quick-chip"
            onClick={() => { setQ(t); onSearch(t, cat); }}
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}
