import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./App.css";

export default function Reset() {
  const navigate = useNavigate();
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleReset() {
    setLoading(true);
    try {
      const res = await fetch("/api/reset", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include", // ✅ 自動帶 cookie session
        body: JSON.stringify({}) // ✅ 不需要傳 user_id
      });
      const data = await res.json();

      if (res.ok && data.message) {
        setMessage(`✅ 重置成功！您目前餘額為 ${Number(data.balance || 5000000).toLocaleString()} USD`);
      } else {
        setMessage("❌ 重置失敗：" + (data.error || "未知錯誤"));
      }
    } catch (err) {
      console.error("重置錯誤：", err);
      setMessage("❌ 系統錯誤，請稍後再試");
    }
    setLoading(false);
  }

  return (
    <div className="crypto-glass reset-page" style={{ maxWidth: 400, margin: "40px auto", padding: 28 }}>
      <button
        className="glass-btn"
        style={{ marginBottom: 14, width: "fit-content", padding: "9px 30px" }}
        onClick={() => navigate("/")}
      >
        回到主頁
      </button>

      <h1 className="title2" style={{ marginBottom: 16 }}>帳戶重置</h1>

      <div style={{ fontSize: "1.08em", color: "#aee1fc", marginBottom: 22, lineHeight: 1.6 }}>
        是否確認要重製餘額？<br />
        這將會重新開始模擬投資（初始值為 <b style={{ color: "#5ee7ff" }}>5,000,000 USD</b>）
      </div>

      <button
        className="glass-btn danger"
        style={{ padding: "12px 0", fontSize: "1.14em", width: "80%", marginBottom: 18 }}
        onClick={handleReset}
        disabled={loading}
      >
        {loading ? "處理中..." : "Reset"}
      </button>

      {message && (
        <div style={{
          marginTop: 18,
          color: message.includes("成功") ? "#09e679" : "#f34b6e",
          fontWeight: 600,
          fontSize: "1.13em",
          letterSpacing: 1
        }}>
          {message}
        </div>
      )}
    </div>
  );
}
