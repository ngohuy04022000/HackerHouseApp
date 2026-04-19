import { useState, useEffect } from "react";
import SearchBar from "./components/SearchBar";
import ProductGrid from "./components/ProductGrid";
import RecommendPanel from "./components/RecommendPanel";
import QueryComparison from "./components/QueryComparison";
import BenchmarkChart from "./components/BenchmarkChart";
import Sidebar from "./components/Sidebar";
import { api } from "./api";
import SuiPanel from "./components/SuiPanel";

const TABS = [
  { id: "search", label: "Tìm kiếm" },
  { id: "recommend", label: "Gợi ý" },
  { id: "compare", label: "So sánh Query" },
  { id: "benchmark", label: "Benchmark" },
  { id: "sui", label: "SUI Blockchain" },
];

export default function App() {
  const [tab, setTab] = useState("search");
  const [searchQuery, setQuery] = useState("");
  const [searchResults, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState("U0001");
  const [users, setUsers] = useState([]);
  const [categories, setCats] = useState([]);
  const [health, setHealth] = useState({});
  const [filterCat, setFilterCat] = useState("");

  useEffect(() => {
    api.get("/health").then(setHealth).catch(() => { });
    api.get("/users?limit=50").then(setUsers).catch(() => { });
    api.get("/categories").then(setCats).catch(() => { });
  }, []);

  const handleSearch = async (q, cat) => {
    if (!q.trim()) return;
    setLoading(true);
    setQuery(q);
    try {
      const params = new URLSearchParams({ q, size: 24 });
      if (cat) params.append("category", cat);
      const data = await api.get(`/search?${params}`);
      setResults(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleBrowse = async (cat) => {
    setLoading(true);
    setFilterCat(cat);
    setTab("search");
    try {
      const params = new URLSearchParams({ size: 24 });
      if (cat) params.append("category", cat);
      const data = await api.get(`/products?${params}`);
      setResults({
        engine: "mysql_browse",
        total: data.total,
        items: data.items,
        query: cat || "Tất cả sản phẩm",
      });
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      {/* ── Header ─────────────────────────────────── */}
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <div>
              <h1>GraphRec</h1>
              <p>Neo4j · MySQL · Elasticsearch</p>
            </div>
          </div>

          <nav className="tab-nav">
            {TABS.map(t => (
              <button
                key={t.id}
                className={`tab-btn ${tab === t.id ? "active" : ""}`}
                onClick={() => setTab(t.id)}
              >
                {t.label}
              </button>
            ))}
          </nav>

          <div className="header-status">
            <StatusDot label="Neo4j" ok={health.neo4j} />
            <StatusDot label="MySQL" ok={health.mysql} />
            <StatusDot label="ES" ok={health.elastic} />
          </div>
        </div>
      </header>

      {/* ── Body ───────────────────────────────────── */}
      <div className="app-body">
        <Sidebar
          categories={categories}
          users={users}
          userId={userId}
          onUserChange={setUserId}
          onCategoryClick={handleBrowse}
          activeCategory={filterCat}
        />

        <main className="main-content">
          {tab === "search" && (
            <div>
              <SearchBar
                onSearch={handleSearch}
                categories={categories}
                loading={loading}
                initialQuery={searchQuery}
              />
              {loading && <LoadingSpinner />}
              {searchResults && !loading && (
                <>
                  <div className="result-meta">
                    <span>
                      {searchResults.engine === "elasticsearch" ? "Elasticsearch"
                        : searchResults.engine === "mysql_fulltext" ? "MySQL FULLTEXT"
                          : "Browse"}
                      {" — "}<strong>{searchResults.total ?? searchResults.items?.length ?? 0}</strong> kết quả
                      {searchResults.took_ms && (
                        <span className="took"> ({searchResults.took_ms}ms)</span>
                      )}
                    </span>
                  </div>
                  <ProductGrid products={searchResults.items || []} />
                </>
              )}
              {!loading && !searchResults && (
                <BrowseDefault onBrowse={handleBrowse} categories={categories} />
              )}
            </div>
          )}

          {tab === "recommend" && <RecommendPanel userId={userId} />}
          {tab === "compare" && <QueryComparison userId={userId} />}
          {tab === "benchmark" && <BenchmarkChart userId={userId} />}
          {tab === "sui" && <SuiPanel userId={userId} />}
        </main>
      </div>
    </div>
  );
}

function StatusDot({ label, ok }) {
  return (
    <span className={`status-dot ${ok ? "ok" : "err"}`}>
      <span className="dot" /> {label}
    </span>
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
        {categories.slice(0, 24).map(c => (
          <button key={c.category} className="cat-chip" onClick={() => onBrowse(c.category)}>
            {c.category}
          </button>
        ))}
      </div>
    </div>
  );
}
