import type { ChannelQuote } from "@/lib/api";
import { hasPrice } from "@/lib/catalog";
import { money } from "@/lib/format";

export function PriceHistory({ quote }: { quote?: ChannelQuote }) {
  const points = (quote?.history ?? []).filter((point) => hasPrice(point.price_cents) && Number.isFinite(Date.parse(point.ts))).sort((a, b) => Date.parse(a.ts) - Date.parse(b.ts));
  if (!quote || points.length < 2) return <div className="notice"><strong>价格历史还在积累。</strong><br />至少需要两个可信价格记录才能展示走势；历史不足 14 天，不作“历史新低”判断。</div>;
  const min = Math.min(...points.map((point) => point.price_cents));
  const max = Math.max(...points.map((point) => point.price_cents));
  const span = max - min || max * .1 || 1;
  const first = Date.parse(points[0].ts);
  const last = Date.parse(points[points.length - 1].ts);
  const days = quote.history_days ?? Math.floor((last - first) / 86_400_000);
  const xy = points.map((point) => ({ x: 5 + ((Date.parse(point.ts) - first) / (last - first || 1)) * 590, y: 25 + (1 - (point.price_cents - min) / span) * 90 }));
  const path = xy.map((point) => `${point.x},${point.y}`).join(" ");
  const date = (timestamp: string) => new Date(timestamp).toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" });
  return <div className="price-history"><div className="history-header"><span>已记录 {days} 天 · {points.length} 个价格点</span><span className="num">{money(min, quote.currency)} — {money(max, quote.currency)}</span></div><svg viewBox="0 0 600 145" role="img" aria-label={`${points.length}个历史到手价记录，最低${money(min, quote.currency)}，最高${money(max, quote.currency)}`}><defs><linearGradient id={`history-fill-${quote.listing_id}`} x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#477148" stopOpacity=".14" /><stop offset="1" stopColor="#477148" stopOpacity="0" /></linearGradient></defs>{[25, 70, 115].map((y) => <line key={y} x1="5" y1={y} x2="595" y2={y} stroke="#dce0d4" strokeDasharray="3 5" />)}<polygon points={`5,145 ${path} 595,145`} fill={`url(#history-fill-${quote.listing_id})`} /><polyline points={path} fill="none" stroke="#477148" strokeWidth="2" strokeLinejoin="round" />{xy.map((point, index) => <circle key={index} cx={point.x} cy={point.y} r="3" fill="#477148"><title>{date(points[index].ts)} · {money(points[index].price_cents, quote.currency)}</title></circle>)}</svg><div className="history-axis"><span>{date(points[0].ts)}</span><span>{date(points[points.length - 1].ts)}</span></div><p className="history-note">该渠道、该规格的已记录到手价。{days < 14 ? "样本不足 14 天，暂不判断历史新低。" : "统计仅覆盖已记录区间，不能代表全网历史。"}</p></div>;
}
