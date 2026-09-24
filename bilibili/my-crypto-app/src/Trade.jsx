import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";
import { formatPrice } from "./format";

export default function Trade() {
  const navigate = useNavigate();

  const [allCoins, setAllCoins] = useState([]);
  const [coinId, setCoinId] = useState("");
  const [cash, setCash] = useState(0);
  const [holdings, setHoldings] = useState([]);
  const [tradeType, setTradeType] = useState("buy");
  const [amount, setAmount] = useState("");
  const [total, setTotal] = useState("");
  const [price, setPrice] = useState(0);
  const [message, setMessage] = useState("");

  const FEE_RATE = 0.001;
  // 買入：實付 = 淨額 + 手續費；賣出：實收 = 淨額 − 手續費
  const feeFactor = tradeType === "buy" ? 1 + FEE_RATE : 1 - FEE_RATE;
  const displayTotal = amount && price ? parseFloat(amount) * price : 0;
  const realTotal = displayTotal * feeFactor;
  const feeAmount = displayTotal * FEE_RATE;

  function handleCoinChange(newCoinId) {
    if (newCoinId === coinId) {
      setPrice(0);
      setAmount("");
      setTotal("");
      setMessage("🔄 已重新選取同一幣種，已清空交易欄位");
    } else {
      setCoinId(newCoinId);
      setAmount("");
      setTotal("");
      setMessage("");
    }
  }

  useEffect(() => {
    fetch("/api/coin_list", { credentials: "include" })
      .then(r => r.json())
      .then(data => {
        setAllCoins(data);
        if (data.length > 0) setCoinId(data[0].coin_id);
      })
      .catch(err => {
        console.error("載入幣種清單失敗：", err);
        setMessage("❌ 無法取得幣種清單，請稍後再試");
      });
  }, []);

  useEffect(() => {
    if (!coinId) return;

    fetch(`/api/trade_info?coin_id=${coinId}`, { credentials: "include" })
      .then(r => r.json())
      .then(data => {
        setCash(data.balance ?? 0);
        setPrice(data.coin_price ?? 0);
      })
      .catch(err => {
        console.error("載入幣價或餘額失敗：", err);
        setMessage("❌ 無法取得即時幣價或帳戶資料");
      });

    fetch(`/api/profit`, { credentials: "include" })
      .then(r => r.json())
      .then(data => {
        setHoldings(data.portfolio ?? []);
      })
      .catch(err => {
        console.error("載入持倉資料失敗：", err);
      });
  }, [coinId, message]);

  // 切換買 / 賣時，依新的手續費方向重新計算金額
  useEffect(() => {
    if (amount !== "" && !isNaN(amount) && price) {
      setTotal((parseFloat(amount) * price * feeFactor).toFixed(2));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tradeType]);

  function handleAmountChange(val) {
    setAmount(val);
    if (val !== "" && !isNaN(val) && price) {
      setTotal((parseFloat(val) * price * feeFactor).toFixed(2));
    } else {
      setTotal("");
    }
  }

  function handleTotalChange(val) {
    setTotal(val);
    if (val !== "" && !isNaN(val) && price) {
      setAmount((parseFloat(val) / feeFactor / price).toFixed(6));
    } else {
      setAmount("");
    }
  }

  async function handleConfirm() {
    const numAmount = parseFloat(amount);
    const numTotal = parseFloat(total);

    if (!numAmount || !numTotal || isNaN(numAmount) || isNaN(numTotal) || numAmount <= 0 || numTotal <= 0) {
      setMessage("請輸入大於0的有效數量和金額");
      return;
    }

    try {
      const res = await fetch("/api/trade", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          coin_id: coinId,
          action: tradeType,
          quantity: numAmount
        })
      });

      const data = await res.json();
      if (res.ok && data.status === "success") {
        const verb = tradeType === "buy" ? "已買入" : "已賣出";
        const totalLabel = tradeType === "buy" ? "實付" : "實收";
        setMessage(`✅ 交易成功！${verb} ${data.quantity} ${coinId}，${totalLabel} $${data.total.toLocaleString("en-US", { minimumFractionDigits: 2 })}`);
        setAmount("");
        setTotal("");
      } else {
        setMessage("❌ " + (data.reason || "交易失敗"));
      }
    } catch (err) {
      console.error("交易錯誤：", err);
      setMessage("❌ 系統錯誤，請稍後再試");
    }
  }

  const holdObj = holdings.find(c => c.coin_id === coinId);
  const holdAmount = holdObj?.quantity || 0;

  return (
    <div className="crypto-glass trade-page" style={{ padding: 20 }}>
      <button className="glass-btn" style={{ marginBottom: 10, width: "fit-content", padding: "9px 30px" }} onClick={() => navigate("/")}>回到主頁</button>
      <h1 className="title2">Trade</h1>

      <div style={{ marginBottom: 16, fontWeight: 500, fontSize: "1.5em", color: "#aee1fc" }}>
        目前餘額：<span style={{ color: "#5ee7ff" }}>${cash.toLocaleString("en-US", { minimumFractionDigits: 2 })}</span>
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={{ marginRight: 8, color: "#aee1fc", fontSize: "1.5em" }}>交易幣種：</label>
        <select className="coin-select" value={coinId} onChange={e => handleCoinChange(e.target.value)}>
          {allCoins.map(c => (
            <option key={c.coin_id} value={c.coin_id}>{c.coin_name} ({c.coin_id})</option>
          ))}
        </select>
      </div>

      <div style={{ marginBottom: 14, color: "#aee1fc", fontSize: "1.5em" }}>
        即時幣價：<b style={{ color: "#5ee7ff" }}>${formatPrice(price)}</b>
      </div>

      <div style={{ marginBottom: 14, color: "#aee1fc", fontSize: "1.5em" }}>
        目前持有：<b style={{ color: "#82ffb8" }}>{holdAmount} {coinId}</b>
      </div>

      <div style={{ marginBottom: 14 }}>
        <label style={{ marginRight: 8, color: "#aee1fc", fontSize: "1.5em" }}>買/賣：</label>
        <select className="coin-select" value={tradeType} onChange={e => setTradeType(e.target.value)}>
          <option value="buy">買入 (Buy)</option>
          <option value="sell">賣出 (Sell)</option>
        </select>
      </div>

      {/* ✅ 改為 grid：數量與金額同一行、靠左 */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "160px 1fr",
          rowGap: 16,
          columnGap: 12,
          marginBottom: 20
        }}
      >
        <label
          style={{
            alignSelf: "center",
            fontSize: "1.3em",
            color: "#aee1fc",
            whiteSpace: "nowrap"
          }}
        >
          數量（顆）：
        </label>
        <input
          type="number"
          style={{
            width: "90%",
            padding: 10,
            borderRadius: 6,
            border: "1px solid #89b",
            fontSize: "1.3em"
          }}
          value={amount}
          onChange={(e) => handleAmountChange(e.target.value)}
        />

        <label
          style={{
            alignSelf: "center",
            fontSize: "1.3em",
            color: "#aee1fc",
            whiteSpace: "nowrap"
          }}
        >
          {tradeType === "buy" ? "實付金額：" : "實收金額："}
        </label>
        <input
          type="number"
          style={{
            width: "90%",
            padding: 10,
            borderRadius: 6,
            border: "1px solid #89b",
            fontSize: "1.3em"
          }}
          value={total}
          onChange={(e) => handleTotalChange(e.target.value)}
        />
      </div>

      {realTotal > 0 && (
        <div style={{ marginTop: 10, color: "#eee", fontSize: "1.2em" }}>
          淨額（不含手續費）：${displayTotal.toFixed(2)}<br />
          手續費：約 ${feeAmount.toFixed(2)}<br />
          {tradeType === "buy" ? "實際付款總額" : "實際入帳金額"}：${realTotal.toFixed(2)}
        </div>
      )}

      <div style={{ marginTop: 20 }}>
        <button className="glass-btn" style={{ width: 120, padding: "8px 0" }} onClick={handleConfirm}>Confirm</button>
      </div>

      {message && (
        <div style={{
          marginTop: 20,
          color: message.includes("成功") ? "#09e679" : "#f34b6e",
          fontWeight: 600,
          fontSize: "1.08em"
        }}>
          {message}
        </div>
      )}
    </div>
  );
}
