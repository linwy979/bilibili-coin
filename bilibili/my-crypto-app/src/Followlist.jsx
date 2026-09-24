import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";
import TrendChart from "./TrendChart";
import { formatPrice } from "./format";

export default function FollowList() {
  const [followList, setFollowList] = useState([]);
  const [showChartId, setShowChartId] = useState(null);
  const [addCoin, setAddCoin] = useState("");
  const navigate = useNavigate();
  const [selectedRange, setSelectedRange] = useState("1d");
  const [allCoins, setAllCoins] = useState([]);

  useEffect(() => {
    fetch("/api/coin_list", { credentials: "include" })
      .then(res => res.json())
      .then(data => {
        const mapped = data.map(c => ({ id: c.coin_id, name: c.coin_name }));
        setAllCoins(mapped);
      });
  }, []);

  useEffect(() => {
    fetch("/follow_list", { credentials: "include" })
      .then(res => res.json())
      .then(data => {
        const trackedCoins = data.tracked || [];
        return Promise.all(trackedCoins.map(coin =>
          fetch(`/api/price_history/${coin.coin_id}?type=${selectedRange}`, { credentials: "include" })
            .then(res => res.json())
            .then(history => ({
              id: coin.coin_id,
              price: coin.price,
              history: Array.isArray(history) ? history : []
            }))
            .catch(() => ({ id: coin.coin_id, price: coin.price, history: [] }))
        ));
      })
      .then(coinData => {
        setFollowList(coinData);
        setShowChartId(null);
      })
      .catch(err => console.error("fetch follow list 發生錯誤：", err));
  }, [selectedRange]);

  async function handleAddCoin() {
    if (!addCoin || followList.some(c => c.id === addCoin)) return;
    const res = await fetch("/follow_list", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ action: "add", coin_id: addCoin }),
      credentials: "include"
    });
    if (res.ok) window.location.reload();
  }

  async function handleRemoveCoin(coinId) {
    const res = await fetch("/follow_list", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ action: "remove", coin_id: coinId }),
      credentials: "include"
    });
    if (res.ok) window.location.reload();
  }

  return (
    <div className="crypto-glass follow-list">
      <button className="glass-btn" style={{ marginBottom: 10, width: "fit-content", padding: "9px 30px" }} onClick={() => navigate("/")}>回到主頁面</button>
      <h1 className="title2">追蹤清單</h1>
      <div style={{ display: "flex", gap: 12, margin: "8px 0 18px 0" }}>
        {["1d", "3d", "7d"].map(r => (
          <button key={r} className="glass-btn" style={{
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
          }} onClick={() => setSelectedRange(r)}>
            {r === "1d" ? "1天" : r === "3d" ? "3天" : "7天"}
          </button>
        ))}
      </div>

      <div className="coin-list">
        {followList.map(coin => (
          <div className="coin-row" key={coin.id} style={{ flexDirection: "column", alignItems: "flex-start" }}>
            <div style={{ display: "flex", alignItems: "center", width: "100%", gap: 12 }}>
              <span className="coin-id">{coin.id}</span>
              <span className="coin-price">${formatPrice(coin.price)}</span>
              <button className="trend-btn" onClick={() => setShowChartId(showChartId === coin.id ? null : coin.id)}>
                {showChartId === coin.id ? "收起" : "趨勢圖"}
              </button>
              <button className="remove-btn" style={{
                flexShrink: 0,
                whiteSpace: "nowrap",
                background: "rgba(255,80,80,0.13)",
                color: "#ff4444",
                border: "none",
                borderRadius: 6,
                padding: "5px 12px",
                cursor: "pointer",
                fontWeight: "bold",
                fontSize: "1em"
              }} onClick={() => handleRemoveCoin(coin.id)} title="取消追蹤">
                取消
              </button>
            </div>
            {showChartId === coin.id && (
              <div className="coin-chart" style={{ width: "100%" }}>
                <TrendChart history={coin.history} />
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="add-coin-row">
        <select className="coin-select" value={addCoin} onChange={e => setAddCoin(e.target.value)}>
          <option value="">選擇幣種新增追蹤</option>
          {allCoins.filter(c => !followList.some(f => f.id === c.id)).map(c => (
            <option value={c.id} key={c.id}>{c.name} ({c.id})</option>
          ))}
        </select>
        <button type="button" className="add-btn" onClick={handleAddCoin}>加入追蹤</button>
      </div>
    </div>
  );
}
