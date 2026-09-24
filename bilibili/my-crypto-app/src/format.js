// 依價格大小決定小數位數：高價幣顯示 2 位，低價幣（如 DOGE）保留較多位
export function formatPrice(value) {
  if (value === null || value === undefined || value === "" || isNaN(value)) return "—";
  const p = Number(value);
  const digits = p >= 100 ? 2 : p >= 1 ? 4 : 6;
  return p.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: digits });
}
