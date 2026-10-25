import Link from "next/link";
import { Icon } from "@/components/Icon";
import type { ChannelQuote } from "@/lib/api";
import { externalUrl, hasPrice, isVerifiedQuote } from "@/lib/catalog";
import { channelName, fen, money, promoName, timeAgo } from "@/lib/format";

/**
 * 渠道对比面板：已核验人民币报价按到手价升序排在最前，
 * 附对比条（最低价满宽）与差价标注，其余渠道次之。
 */
export function QuoteList({ channels, bestListingId }: { channels: ChannelQuote[]; bestListingId?: number }) {
  if (!channels.length) return <div className="notice"><strong>还没有可核验的商家报价。</strong><br />线报参考价不能替代商家当前到手价，请先阅读优惠条件并核对来源。</div>;
  const priced = channels.filter((quote) => isVerifiedQuote(quote) && quote.currency === "CNY" && hasPrice(quote.effective_cents));
  const lowest = priced.length ? Math.min(...priced.map((quote) => quote.effective_cents as number)) : null;
  const rank = new Map(channels.map((quote) => {
    const verifiedCny = isVerifiedQuote(quote) && quote.currency === "CNY" && hasPrice(quote.effective_cents);
    return [quote.listing_id, verifiedCny ? 0 : isVerifiedQuote(quote) ? 1 : 2] as const;
  }));
  const sorted = [...channels].sort((a, b) => {
    const [ra, rb] = [rank.get(a.listing_id) ?? 2, rank.get(b.listing_id) ?? 2];
    if (ra !== rb) return ra - rb;
    if (ra === 0) return (a.effective_cents as number) - (b.effective_cents as number);
    return 0;
  });
  return <div className="quote-list">{sorted.map((quote) => {
    const verified = isVerifiedQuote(quote);
    const url = externalUrl(quote.url);
    const effective = verified ? quote.effective_cents : null;
    const isCny = quote.currency === "CNY";
    const price = effective ?? quote.price_cents;
    const isLowest = lowest != null && verified && isCny && effective === lowest;
    const delta = lowest != null && verified && isCny && effective != null && !isLowest ? effective - lowest : null;
    const barWidth = lowest != null && verified && isCny && effective != null && lowest > 0 ? Math.round((lowest / effective) * 100) : null;
    const statusLabel = verified ? "已核验" : quote.in_stock === false ? "暂无库存" : quote.price_status === "stale" ? "报价待更新" : quote.price_status === "verified" ? "购买状态待确认" : "规格待核对";
    const priceNote = verified ? isCny ? "人民币到手价" : "原币报价，未含海淘落地成本" : quote.price_status === "stale" ? "较早采集价，当前需重新核对" : "参考记录，规格与当前价格待核对";
    return <article className={`quote-card ${bestListingId === quote.listing_id ? "is-best" : ""}`} key={quote.listing_id}><div className="quote-head"><div><h3>{quote.channel_name || channelName(quote.channel)}<span className={`badge ${verified ? "badge-verified" : "badge-reported"}`}>{statusLabel}</span>{isLowest && <span className="badge badge-best">本页最低</span>}{delta != null && <span className="quote-delta">较最低 +{fen(delta)}</span>}</h3><p className="quote-subtitle">{priceNote}{quote.in_stock === false ? " · 暂无库存" : quote.in_stock == null ? " · 库存未确认" : ""}</p></div><div className="text-right"><span className="quote-main-price">{hasPrice(price) ? money(price, quote.currency) : "暂无价格"}</span>{bestListingId === quote.listing_id && <span className="mt-1 block text-[9px] text-moss">本页最低核验到手价</span>}</div></div>
      {barWidth != null && <div className="quote-bar" aria-hidden="true"><span className={isLowest ? "is-lowest" : ""} style={{ width: `${barWidth}%` }} /></div>}
      {verified && <div className="quote-breakdown"><div>当下实付<strong>{hasPrice(quote.paid_now_cents) ? money(quote.paid_now_cents, quote.currency) : "尚未提供"}</strong></div><div>事后返利<strong>{quote.rebate_cents != null ? money(quote.rebate_cents, quote.currency) : "尚未提供"}</strong></div></div>}
      {!!quote.steps?.length && <details className="quote-steps"><summary>优惠计算明细<Icon name="chevron" /></summary><ol>{quote.steps.map((step, index) => <li key={`${step.promo_id}-${index}`}><span>{step.promo_name || promoName(step.kind)} · {money(step.amount_before_cents, quote.currency)} → {money(step.amount_after_cents, quote.currency)}</span>{step.note && <p>{step.note}</p>}</li>)}</ol></details>}
      {!isCny && <p className="mt-4 text-[11px] text-dim">原币商品价；美国税费、转运费与汇率需自行核算，暂不与人民币价合并比价。</p>}
      <div className="quote-footer"><span>{quote.checked_at ? `${verified ? "最近核验" : "最近检查"} ${timeAgo(quote.checked_at)}` : "暂无检查时间"}{quote.source ? ` · ${quote.source}` : ""}</span>{url && <a href={url} target="_blank" rel="noopener noreferrer" className="text-link">{verified ? "前往渠道核对" : "查看报价来源"}<Icon name="external" /></a>}</div>
    </article>;
  })}</div>;
}
