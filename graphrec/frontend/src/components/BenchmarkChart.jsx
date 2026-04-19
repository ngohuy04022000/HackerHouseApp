import { useState } from "react";
import { api } from "../api";

// Màu theo số hop
const HOP_COLOR = { 2: "#00B4D8", 3: "#7C3AED", 4: "#EC4899", 5: "#F59E0B" };

// Complexity reference table (static, không cần API)
const COMPLEXITY_REF = [
  {
    type:  "2-hop Collaborative",
    hops:  2,
    n4j_joins: 0, sql_joins: 4,
    n4j_sub:   0, sql_sub:   1,
    n4j_lines: 8, sql_lines: 14,
    mysql_ok:  true,
    note: "MySQL hoạt động tốt với 2-hop đơn giản nhờ B-tree index. Neo4j nhanh hơn nhờ pointer-based traversal.",
  },
  {
    type:  "3-hop Category",
    hops:  3,
    n4j_joins: 0, sql_joins: 3,
    n4j_sub:   0, sql_sub:   2,
    n4j_lines: 10, sql_lines: 20,
    mysql_ok:  true,
    note: "SQL cần inline view + NOT EXISTS. Neo4j thêm 1 mệnh đề MATCH. Khoảng cách bắt đầu rõ.",
  },
  {
    type:  "4-hop Collab (2nd-level)",
    hops:  4,
    n4j_joins: 0, sql_joins: 7,
    n4j_sub:   0, sql_sub:   1,
    n4j_lines: 13, sql_lines: 26,
    mysql_ok:  false,
    note: "7 JOIN. MySQL: gần như không thể tối ưu với dataset thực tế. Neo4j: chỉ thêm 2 dòng MATCH.",
  },
  {
    type:  "4-hop Brand Affinity",
    hops:  4,
    n4j_joins: 0, sql_joins: 6,
    n4j_sub:   0, sql_sub:   1,
    n4j_lines: 11, sql_lines: 22,
    mysql_ok:  false,
    note: "6 JOIN + 2 alias bảng products. Neo4j lọc thuộc tính brand trực tiếp — không JOIN thêm.",
  },
  {
    type:  "5-hop Cross-Category",
    hops:  5,
    n4j_joins: 0, sql_joins: 9,
    n4j_sub:   0, sql_sub:   1,
    n4j_lines: 14, sql_lines: 34,
    mysql_ok:  false,
    note: "9 JOIN + self-join products 3 lần. Không thể thực thi hiệu quả. Neo4j: 14 dòng Cypher tự nhiên.",
  },
  {
    type:  "5-hop Influence Chain",
    hops:  5,
    n4j_joins: 0, sql_joins: 9,
    n4j_sub:   0, sql_sub:   1,
    n4j_lines: 16, sql_lines: 28,
    mysql_ok:  false,
    note: "9 alias bảng actions. Optimizer MySQL không thể tối ưu. Đây là trường hợp Neo4j wins tuyệt đối.",
  },
];

// Bar đơn
function Bar({ label, value, max, colorClass }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 5;
  return (
    <div className="bench-bar-row">
      <span className="bench-label">{label}</span>
      <div className="bench-bar-outer">
        <div className={`bench-bar-inner ${colorClass}`} style={{ width: `${pct}%` }}>
          {value} ms
        </div>
      </div>
    </div>
  );
}

