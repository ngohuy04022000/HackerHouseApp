// frontend/src/components/QueryComparison.jsx
//
// So sánh truy vấn Neo4j vs MySQL từ 2-hop đến 5-hop.
// Mục tiêu: minh chứng trực quan ưu thế Graph DB với multi-hop queries.

import { useState } from "react";
import { api } from "../api";

// ─── Cấu hình các loại truy vấn ───────────────────────────────────────────────
const QUERY_TYPES = [
  {
    id:       "collaborative",
    label:    "Collaborative",
    hops:     2,
    advanced: false,
    desc:     "2-hop: User → Product ← User → Product",
    chain:    [["user","U"], ["product","P"], ["user","U'"], ["product","Rec"]],
  },
  {
    id:       "category",
    label:    "Category-based",
    hops:     3,
    advanced: false,
    desc:     "3-hop: User → Product → Category ← Product",
    chain:    [["user","U"], ["product","P"], ["category","C"], ["product","Rec"]],
  },
  {
    id:       "collab_4hop",
    label:    "4-hop Collab",
    hops:     4,
    advanced: true,
    desc:     "4-hop: User → P ← U1 → P ← U2 → Rec",
    chain:    [["user","U"], ["product","P"], ["user","U1"], ["product","P2"], ["user","U2"], ["product","Rec"]],
  },
  {
    id:       "brand_affinity",
    label:    "Brand Affinity",
    hops:     4,
    advanced: true,
    desc:     "4-hop: Tìm sản phẩm cùng thương hiệu mà user tương tự đã mua",
    chain:    [["user","U"], ["product","P (brand X)"], ["user","U'"], ["product","Rec (brand X)"]],
  },
  {
    id:       "cross_category",
    label:    "Cross-Category",
    hops:     5,
    advanced: true,
    desc:     "5-hop: Khám phá danh mục mới qua mạng lưới người dùng",
    chain:    [["user","U"], ["product","P"], ["category","C1"], ["product","P2"], ["user","U'"], ["product","Rec"], ["category","C2"]],
  },
  {
    id:       "influence_chain",
    label:    "Influence Chain",
    hops:     5,
    advanced: true,
    desc:     "5-hop: Gợi ý qua chuỗi ảnh hưởng 3 tầng người dùng",
    chain:    [["user","U"], ["product","P1"], ["user","U1"], ["product","P2"], ["user","U2"], ["product","P3"], ["user","U3"], ["product","Rec"]],
  },
  {
    id:       "search",
    label:    "Search",
    hops:     0,
    advanced: false,
    desc:     "Tìm kiếm theo từ khóa (tham khảo)",
    chain:    [],
  },
];

// Màu cho từng số hop
const HOP_COLORS = { 0: "#94A3B8", 2: "#00B4D8", 3: "#7C3AED", 4: "#EC4899", 5: "#F59E0B" };

// ─── Sub-components ────────────────────────────────────────────────────────────

// Chuỗi hop trực quan
function HopChain({ chain }) {
  if (!chain || chain.length === 0) return null;
  return (
    <div className="hop-chain">
      {chain.map(([type, label], i) => (
        <span key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
          {i > 0 && <span className="hop-arrow">→</span>}
          <span className={`hop-node ${type}`}>{label}</span>
        </span>
      ))}
    </div>
  );
}

// Badge số hop
function HopBadge({ hops }) {
  if (hops === 0) return <span className="hop-badge hop-2" style={{ color: "#94A3B8", background: "rgba(148,163,184,.12)", borderColor: "rgba(148,163,184,.2)" }}>Search</span>;
  return <span className={`hop-badge hop-${Math.min(hops, 5)}`}>{hops}-hop</span>;
}

// Metric đơn: số + nhãn + màu
function Metric({ val, label, bad }) {
  const cls = bad ? "red" : val === 0 ? "green" : "neutral";
  return (
    <div className="comp-metric">
      <span className={`comp-metric-val ${cls}`}>{val ?? "—"}</span>
      <span className="comp-metric-key">{label}</span>
    </div>
  );
}

