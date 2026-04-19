export default function Sidebar({
  categories,
  users,
  userId,
  onUserChange,
  onCategoryClick,
  activeCategory,
}) {
  return (
    <aside className="sidebar">
      {/* Chọn người dùng */}
      <div className="sidebar-section">
        <span className="sidebar-label">Người dùng</span>
        <select
          value={userId}
          onChange={e => onUserChange(e.target.value)}
          className="user-select"
        >
          {users.map(u => (
            <option key={u.user_id} value={u.user_id}>
              {u.user_id} – {u.user_name || u.name || ""}
            </option>
          ))}
        </select>
      </div>

      {/* Danh mục sản phẩm */}
      <div className="sidebar-section">
        <span className="sidebar-label">Danh mục</span>
        <ul className="category-list">
          {/* Xem tất cả */}
          <li>
            <button
              className={`cat-btn ${!activeCategory ? "active" : ""}`}
              onClick={() => onCategoryClick("")}
            >
              <span>Tất cả</span>
            </button>
          </li>

          {categories.map(c => (
            <li key={c.category}>
              <button
                className={`cat-btn ${activeCategory === c.category ? "active" : ""}`}
                onClick={() => onCategoryClick(c.category)}
              >
                <span>{c.category}</span>
                {c.count != null && (
                  <span className="cat-count">{c.count}</span>
                )}
              </button>
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}