// Card kết quả một loại truy vấn
function MetricCard({ qkey, data }) {
  if (!data) return null;
  const { label, hops, neo4j, mysql, speedup, winner, faster_name, mysql_runnable, neo4j_code_lines, mysql_code_lines, neo4j_joins, mysql_joins } = data;

  const hasNeo4jTime  = neo4j && !neo4j.error && neo4j.avg_ms != null;
  const hasMysqlTime  = mysql && !mysql.na && !mysql.error && mysql.avg_ms != null;
  const maxMs = Math.max(hasNeo4jTime ? neo4j.avg_ms : 0, hasMysqlTime ? mysql.avg_ms : 0, 1);
  const hopColor = HOP_COLOR[hops] || "#94A3B8";

  return (
    <div className="bench-card" style={{ borderTop: `3px solid ${hopColor}` }}>
      {/* Title + hop badge */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
        <div className="bench-card-title">{label}</div>
        {hops > 0 && (
          <span className={`hop-badge hop-${Math.min(hops, 5)}`}>{hops}-hop</span>
        )}
      </div>

      {/* Winner or N/A */}
      {hasMysqlTime && speedup ? (
        <div className={`bench-winner-badge ${winner}`}>
          {faster_name} nhanh hơn {speedup}×
        </div>
      ) : !mysql_runnable ? (
        <div className="bench-winner-badge neo4j" style={{ background: "rgba(236,72,153,.1)", color: "var(--hop4)", borderColor: "rgba(236,72,153,.25)" }}>
          MySQL không thể thực thi
        </div>
      ) : null}

      {/* Bars */}
      <div className="bench-bars">
        {hasNeo4jTime ? (
          <Bar label="Neo4j avg" value={neo4j.avg_ms} max={maxMs} colorClass="neo4j" />
        ) : (
          <div className="bench-bar-row">
            <span className="bench-label">Neo4j</span>
            <div style={{ fontSize: ".78rem", color: "var(--bad)", paddingLeft: 4 }}>Lỗi: {neo4j?.error}</div>
          </div>
        )}
        {hasMysqlTime ? (
          <Bar label="MySQL avg" value={mysql.avg_ms} max={maxMs} colorClass="mysql" />
        ) : (
          <div className="bench-bar-row">
            <span className="bench-label" style={{ color: "var(--text-3)" }}>MySQL</span>
            <div style={{ flex: 1, background: "var(--surface-2)", borderRadius: 5, height: 26, display: "flex", alignItems: "center", paddingLeft: 10 }}>
              <span style={{ fontSize: ".76rem", color: mysql_runnable ? "var(--bad)" : "var(--mysql)", fontWeight: 700 }}>
                {mysql_runnable ? (mysql?.error || "Lỗi") : `N/A — ${mysql?.reason?.substring(0, 60)}...`}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Stats grid */}
      {hasNeo4jTime && (
        <div className="bench-stats">
          <div className="bench-stat-group">
            <span className="bench-db-badge neo4j">Neo4j</span>
            <span>min: {neo4j.min_ms}ms</span>
            <span>p50: {neo4j.p50_ms}ms</span>
            <span>p95: {neo4j.p95_ms}ms</span>
          </div>
          {hasMysqlTime && (
            <div className="bench-stat-group">
              <span className="bench-db-badge mysql">MySQL</span>
              <span>min: {mysql.min_ms}ms</span>
              <span>p50: {mysql.p50_ms}ms</span>
              <span>p95: {mysql.p95_ms}ms</span>
            </div>
          )}
        </div>
      )}

      {/* Code complexity comparison */}
      {neo4j_code_lines && (
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr",
          gap: 8, padding: "8px 10px",
          background: "var(--surface-2)", borderRadius: 6, fontSize: ".76rem",
        }}>
          <div style={{ color: "var(--neo4j)" }}>
            <strong>Neo4j:</strong> {neo4j_code_lines} dòng / {neo4j_joins ?? 0} JOIN
          </div>
          <div style={{ color: mysql_runnable ? "var(--text-2)" : "var(--bad)" }}>
            <strong>MySQL:</strong> {mysql_code_lines} dòng / {mysql_joins ?? "?"} JOIN
            {!mysql_runnable && " (Cảnh báo)"}
          </div>
        </div>
      )}

      {/* Speedup or N/A explanation */}
      {hasMysqlTime && speedup ? (
        <div className={`bench-speedup ${winner}`}>
          <strong>{faster_name}</strong> nhanh hơn <strong>{speedup}×</strong>
        </div>
      ) : !mysql_runnable && (
        <div className="bench-speedup neo4j" style={{ background: "rgba(236,72,153,.08)", color: "var(--hop4)", borderColor: "rgba(236,72,153,.2)", fontSize: ".78rem" }}>
          MySQL không thể thực thi truy vấn {hops}-hop trong thực tế.
          Neo4j là lựa chọn duy nhất khả thi.
        </div>
      )}
    </div>
  );
}