// Hộp hiển thị kết quả một phía (Neo4j hoặc MySQL)
function QueryBox({ label, data, colorClass, mysqlRunnable }) {
  const [showCode, setShowCode] = useState(false);
  if (!data) return null;

  const isWinner = data.time_ms != null && data.time_ms <= (data._otherMs ?? 99999);
  const hasError = !!data.error;
  const isNA     = data.error && data.error.includes("KHÔNG THỂ");

  return (
    <div className={`query-box ${colorClass}`}>
      {/* Header */}
      <div className="qbox-header">
        <span className="qbox-title">{label}</span>
        {data.time_ms != null ? (
          <span className={`time-badge ${isWinner ? "winner" : ""}`}>
            {data.time_ms} ms{isWinner ? " (Nhanh nhất)" : ""}
          </span>
        ) : isNA ? (
          <span className="time-badge" style={{ background: "var(--bad-bg)", color: "var(--bad)" }}>
            N/A
          </span>
        ) : (
          <span className="time-badge">—</span>
        )}
      </div>

      {/* Complexity metrics */}
      {data.complexity && (
        <div className="complexity-block">
          <div className="complexity-title">Chỉ số độ phức tạp</div>
          <div className="comp-metrics">
            <Metric val={data.complexity.join_count     ?? 0} label="JOIN"      bad={data.complexity.join_count > 0} />
            <Metric val={data.complexity.subquery_count ?? 0} label="Subquery"  bad={data.complexity.subquery_count > 0} />
            <Metric val={data.complexity.hops           ?? 0} label="Hops"      bad={false} />
            <Metric val={data.complexity.code_lines     ?? "—"} label="Dòng code" bad={false} />
          </div>
          <p className="comp-note">{data.complexity.note}</p>
        </div>
      )}

      {/* Lỗi / N/A */}
      {hasError && (
        <div style={{ padding: "10px 14px", borderBottom: "1px solid var(--border)" }}>
          <div style={{
            background: isNA ? "rgba(239,68,68,.08)" : "var(--warn-bg)",
            border: `1px solid ${isNA ? "rgba(239,68,68,.2)" : "rgba(245,158,11,.2)"}`,
            borderRadius: 6, padding: "10px 12px",
            fontSize: ".8rem", color: isNA ? "var(--bad)" : "var(--warn)", lineHeight: 1.55,
          }}>
            {isNA ? "Cảnh báo: " : "Thông tin: "}{data.error}
          </div>
        </div>
      )}

      {/* Query code */}
      {data.query && (
        <div className="query-code-wrap">
          <button className="toggle-code" onClick={() => setShowCode(v => !v)}>
            {showCode ? "Ẩn query" : "Xem nội dung truy vấn"}
          </button>
          {showCode && <pre className="query-code">{data.query}</pre>}
        </div>
      )}

      {/* Result preview */}
      {!hasError && (
        <div className="result-preview">
          <div className="result-preview-title">Kết quả ({data.result_count} dòng)</div>
          {data.results && data.results.length > 0 ? (
            <table className="mini-table">
              <thead>
                <tr><th>#</th><th>Sản phẩm</th><th>Score/Rating</th></tr>
              </thead>
              <tbody>
                {data.results.slice(0, 5).map((r, i) => (
                  <tr key={i}>
                    <td>{i + 1}</td>
                    <td className="td-title">
                      {(r.title || "").substring(0, 54)}{(r.title?.length ?? 0) > 54 ? "…" : ""}
                    </td>
                    <td>{r.score ?? r.rating ?? "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="no-results">Không có kết quả — user chưa có lịch sử mua hàng.</p>
          )}
        </div>
      )}
    </div>
  );
}

// Thanh so sánh tốc độ
function SpeedupBar({ result }) {
  if (!result) return null;
  const { neo4j, mysql, speedup, winner, faster_name, slower_name, context_note, mysql_runnable } = result;
  const neo4jMs = neo4j?.time_ms ?? 0;
  const mysqlMs = mysql?.time_ms ?? null;
  const maxMs   = Math.max(neo4jMs, mysqlMs ?? 0, 1);

  return (
    <div className="speedup-section">
      <div className="speedup-title">So sánh tốc độ thực thi</div>
      <div className="speedup-bars">
        <div className="sbar-row">
          <span className="sbar-label neo4j">Neo4j</span>
          <div className="sbar-outer">
            <div className="sbar-inner neo4j" style={{ width: `${neo4jMs > 0 ? (neo4jMs / maxMs) * 100 : 5}%` }}>
              {neo4jMs} ms
            </div>
          </div>
        </div>
        <div className="sbar-row">
          <span className="sbar-label mysql">MySQL</span>
          <div className="sbar-outer">
            {mysqlMs != null ? (
              <div className="sbar-inner mysql" style={{ width: `${(mysqlMs / maxMs) * 100}%` }}>
                {mysqlMs} ms
              </div>
            ) : (
              <div style={{
                height: "100%", display: "flex", alignItems: "center",
                padding: "0 10px", color: "var(--bad)", fontSize: ".78rem", fontWeight: 700,
              }}>
                {mysql_runnable === false ? "N/A — không thể thực thi" : "Lỗi"}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Winner summary */}
      <div className={`speedup-winner ${winner === "neo4j" ? "neo4j-wins" : "mysql-wins"}`}>
        <div className="speedup-winner-title">Kết quả</div>
        <div className="speedup-winner-text">
          {mysqlMs != null && speedup != null ? (
            <><strong>{faster_name}</strong> nhanh hơn {slower_name} <strong>{speedup}×</strong></>
          ) : (
            <><strong>Neo4j</strong>: {neo4jMs}ms — MySQL <strong>không thể thực thi</strong> truy vấn này hiệu quả</>
          )}
        </div>
      </div>

      {/* Context */}
      {context_note && <div className="context-note">{context_note}</div>}
    </div>
  );
}

// ─── Main Component ────────────────────────────────────────────────────────────
export default function QueryComparison({ userId }) {
  const [type,    setType]    = useState("collaborative");
  const [searchQ, setSearchQ] = useState("LG");
  const [result,  setResult]  = useState(null);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState(null);
  const [lastRunAt, setLastRunAt] = useState(null);

  const selectedType = QUERY_TYPES.find(q => q.id === type);

  const run = async () => {
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const body = { user_id: userId, query_type: type };
      if (type === "search") body.search_term = searchQ;
      const d = await api.post("/compare/query", body);
      setResult(d);
      setLastRunAt(new Date());
    } catch (e) {
      setError(e.message || "Không kết nối được API.");
    } finally {
      setLoading(false);
    }
  };

  const clearResult = () => {
    setResult(null);
    setError(null);
  };

  if (result?.neo4j && result?.mysql) {
    result.neo4j._otherMs = result.mysql.time_ms;
    result.mysql._otherMs = result.neo4j.time_ms;
  }

  return (
    <div className="compare-panel">
      {/* Header */}
      <div className="panel-header">
        <h2>So sánh truy vấn: Neo4j vs MySQL</h2>
        <p>
          Cùng logic — chạy song song từ 2-hop đến 5-hop.
          Với các truy vấn phức tạp (4-5 hop), MySQL không thể thực thi hiệu quả trong thực tế.
        </p>
      </div>

      {/* Controls */}
      <div className="section-card">
        <div className="section-title">Chọn loại truy vấn</div>

        {/* Basic queries */}
        <div style={{ marginBottom: 6, fontSize: ".75rem", color: "var(--text-3)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px" }}>
          Truy vấn cơ bản
        </div>
        <div className="query-type-row" style={{ marginBottom: 12 }}>
          {QUERY_TYPES.filter(q => !q.advanced).map(q => (
            <button
              key={q.id}
              className={`qtype-btn ${type === q.id ? "active" : ""}`}
              onClick={() => setType(q.id)}
            >
              <span className="qtype-btn-label">{q.label}</span>
              <span className="qtype-btn-desc">{q.desc}</span>
              <HopBadge hops={q.hops} />
            </button>
          ))}
        </div>

        {/* Advanced queries */}
        <div style={{ marginBottom: 6, fontSize: ".75rem", color: "var(--hop4)", fontWeight: 700, textTransform: "uppercase", letterSpacing: ".6px" }}>
          Truy vấn nâng cao (4-5 hop) — MySQL không thể thực thi trong thực tế
        </div>
        <div className="query-type-row" style={{ marginBottom: 12 }}>
          {QUERY_TYPES.filter(q => q.advanced).map(q => (
            <button
              key={q.id}
              className={`qtype-btn advanced ${type === q.id ? "active" : ""}`}
              onClick={() => setType(q.id)}
            >
              <span className="qtype-btn-label">{q.label}</span>
              <span className="qtype-btn-desc">{q.desc}</span>
              <HopBadge hops={q.hops} />
            </button>
          ))}
        </div>

        {/* Hop chain visualization */}
        {selectedType && selectedType.chain.length > 0 && (
          <div style={{
            background: "var(--bg)", border: "1px solid var(--border)",
            borderRadius: 8, padding: "10px 14px", marginBottom: 12,
          }}>
            <div style={{ fontSize: ".72rem", color: "var(--text-3)", fontWeight: 700, marginBottom: 6, textTransform: "uppercase", letterSpacing: ".5px" }}>
              Luồng traversal
            </div>
            <HopChain chain={selectedType.chain} />
          </div>
        )}

        {type === "search" && (
          <input
            className="search-term-input"
            value={searchQ}
            onChange={e => setSearchQ(e.target.value)}
            placeholder="Từ khóa... (vd: LG , Daikin 1.5 Ton)"
          />
        )}

        <div className="compare-run-row">
          <div className="uid-label-wrap">
            <span className="uid-label">User: <strong>{userId}</strong></span>
            {lastRunAt && <span className="last-run">Lần chạy gần nhất: {lastRunAt.toLocaleTimeString("vi-VN")}</span>}
          </div>
          <div className="compare-actions">
            <button className="btn-secondary" onClick={clearResult} disabled={loading || (!result && !error)}>
              Xóa kết quả
            </button>
            <button className="run-btn" onClick={run} disabled={loading}>
              {loading ? "Đang chạy..." : "Chạy so sánh"}
            </button>
          </div>
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="spinner-wrap">
          <div className="spinner" />
          <p>Đang thực thi trên cả hai hệ thống...</p>
        </div>
      )}

      {/* Error */}
      {error && !loading && (
        <div className="badge-err" style={{ padding: "12px 16px", borderRadius: 10, flexDirection: "column", alignItems: "flex-start" }}>
          <strong>Lỗi kết nối</strong>
          <span style={{ marginTop: 4, fontWeight: 400 }}>{error}</span>
        </div>
      )}

      {/* Results */}
      {result && !loading && (
        <>
          <SpeedupBar result={result} />

          {result.result_alignment && (
            <div className="alignment-card">
              <div className="alignment-title">Mức độ tương đồng kết quả (Top-{result.result_alignment.topk})</div>
              <div className="alignment-grid">
                <div><strong>{result.result_alignment.neo4j_count}</strong><span>Neo4j items</span></div>
                <div><strong>{result.result_alignment.mysql_count}</strong><span>MySQL items</span></div>
                <div><strong>{result.result_alignment.overlap_count}</strong><span>Sản phẩm trùng</span></div>
                <div><strong>{result.result_alignment.overlap_ratio}%</strong><span>Tỷ lệ overlap</span></div>
              </div>
              <p className="alignment-note">
                {result?.data_consistency?.in_sync === false
                  ? `Cảnh báo: ${result?.data_consistency?.message}`
                  : "Hai truy vấn đã được chuẩn hóa để so sánh công bằng hơn (đồng bộ ORDER BY và tiêu chí text search)."}
              </p>
            </div>
          )}

          <div className="two-col">
            <QueryBox
              label="Neo4j — Cypher"
              data={result.neo4j}
              colorClass="neo4j"
              mysqlRunnable={result.mysql_runnable}
            />
            <QueryBox
              label="MySQL — SQL"
              data={result.mysql}
              colorClass="mysql"
              mysqlRunnable={result.mysql_runnable}
            />
          </div>

          {/* Analysis table */}
          <div className="analysis-block">
            <div className="analysis-title">Phân tích so sánh — {result.query_label}</div>
            <table className="analysis-table">
              <thead>
                <tr>
                  <th>Tiêu chí</th>
                  <th>Neo4j (Cypher)</th>
                  <th>MySQL (SQL)</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Thời gian thực thi</td>
                  <td className={result.neo4j.time_ms != null && (result.mysql.time_ms == null || result.neo4j.time_ms <= result.mysql.time_ms) ? "cell-good" : "cell-bad"}>
                    {result.neo4j.time_ms != null ? `${result.neo4j.time_ms} ms (OK)` : "Lỗi"}
                  </td>
                  <td className={result.mysql.time_ms == null ? "cell-bad" : result.mysql.time_ms < result.neo4j.time_ms ? "cell-good" : "cell-bad"}>
                    {result.mysql.time_ms != null ? `${result.mysql.time_ms} ms` : "N/A — không thể thực thi"}
                  </td>
                </tr>
                <tr>
                  <td>Số lượng JOIN</td>
                  <td className="cell-good">{result.neo4j.complexity?.join_count ?? 0} (0 JOIN)</td>
                  <td className={result.mysql.complexity?.join_count > 0 ? "cell-bad" : "cell-neutral"}>
                    {result.mysql.complexity?.join_count ?? "?"} phép JOIN
                  </td>
                </tr>
                <tr>
                  <td>Subquery lồng nhau</td>
                  <td className="cell-good">{result.neo4j.complexity?.subquery_count ?? 0}</td>
                  <td className={result.mysql.complexity?.subquery_count > 0 ? "cell-bad" : "cell-neutral"}>
                    {result.mysql.complexity?.subquery_count ?? "?"}
                  </td>
                </tr>
                <tr>
                  <td>Số dòng code</td>
                  <td className="cell-good">{result.neo4j.complexity?.code_lines ?? "—"} dòng</td>
                  <td className={result.mysql.complexity?.code_lines > result.neo4j.complexity?.code_lines ? "cell-bad" : "cell-neutral"}>
                    {result.mysql.complexity?.code_lines ?? "—"} dòng
                  </td>
                </tr>
                <tr>
                  <td>Cách mở rộng thêm 1 hop</td>
                  <td className="cell-good">Thêm 1 dòng MATCH</td>
                  <td className="cell-bad">Thêm 2–3 phép JOIN</td>
                </tr>
                <tr>
                  <td>Khả năng thực thi thực tế</td>
                  <td className="cell-good">Hỗ trợ mọi độ sâu</td>
                  <td className={result.mysql_runnable ? "cell-neutral" : "cell-bad"}>
                    {result.mysql_runnable ? "2-3 hop ổn định" : "4+ hop: time-out với data thực"}
                  </td>
                </tr>
                <tr className="conclusion-row">
                  <td>Kết luận</td>
                  <td colSpan={2}>{result.context_note}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}

      {/* Static complexity overview table */}
      <ComplexityOverview />
    </div>
  );
}

// Bảng tổng quan độ phức tạp tất cả loại truy vấn
function ComplexityOverview() {
  const rows = [
    { type: "2-hop Collaborative", n4j_joins: 0, sql_joins: 4,  n4j_sub: 0, sql_sub: 1, n4j_lines: 8,  sql_lines: 14, mysql_ok: true },
    { type: "3-hop Category",      n4j_joins: 0, sql_joins: 3,  n4j_sub: 0, sql_sub: 2, n4j_lines: 10, sql_lines: 20, mysql_ok: true },
    { type: "4-hop Collab",        n4j_joins: 0, sql_joins: 7,  n4j_sub: 0, sql_sub: 1, n4j_lines: 13, sql_lines: 26, mysql_ok: false },
    { type: "4-hop Brand Affinity",n4j_joins: 0, sql_joins: 6,  n4j_sub: 0, sql_sub: 1, n4j_lines: 11, sql_lines: 22, mysql_ok: false },
    { type: "5-hop Cross-Category",n4j_joins: 0, sql_joins: 9,  n4j_sub: 0, sql_sub: 1, n4j_lines: 14, sql_lines: 34, mysql_ok: false },
    { type: "5-hop Influence Chain",n4j_joins:0, sql_joins: 9,  n4j_sub: 0, sql_sub: 1, n4j_lines: 16, sql_lines: 28, mysql_ok: false },
  ];

  return (
    <div className="static-compare">
      <div className="static-compare-title">Tổng quan độ phức tạp theo số hop</div>
      <div className="table-scroll">
        <table className="big-compare-table">
          <thead>
            <tr>
              <th rowSpan={2} style={{ minWidth: 180 }}>Loại truy vấn</th>
              <th colSpan={3} className="cell-neo4j-header">Neo4j (Cypher)</th>
              <th colSpan={3} className="cell-mysql-header">MySQL (SQL)</th>
              <th rowSpan={2} style={{ minWidth: 110 }}>MySQL chạy được?</th>
            </tr>
            <tr>
              <th className="cell-neo4j-header">JOIN</th>
              <th className="cell-neo4j-header">Subquery</th>
              <th className="cell-neo4j-header">Dòng code</th>
              <th className="cell-mysql-header">JOIN</th>
              <th className="cell-mysql-header">Subquery</th>
              <th className="cell-mysql-header">Dòng code</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i}>
                <td><strong>{r.type}</strong></td>
                <td className="cell-good">{r.n4j_joins}</td>
                <td className="cell-good">{r.n4j_sub}</td>
                <td className="cell-good">{r.n4j_lines}</td>
                <td className={r.sql_joins > 4 ? "cell-bad" : r.sql_joins > 0 ? "" : "cell-good"}>{r.sql_joins}</td>
                <td className={r.sql_sub > 1 ? "cell-bad" : r.sql_sub > 0 ? "" : "cell-good"}>{r.sql_sub}</td>
                <td className={r.sql_lines > 20 ? "cell-bad" : ""}>{r.sql_lines}</td>
                <td style={{ fontWeight: 700, color: r.mysql_ok ? "var(--good)" : "var(--bad)" }}>
                  {r.mysql_ok ? "Có" : "Time-out"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="table-note" style={{ marginTop: 14 }}>
        <strong>Kết luận cốt lõi:</strong>{" "}
        Neo4j luôn cần <strong>0 JOIN</strong> bất kể số hop.
        Thêm 1 hop = thêm 1 dòng MATCH trong Cypher.
        MySQL: mỗi hop thêm 2–3 JOIN. Từ 4-hop trở lên, truy vấn SQL gần như không thể
        bảo trì và không thể thực thi hiệu quả với dữ liệu thực tế.
        Đây là ưu thế <strong>bản chất</strong> của CSDL đồ thị.
      </div>
    </div>
  );
}
