// src/TrendChart.jsx
import { formatPrice } from "./format";

const W = 350, H = 150, PAD_Y = 10;

function Stat({ label, value, color }) {
  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div style={{ color: "#8fa8c8", fontSize: "0.8em" }}>{label}</div>
      <div style={{ color, fontWeight: 600, fontSize: "clamp(0.72em, 3.4vw, 0.95em)", whiteSpace: "nowrap" }}>${formatPrice(value)}</div>
    </div>
  );
}

export default function TrendChart({ history }) {
  if (!history || history.length === 0) return (
    <div style={{ padding: 18, color: "#bbb" }}>暫無資料</div>
  );

  const prices = history.map(d => Number(d.price));
  const avg = prices.reduce((sum, p) => sum + p, 0) / prices.length;
  const max = Math.max(...prices);
  const min = Math.min(...prices);

  // 只有一筆資料時畫成水平線，避免除以 0
  const span = Math.max(prices.length - 1, 1);
  const range = max - min || 1;
  const points = prices.map((p, i) => [
    (i / span) * W,
    H - PAD_Y - ((p - min) / range) * (H - PAD_Y * 2)
  ]);
  if (points.length === 1) points.push([W, points[0][1]]);
  const pointsStr = points.map(p => p.join(",")).join(" ");
  const areaPointsStr = `0,${H} ${pointsStr} ${W},${H}`;

  return (
    <div style={{
      marginTop: 18,
      background: "rgba(255,255,255,0.08)",
      borderRadius: 10,
      padding: "12px 12px 10px",
      boxShadow: "0 2px 18px #031d39cc"
    }}>
      {/* 以 viewBox 縮放，寬度隨容器調整 */}
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" style={{ width: "100%", height: H, display: "block" }}>
        <defs>
          <linearGradient id="line-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#90caf9" stopOpacity="0.7" />
            <stop offset="100%" stopColor="#e040fb" stopOpacity="0.13" />
          </linearGradient>
        </defs>
        <polygon points={areaPointsStr} fill="url(#line-gradient)" opacity="0.41" />
        <polyline
          points={pointsStr}
          fill="none"
          stroke="#90caf9"
          strokeWidth="2.2"
          vectorEffect="non-scaling-stroke"
          strokeLinejoin="round"
        />
      </svg>
      <div style={{ display: "flex", gap: 6, marginTop: 10, textAlign: "center" }}>
        <Stat label="最低" value={min} color="#ff8a8a" />
        <Stat label="平均" value={avg} color="#5ee7ff" />
        <Stat label="最高" value={max} color="#6dffb0" />
      </div>
    </div>
  );
}