// Main component
export default function BenchmarkChart({ userId }) {
  const [result,  setResult]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [iters,   setIters]   = useState(10);
  const [error,   setError]   = useState(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await api.get(`/benchmark/run?user_id=${userId}&iterations=${iters}`);
      setResult(d);
    } catch (e) {
      setError(e.message || "Lỗi kết nối API.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="benchmark-panel">
      {/* Header */}
      <div className="panel-header">
        <h2>Benchmark: Neo4j vs MySQL — 2-hop đến 5-hop</h2>
        <p>
          Chạy mỗi loại truy vấn N lần, đo avg/min/max/p95.
          Truy vấn 4-hop+ trên MySQL trả về "N/A — không thể thực thi hiệu quả".
        </p>
      </div>

      {/* Info panel */}
      <div className="api-info-panel">
        <strong>Giải thích benchmark:</strong>
        <div className="api-param-list">
          <div className="api-param-item">
            <span className="api-param-key">avg_ms</span>
            <span className="api-param-desc">Thời gian trung bình — chỉ số so sánh chính giữa hai DB</span>
          </div>
          <div className="api-param-item">
            <span className="api-param-key">p95_ms</span>
            <span className="api-param-desc">95% requests hoàn thành trong khoảng thời gian này — phản ánh trường hợp xấu nhất</span>
          </div>
          <div className="api-param-item">
            <span className="api-param-key">N/A</span>
            <span className="api-param-desc">MySQL không thể thực thi truy vấn này hiệu quả — sẽ time-out hoặc hết RAM với data thực</span>
          </div>
        </div>
      </div>

      {/* Controls */}
      <div className="section-card bench-controls">
        <label>
          Số lần chạy:
          <select value={iters} onChange={e => setIters(Number(e.target.value))}>
            {[5, 10, 20, 50].map(n => <option key={n} value={n}>{n} lần</option>)}
          </select>
        </label>
        <span className="uid-label">User: <strong>{userId}</strong></span>
        <button className="run-btn" onClick={run} disabled={loading}>
          {loading ? `Đang chạy ${iters}× mỗi loại...` : "Bắt đầu benchmark"}
        </button>
      </div>

      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <p>Đang chạy benchmark... (có thể mất 30-60 giây)</p>
        </div>
      )}

      {error && !loading && (
        <div className="badge-err" style={{ padding: "12px 16px", borderRadius: 10 }}>
          {error}
        </div>
      )}

      {/* Live results */}
      {result && !loading && (
        <div className="section-card">
          <div className="section-title">
            Kết quả sau {result.iterations} lần chạy — user {result.user_id}
          </div>

          {/* Summary */}
          {result.summary && (
            <div className="badge-info" style={{ marginBottom: 14, fontSize: ".83rem" }}>
              {result.summary.note}
            </div>
          )}

          {/* Cards grid */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
            {Object.entries(result.results).map(([key, data]) => (
              <MetricCard key={key} qkey={key} data={data} />
            ))}
          </div>
        </div>
      )}

      {/* Static complexity table — always visible */}
      <div className="static-compare">
        <div className="static-compare-title">Bảng so sánh độ phức tạp (phân tích tĩnh)</div>
        <div className="table-scroll">
          <table className="compare-table">
            <thead>
              <tr>
                <th rowSpan={2}>Loại truy vấn</th>
                <th colSpan={3} className="cell-neo4j-header">Neo4j (Cypher)</th>
                <th colSpan={3} className="cell-mysql-header">MySQL (SQL)</th>
                <th rowSpan={2}>Thực thi được?</th>
              </tr>
              <tr>
                <th className="cell-neo4j-header">JOIN</th>
                <th className="cell-neo4j-header">Subq.</th>
                <th className="cell-neo4j-header">Dòng</th>
                <th className="cell-mysql-header">JOIN</th>
                <th className="cell-mysql-header">Subq.</th>
                <th className="cell-mysql-header">Dòng</th>
              </tr>
            </thead>
            <tbody>
              {COMPLEXITY_REF.map((r, i) => (
                <tr key={i}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                      <span style={{
                        width: 10, height: 10, borderRadius: "50%", flexShrink: 0,
                        background: HOP_COLOR[r.hops] || "#94A3B8",
                      }} />
                      <strong>{r.type}</strong>
                    </div>
                  </td>
                  <td className="cell-good">{r.n4j_joins}</td>
                  <td className="cell-good">{r.n4j_sub}</td>
                  <td className="cell-good">{r.n4j_lines}</td>
                  <td className={r.sql_joins > 5 ? "cell-bad" : r.sql_joins > 0 ? "" : "cell-good"}>{r.sql_joins}</td>
                  <td className={r.sql_sub > 1 ? "cell-bad" : ""}>{r.sql_sub}</td>
                  <td className={r.sql_lines > 25 ? "cell-bad" : ""}>{r.sql_lines}</td>
                  <td style={{ fontWeight: 700, color: r.mysql_ok ? "var(--good)" : "var(--bad)", whiteSpace: "nowrap" }}>
                    {r.mysql_ok ? "MySQL OK" : "Time-out"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Notes */}
        {COMPLEXITY_REF.map((r, i) => (
          <div key={i} className="table-note" style={{ marginTop: i === 0 ? 14 : 5 }}>
            <strong>{r.type}:</strong> {r.note}
          </div>
        ))}

        <div className="table-note" style={{ marginTop: 10, borderLeftColor: "var(--hop4)" }}>
          <strong>Kết luận:</strong>{" "}
          Từ 4-hop trở lên, SQL trở nên gần như không thể viết và bảo trì.
          MySQL về cơ bản không thể thực thi hiệu quả 4-hop+ với dataset thực tế.
          Neo4j luôn cần 0 JOIN bất kể số hop — đây là ưu thế <strong>bản chất</strong>.
        </div>
      </div>
    </div>
  );
}
