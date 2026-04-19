import SearchBar from "../components/SearchBar";
import ProductGrid from "../components/ProductGrid";

export default function ShopPage({
  searchQuery,
  searchResults,
  loading,
  categories,
  selectedProduct,
  walletAddress,
  profileObjectId,
  walletSummary,
  txMessage,
  txLoading,
  onSearch,
  onBrowse,
  onSelectProduct,
  onViewDetail,
  onWalletAddressChange,
  onProfileObjectIdChange,
  onRewardAction,
  onRefreshWalletSummary,
}) {
  return (
    <div>
      <div className="panel-header">
        <h2>Cửa hàng sản phẩm</h2>
        <p>
          Tìm kiếm sản phẩm như một trang thương mại điện tử thông thường,
          sau đó nhận thưởng blockchain khi xem, mua, đánh giá.
        </p>
      </div>

      <SearchBar
        onSearch={onSearch}
        categories={categories}
        loading={loading}
        initialQuery={searchQuery}
      />

      {loading && <LoadingSpinner />}

      {searchResults && !loading && (
        <>
          <div className="result-meta">
            <span>
              <strong>{searchResults.total ?? searchResults.items?.length ?? 0}</strong> sản phẩm
              {searchResults.took_ms && (
                <span className="took"> ({searchResults.took_ms}ms)</span>
              )}
            </span>
          </div>

          <ProductGrid
            products={searchResults.items || []}
            onSelect={onSelectProduct}
            onViewDetail={onViewDetail}
            selectedProductId={selectedProduct?.product_id}
          />

          <div className="section-card" style={{ marginTop: 16 }}>
            <div className="section-title">Hành động blockchain cho sản phẩm đã chọn</div>
            <p style={{ marginBottom: 10, color: "var(--text-2)", fontSize: ".85rem" }}>
              Sản phẩm: <strong>{selectedProduct?.title || selectedProduct?.product_id || "Chưa chọn"}</strong>
            </p>

            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10, marginBottom: 10 }}>
              <input
                value={walletAddress}
                onChange={(e) => onWalletAddressChange(e.target.value)}
                placeholder="SUI wallet address (0x...)"
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
              />
              <input
                value={profileObjectId}
                onChange={(e) => onProfileObjectIdChange(e.target.value)}
                placeholder="Profile object ID (khuyến nghị điền khi chạy thật)"
                style={{ padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
              />
            </div>

            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 10 }}>
              <button className="run-btn" disabled={txLoading} onClick={() => onRewardAction("VIEWED")}>+10 điểm khi xem</button>
              <button className="run-btn" disabled={txLoading} onClick={() => onRewardAction("BOUGHT")}>+100 điểm khi mua + NFT</button>
              <button className="run-btn" disabled={txLoading} onClick={() => onRewardAction("REVIEWED")}>+50 điểm khi đánh giá</button>
              <button className="btn-secondary" disabled={txLoading} onClick={onRefreshWalletSummary}>Làm mới ví</button>
            </div>

            {txMessage && <div className="badge-info">{txMessage}</div>}

            {walletSummary && (
              <div style={{ marginTop: 10, fontSize: ".82rem", color: "var(--text-2)", display: "flex", gap: 12, flexWrap: "wrap" }}>
                <span>GREC: <strong style={{ color: "var(--acc)" }}>{walletSummary.grec_formatted || "0 GREC"}</strong></span>
                <span>NFT: <strong style={{ color: "var(--neo4j)" }}>{walletSummary.nft_count ?? 0}</strong></span>
                <span>Chế độ: <strong>{walletSummary.simulated ? "Demo" : "On-chain"}</strong></span>
              </div>
            )}
          </div>
        </>
      )}

      {!loading && !searchResults && (
        <BrowseDefault onBrowse={onBrowse} categories={categories} />
      )}
    </div>
  );
}

function LoadingSpinner() {
  return (
    <div className="spinner-wrap">
      <div className="spinner" />
      <p>Đang tìm kiếm...</p>
    </div>
  );
}

function BrowseDefault({ onBrowse, categories }) {
  return (
    <div className="browse-default">
      <h2>Khám phá theo danh mục</h2>
      <div className="cat-chips">
        {categories.slice(0, 24).map((c) => (
          <button key={c.category} className="cat-chip" onClick={() => onBrowse(c.category)}>
            {c.category}
          </button>
        ))}
      </div>
    </div>
  );
}
