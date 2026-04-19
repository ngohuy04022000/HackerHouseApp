export default function RewardsPage({
  health,
  walletAddress,
  walletSummary,
  onWalletAddressChange,
  onRefreshWalletSummary,
}) {
  return (
    <div>
      <div className="panel-header">
        <h2>Điểm thưởng Blockchain</h2>
        <p>
          Theo dõi trạng thái ví và pool thưởng SUI để vận hành chương trình loyalty.
        </p>
      </div>

      <div className="section-card">
        <div className="section-title">Trạng thái hệ thống</div>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          <span className={`badge-${health.neo4j ? "ok" : "err"}`}>Neo4j {health.neo4j ? "OK" : "Lỗi"}</span>
          <span className={`badge-${health.mysql ? "ok" : "err"}`}>MySQL {health.mysql ? "OK" : "Lỗi"}</span>
          <span className={`badge-${health.sui ? "ok" : "warn"}`}>SUI {health.sui ? "On-chain" : "Demo mode"}</span>
        </div>
      </div>

      <div className="section-card">
        <div className="section-title">Ví người dùng</div>
        <div style={{ display: "flex", gap: 8, marginBottom: 10 }}>
          <input
            value={walletAddress}
            onChange={(e) => onWalletAddressChange(e.target.value)}
            placeholder="Nhập địa chỉ ví SUI để xem số dư"
            style={{ flex: 1, padding: "10px 12px", borderRadius: 8, border: "1px solid var(--border-2)", background: "var(--bg)", color: "var(--text)", outline: "none" }}
          />
          <button className="run-btn" onClick={onRefreshWalletSummary}>Kiểm tra ví</button>
        </div>
        {walletSummary && (
          <div style={{ fontSize: ".85rem", color: "var(--text-2)", lineHeight: 1.7 }}>
            <div>GREC: <strong style={{ color: "var(--acc)" }}>{walletSummary.grec_formatted || "0 GREC"}</strong></div>
            <div>Product NFT: <strong style={{ color: "var(--neo4j)" }}>{walletSummary.nft_count ?? 0}</strong></div>
            <div>Score object: <strong>{walletSummary.recommend_score ? "Có" : "Chưa có"}</strong></div>
          </div>
        )}
      </div>
    </div>
  );
}
