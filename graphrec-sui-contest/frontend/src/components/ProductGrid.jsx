// frontend/src/components/ProductGrid.jsx

// Hien thi thanh danh gia sao
function Stars({ rating }) {
  const r = Math.min(5, Math.max(0, Math.round(parseFloat(rating) || 0)));
  return (
    <span className="stars">
      {"★".repeat(r)}
      {"☆".repeat(5 - r)}
      <span className="rating-num"> {(parseFloat(rating) || 0).toFixed(1)}</span>
    </span>
  );
}

function ProductCard({ product, onSelect, onViewDetail, selected }) {
  // _highlight la doan HTML co <em> tu Elasticsearch highlight
  const title = product._highlight?.[0] || product.title || "(Khong co ten)";
  const img   = product.image_url;
  const price = parseFloat(product.price)          || 0;
  const orig  = parseFloat(product.original_price) || 0;

  // Phan tram giam gia — chi hien neu gia goc > gia hien tai > 0
  const disc  = (orig > price && price > 0)
    ? Math.round((1 - price / orig) * 100) : 0;

  return (
    <div
      className="product-card"
      onClick={() => onSelect?.(product)}
      style={selected ? { border: "1px solid var(--acc)" } : undefined}
    >
      {/* Anh san pham */}
      <div className="product-img-wrap">
        {img
          ? <img src={img} alt={product.title} loading="lazy" />
          : <div className="product-img-placeholder">San pham</div>}
        {disc > 0 && <span className="discount-badge">-{disc}%</span>}
      </div>

      {/* Thong tin san pham */}
      <div className="product-info">
        <p
          className="product-title"
          /* dangerouslySetInnerHTML de render the <em> tu ES highlight */
          dangerouslySetInnerHTML={{ __html: title }}
        />
        {product.brand && <p className="product-brand">{product.brand}</p>}

        <Stars rating={product.rating} />
        {product.review_count > 0 && (
          <span className="review-count">
            ({Number(product.review_count).toLocaleString()} danh gia)
          </span>
        )}

        <div className="product-price">
          {price > 0 && <span className="price-current">₹{price.toLocaleString()}</span>}
          {orig > price && orig > 0 &&
            <span className="price-orig">₹{orig.toLocaleString()}</span>}
        </div>

        {/* Danh muc — backend co the tra ve 'category' hoac 'sub_category' */}
        <span className="product-cat-tag">
          {product.category || product.sub_category || ""}
        </span>

        {/* Score hien khi la ket qua goi y */}
        {product.score != null && (
          <span className="score-badge">score: {product.score}</span>
        )}

        <button
          className="btn-secondary"
          style={{ marginTop: 8, width: "100%" }}
          onClick={(e) => {
            e.stopPropagation();
            onViewDetail?.(product);
          }}
        >
          Xem chi tiết
        </button>
      </div>
    </div>
  );
}

export default function ProductGrid({ products, onSelect, onViewDetail, selectedProductId }) {
  if (!products || products.length === 0) {
    return (
      <div className="empty-state">
        Khong tim thay san pham nao.
      </div>
    );
  }
  return (
    <div className="product-grid">
      {products.map((p, i) => (
        <ProductCard
          key={p.product_id || i}
          product={p}
          onSelect={onSelect}
          onViewDetail={onViewDetail}
          selected={selectedProductId && selectedProductId === p.product_id}
        />
      ))}
    </div>
  );
}
