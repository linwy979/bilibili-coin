import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";
import TrendChart from "./TrendChart";
import { formatPrice } from "./format";

export default function PriceSearch() {
  const navigate = useNavigate();
  const [coinList, setCoinList] = useState([]);
  const [selectedCoin, setSelectedCoin] = useState("");
  const [selectedRange, setSelectedRange] = useState("1d");
  const [chartData, setChartData] = useState([]);
  const [coinPrice, setCoinPrice] = useState(null);
  const [followedCoins, setFollowedCoins] = useState([]);

  // ✅ 取得幣種列表
  useEffect(() => {
    fetch("/api/current_prices", { credentials: "include" })
      .then(res => res.json())
      .then(data => setCoinList(data))
      .catch(err => console.error("取得幣價失敗：", err));
  }, []);

  // ✅ 取得使用者追蹤的幣種
  useEffect(() => {
    fetch("/follow_list", { credentials: "include" })
      .then(res => res.json())
      .then(data => {
        const tracked = data.tracked?.map(c => c.coin_id) || [];
        setFollowedCoins(tracked);
      })
      .catch(err => console.error("取得追蹤清單失敗：", err));
  }, []);

  // ✅ 選擇幣種與區間時，取得趨勢圖與即時價格
  useEffect(() => {
    if (!selectedCoin) return;

    const coin = coinList.find(c => c.coin_id === selectedCoin);
    setCoinPrice(coin?.price || null);

    fetch(`/api/price_history/${selectedCoin}?type=${selectedRange}`, { credentials: "include" })
      .then(res => res.json())
      .then(data => setChartData(Array.isArray(data) ? data : []))
      .catch(err => {
        console.error("取得趨勢圖資料失敗：", err);
        setChartData([]);
      });
  }, [selectedCoin, selectedRange, coinList]);

  // ✅ 加入追蹤
  async function handleAddFollow() {
    if (!selectedCoin) return;
    const res = await fetch("/follow_list", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ action: "add", coin_id: selectedCoin }),
      credentials: "include",
    });
    if (res.ok) {
      setFollowedCoins(prev => [...prev, selectedCoin]);
    } else {
      alert("❌ 加入追蹤失敗！");
    }
  }

  return (
    <div className="crypto-glass price-search" style={{ maxWidth: 480, margin: "0 auto", padding: "0 16px", boxSizing: "border-box" }}>
      <button className="glass-btn" style={{ marginBottom: 16 }} onClick={() => navigate("/")}>
        回到主頁
      </button>
      <h1 className="title2">即時幣價查詢</h1>

      <div className="add-coin-row" style={{ marginBottom: 20 }}>
        <select
          className="coin-select"
          value={selectedCoin}
          onChange={(e) => setSelectedCoin(e.target.value)}
        >
          <option value="">請選擇幣種</option>
          {coinList.map((coin) => (
            <option key={coin.coin_id} value={coin.coin_id}>
              {coin.coin_id}
            </option>
          ))}
        </select>
      </div>

      {/* ✅ 改成跟追蹤清單一致的按鈕樣式 */}
      <div style={{ display: "flex", gap: 12, marginBottom: 18 }}>
        {["1d", "3d", "7d"].map(r => (
          <button
            key={r}
            className="glass-btn"
            style={{
              padding: "6px 0",
              width: "auto",
              flex: 1,
              margin: 0,
              background: selectedRange === r ? "#5ee7ff" : "transparent",
              color: selectedRange === r ? "#000" : "#ccc",
              border: "1px solid #5ee7ff",
              borderRadius: 6,
              cursor: "pointer",
              fontWeight: "bold"
            }}
            onClick={() => setSelectedRange(r)}
          >
            {r === "1d" ? "1天" : r === "3d" ? "3天" : "7天"}
          </button>
        ))}
      </div>

      {selectedCoin && (
        <>
          <div style={{ color: "#ccc", marginBottom: 10 }}>
            📌 幣種：<strong>{selectedCoin}</strong>，即時價格：<strong>${formatPrice(coinPrice)}</strong>
          </div>

          {followedCoins.includes(selectedCoin) ? (
            <div style={{ color: "#5ee7ff", fontWeight: "bold", marginBottom: 10 }}>
              ✅ 已加入追蹤
            </div>
          ) : (
            <button className="add-btn" onClick={handleAddFollow}>加入追蹤</button>
          )}

          <TrendChart history={chartData} />
        </>
      )}
    </div>
  );
}
