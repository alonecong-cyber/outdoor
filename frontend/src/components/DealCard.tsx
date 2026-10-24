import Link from "next/link";
import { Icon } from "@/components/Icon";
import { ProductImage } from "@/components/ProductImage";
import type { DealItem } from "@/lib/api";
import { CATEGORIES, conditionTags, hasPrice, officialStyleNumber, specs, summaryText } from "@/lib/catalog";
import { channelName, money, timeAgo } from "@/lib/format";

export function DealCard({ deal, index = 0 }: { deal: DealItem; index?: number }) {
  const category = CATEGORIES.slice(1, -1).find((item) => item.terms.some((term) => deal.title.toLowerCase().includes(term)));
  const specification = deal.variant ? [officialStyleNumber(deal.variant.style_number), ...specs(deal.variant.color, deal.variant.size)].filter(Boolean) : [];
  const expired = deal.price_status === "expired";
  const stale = deal.price_status === "stale";
  const summary = summaryText(deal);
  const tags = conditionTags(deal.tags).slice(0, 3);
  return <li className={`rise rise-${(index % 5) + 1}`}>
    <Link href={`/deals/${deal.id}`} className="deal-card" aria-label={`查看优惠详情：${deal.title}`}>
      <div className="deal-image"><ProductImage src={deal.image} alt={deal.title} priority={index < 3} /><span className="image-category">{category?.label ?? "户外装备"}</span><span className="image-index num">FIELD / {String(index + 1).padStart(2, "0")}</span></div>
      <div className="deal-card-body">
        <div className="deal-meta"><span className="deal-channel">{channelName(deal.channel)}</span><time dateTime={deal.published_at ?? undefined}>{timeAgo(deal.published_at)}</time></div>
        <h3>{deal.title}</h3>
        {specification.length > 0 && <p className="deal-specs">{specification.join(" · ")}</p>}
        {summary && <p className="deal-description">{summary}</p>}
        <div className="card-tags"><span className={`badge ${expired ? "badge-expired" : "badge-reported"}`}>{expired ? "线报已过期" : stale ? "较早线报 · 待复核" : "线报待核验"}</span>{tags.map((tag) => <span className="badge badge-outline" key={tag}>{tag}</span>)}</div>
        <div className="deal-price-row"><div><span className="price-label">{expired ? "过期线报参考价" : stale ? "历史线报参考价" : "线报参考价"}</span>{hasPrice(deal.price_cents) ? <span className="deal-price">{money(deal.price_cents, deal.currency)}</span> : <span className="price-unknown">价格见详情</span>}</div><span className="card-action">查看优惠详情<Icon name="arrow" /></span></div>
      </div>
    </Link>
  </li>;
}

export function DealSkeletons() {
  return <div className="deal-grid" aria-label="正在载入装备" role="status">{[0, 1, 2].map((i) => <div key={i} className="skeleton-card"><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /><div className="skeleton" /></div>)}</div>;
}
