import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";

export default function PnLBalance() {
  const navigate = useNavigate();
  const [balance, setBalance] = useState(null);
  const [portfolio, setPortfolio] = useState([]);
  const [summary, setSummary] = useState({});
  const [selectedCoin, setSelectedCoin] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    fetch("/api/profit", {
      credentials: "include"
    })
      .then(res => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then(data => {
        setBalance(data.balance ?? 0);
        setPortfolio(data.portfolio || []);
        setSummary(data.summary || {});
        if (data.portfolio?.length > 0) {
          setSelectedCoin(data.portfolio[0].coin_id);
        }
        setLoading(false);
      })
      .catch(err => {
        console.error("獲取損益資料失敗：", err);
        setError("載入資料失敗，請稍後再試");
        setLoading(false);
      });
  }, []);

  const holding = portfolio.find(c => c.coin_id === selectedCoin);

  function fmt(n) {
    return Number(n || 0).toLocaleString("en-US", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  }

  return (
    <div className="crypto-glass pnl-balance">
      <button className="glass-btn" style={{ marginLeft: 10, marginBottom: 10 }} onClick={() => navigate("/")}>
        回到主頁
      </button>

      <h1 className="title2" style={{ marginLeft: 18 }}>損益 & 餘額查詢</h1>

      {loading ? (
        <div style={{ color: "#ccc", marginLeft: 18 }}>載入中...</div>
      ) : error ? (
        <div style={{ color: "red", marginLeft: 18 }}>{error}</div>
      ) : (
        <>
          <div style={{
            marginLeft: 20,
            marginBottom: 24,
            fontWeight: 500,
            fontSize: "1.5em",
            color: "#aee1fc"
          }}>
            目前帳戶現金：
            <span style={{ color: "#5ee7ff", fontSize: "1.13em" }}>
              ${fmt(balance)}
            </span>
          </div>

          <div style={{
            marginLeft: 20,
            marginRight: 20,
            marginBottom: 20,
            background: "rgba(255,255,255,0.05)",
            borderRadius: 12,
            padding: "12px 16px 10px 16px",
            color: "#aee1fc",
            fontSize: "1.5em",
            boxShadow: "0 2px 12px #2c2c5a18"
          }}>
            <div>總市值：<b style={{ color: "#5ee7ff" }}>${fmt(summary.total_market_value || 0)}</b></div>
            <div>總成本：<b style={{ color: "#ffd780" }}>${fmt(summary.total_buy_cost || 0)}</b></div>
            {(summary.total_sell_income || 0) > 0 && (
              <div>已賣出收入：<b style={{ color: "#ffd780" }}>${fmt(summary.total_sell_income)}</b></div>
            )}
            <div>總損益：<b style={{ color: (summary.total_net_profit || 0) >= 0 ? "#09e679" : "#ff4e4e" }}>
              {fmt(summary.total_net_profit || 0)}
            </b></div>
            <div>總報酬率：<b style={{ color: (summary.total_return_rate || 0) >= 0 ? "#09e679" : "#ff4e4e" }}>
              {fmt(summary.total_return_rate || 0)}%
            </b></div>
          </div>

          {portfolio.length > 0 && (
            <>
              <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 16, marginLeft: 20 }}>
                <label htmlFor="coin-select" style={{ fontSize: "1.5em", color: "#aee1fc" }}>幣種：</label>
                <select
                  className="coin-select"
                  id="coin-select"
                  value={selectedCoin}
                  onChange={e => setSelectedCoin(e.target.value)}
                >
                  {portfolio.map(c => (
                    <option key={c.coin_id} value={c.coin_id}>{c.coin_id}</option>
                  ))}
                </select>
              </div>
            </>
          )}

          {holding && (
            <div style={{
              background: "rgba(255,255,255,0.07)",
              borderRadius: 16,
              margin: "8px 16px 28px 16px",
              padding: "18px 12px",
              boxShadow: "0 2px 14px #5169fa33"
            }}>
              <div style={{ marginBottom: 8, color: "#aee1fc", fontSize: "1.5em" }}>持有數量：<b>{holding.quantity}</b></div>
              <div style={{ marginBottom: 8, color: "#aee1fc", fontSize: "1.5em" }}>平均成本：<b>${fmt(holding.average_buy_cost)}</b></div>
              <div style={{ marginBottom: 8, color: "#aee1fc", fontSize: "1.5em" }}>即時價格：<b style={{ color: "#5ee7ff" }}>${fmt(holding.current_price)}</b></div>
              <div style={{ marginBottom: 8, color: "#aee1fc", fontSize: "1.5em" }}>
                損益（含已賣出）：<b style={{ color: holding.net_profit >= 0 ? "#09e679" : "#ff4e4e" }}>
                  {fmt(holding.net_profit)}
                </b>
              </div>
            </div>
          )}

        </>
      )}
    </div>
  );
}

