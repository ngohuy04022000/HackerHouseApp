import { useEffect, useState } from "react";
import { Route, Routes, useNavigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import { api } from "./api";
import RecommendPanel from "./components/RecommendPanel";
import ProductDetailPage from "./pages/ProductDetailPage";
import ShopPage from "./pages/ShopPage";
import RewardsPage from "./pages/RewardsPage";

const TABS = [
  { id: "shop", label: "Cửa hàng" },
  { id: "recommend", label: "Đề xuất" },
  { id: "rewards", label: "Điểm thưởng Blockchain" },
];

export default function App() {
  const navigate = useNavigate();
  const [tab, setTab] = useState("shop");
  const [searchQuery, setQuery] = useState("");
  const [searchResults, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [userId, setUserId] = useState(localStorage.getItem("gh_user_id") || "U0001");
  const [users, setUsers] = useState([]);
  const [categories, setCats] = useState([]);
  const [health, setHealth] = useState({});
  const [filterCat, setFilterCat] = useState("");
  const [selectedProduct, setSelectedProduct] = useState(null);
  const [walletAddress, setWalletAddress] = useState(localStorage.getItem("gh_wallet") || "");
  const [profileObjectId, setProfileObjectId] = useState(localStorage.getItem("gh_profile_id") || "");
  const [walletSummary, setWalletSummary] = useState(null);
  const [txMessage, setTxMessage] = useState("");
  const [txLoading, setTxLoading] = useState(false);

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
    setTab("shop");
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
      setSelectedProduct((data.items || [])[0] || null);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const refreshWalletSummary = async () => {
    if (!walletAddress.trim()) {
      setWalletSummary(null);
      return;
    }
    try {
      const d = await api.get(`/sui/wallet/${walletAddress.trim()}`);
      setWalletSummary(d);
      if (d?.default_profile_object_id && !profileObjectId.trim()) {
        setProfileObjectId(d.default_profile_object_id);
      }
    } catch (e) {
      setWalletSummary(null);
      setTxMessage(`Không đọc được ví: ${e.message}`);
    }
  };

  const rewardAction = async (action) => {
    if (!selectedProduct) {
      setTxMessage("Hãy chọn sản phẩm trước khi thao tác.");
      return;
    }
    if (!walletAddress.trim()) {
      setTxMessage("Hãy nhập địa chỉ ví SUI.");
      return;
    }

    setTxLoading(true);
    setTxMessage("");
    try {
      const rewardRes = await api.post("/sui/reward", {
        recipient_address: walletAddress.trim(),
        profile_object_id: profileObjectId.trim(),
        product_id: selectedProduct.product_id,
        action,
      });

      if (action === "BOUGHT") {
        await api.post("/sui/mint-nft", {
          recipient_address: walletAddress.trim(),
          product_id: selectedProduct.product_id,
          name: selectedProduct.title || selectedProduct.name || selectedProduct.product_id,
          description: `Đơn mua từ GraphRec Commerce - ${new Date().toLocaleDateString("vi-VN")}`,
          image_url: selectedProduct.image_url || "",
          brand: selectedProduct.brand || "",
          category: selectedProduct.category || selectedProduct.sub_category || "",
          price_grec: 100000000,
          rating: Math.round((Number(selectedProduct.rating) || 0) * 10),
        });
      }

      setTxMessage(
        `${action} thành công${rewardRes?.grec_amount ? `, +${rewardRes.grec_amount} GREC` : ""}.`
      );
      await refreshWalletSummary();
    } catch (e) {
      setTxMessage(`Giao dịch lỗi: ${e.message}`);
    } finally {
      setTxLoading(false);
    }
  };

  useEffect(() => {
    if (!searchResults?.items?.length) return;
    setSelectedProduct(searchResults.items[0]);
  }, [searchResults]);

  useEffect(() => {
    localStorage.setItem("gh_user_id", userId || "");
  }, [userId]);

  useEffect(() => {
    localStorage.setItem("gh_wallet", walletAddress || "");
  }, [walletAddress]);

  useEffect(() => {
    localStorage.setItem("gh_profile_id", profileObjectId || "");
  }, [profileObjectId]);

  const homePage = (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-inner">
          <div className="logo">
            <div>
              <h1>GraphRec Commerce</h1>
              <p>E-commerce + Recommendation + SUI Rewards</p>
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
          {tab === "shop" && (
            <ShopPage
              searchQuery={searchQuery}
              searchResults={searchResults}
              loading={loading}
              categories={categories}
              selectedProduct={selectedProduct}
              walletAddress={walletAddress}
              profileObjectId={profileObjectId}
              walletSummary={walletSummary}
              txMessage={txMessage}
              txLoading={txLoading}
              onSearch={handleSearch}
              onBrowse={handleBrowse}
              onSelectProduct={setSelectedProduct}
              onViewDetail={(product) => navigate(`/product/${product.product_id}`)}
              onWalletAddressChange={setWalletAddress}
              onProfileObjectIdChange={setProfileObjectId}
              onRewardAction={rewardAction}
              onRefreshWalletSummary={refreshWalletSummary}
            />
          )}

          {tab === "recommend" && <RecommendPanel userId={userId} />}

          {tab === "rewards" && (
            <RewardsPage
              health={health}
              walletAddress={walletAddress}
              walletSummary={walletSummary}
              onWalletAddressChange={setWalletAddress}
              onRefreshWalletSummary={refreshWalletSummary}
            />
          )}
        </main>
      </div>
    </div>
  );

  return (
    <Routes>
      <Route path="/" element={homePage} />
      <Route
        path="/product/:productId"
        element={
          <ProductDetailPage
            userId={userId}
            walletAddress={walletAddress}
            profileObjectId={profileObjectId}
            setWalletAddress={setWalletAddress}
            setProfileObjectId={setProfileObjectId}
          />
        }
      />
    </Routes>
  );
}

function StatusDot({ label, ok }) {
  return (
    <span className={`status-dot ${ok ? "ok" : "err"}`}>
      <span className="dot" /> {label}
    </span>
  );
}
