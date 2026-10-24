"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Icon } from "@/components/Icon";
import { PlanPanel } from "@/components/PlanPanel";
import { PriceHistory } from "@/components/PriceHistory";
import { ProductImage } from "@/components/ProductImage";
import { QuoteList } from "@/components/QuoteList";
import { SiteHeader } from "@/components/SiteHeader";
import { SubscribeBox } from "@/components/SubscribeBox";
import { api } from "@/lib/api";
import { asDealItem, bestQuote, externalUrl, hasPrice, isConfirmed, officialStyleNumber, specs } from "@/lib/catalog";
import { channelName, money, timeAgo } from "@/lib/format";

export default function VariantPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const validId = Number.isSafeInteger(id) && id > 0;
  const detail = useQuery({ queryKey: ["variant", id], queryFn: () => api.variant(id), enabled: validId, retry: 1 });
  const plan = useQuery({ queryKey: ["variant-plan", id], queryFn: () => api.variantPlan(id), enabled: validId, retry: 0 });
  if (validId && detail.isPending) return <main><SiteHeader kicker="GEAR NOTES" /><div className="detail-hero"><div className="skeleton aspect-square" /><div className="space-y-5 py-6"><div className="skeleton h-7 w-3/4" /><div className="skeleton h-20" /><p className="micro-label" role="status">正在载入装备…</p></div></div></main>;
  if (!validId || detail.isError || !detail.data) return <main><SiteHeader kicker="GEAR NOTES" /><div className="empty-state"><Icon name="mountain" /><h1 className="mb-3 text-xl font-semibold">暂时无法读取这件装备</h1><p>记录可能不存在，或连接暂时不可用。</p><Link href="/variants" className="btn-primary">返回装备目录<Icon name="arrow" /></Link></div></main>;
  const variant = detail.data;
  const confirmed = isConfirmed(variant.match_status);
  const best = confirmed ? bestQuote(variant.channels) : undefined;
  const merchantUrl = externalUrl(best?.url);
  const styleNumber = officialStyleNumber(variant.style_number);
  const specification = [styleNumber ? `款号 ${styleNumber}` : "", ...specs(variant.color, variant.size)].filter(Boolean);
  const reported = variant.reported_min_price_cents;
  const heroImage = variant.image || variant.channels.find((quote) => quote.image)?.image;
  const canSubscribe = variant.can_subscribe === true;
  const cluesHref = variant.deals.length > 0 ? "#deal-notes" : "#channel-quotes";
  const actionHref = merchantUrl ?? cluesHref;
  const actionLabel = merchantUrl ? "前往渠道核对" : "查看优惠线索";
  const history = best ?? variant.channels.find((quote) => quote.price_status === "verified" && quote.currency === "CNY" && quote.history.length > 1);
  return <main>
    <SiteHeader kicker="GEAR NOTES" />
    <nav className="breadcrumb" aria-label="面包屑"><Link href="/">发现优惠</Link><Icon name="chevron" /><Link href="/variants">装备目录</Link><Icon name="chevron" /><span>装备详情</span></nav>
    <section className="detail-hero rise"><figure className="detail-visual"><ProductImage src={heroImage} alt={variant.style_name} priority /><figcaption><span>装备参考图 · 购买前核对颜色与尺码</span><Icon name="mountain" /></figcaption></figure><div className="detail-summary"><div className="detail-topline"><span className="eyebrow">{variant.brand_name || variant.brand} / GEAR NOTES</span><span className={`badge ${confirmed ? "badge-verified" : "badge-reported"}`}>{confirmed ? "规格已确认" : "规格待补齐"}</span></div><h1>{variant.style_name}</h1>{specification.length > 0 && <div className="spec-chips">{specification.map((spec) => <span className="spec-chip" key={spec}>{spec}</span>)}</div>}
      <div className="detail-price-block"><div className="detail-price-label"><span>{best ? "当前核验到手价 · 人民币" : "当前人民币报价"}</span>{best && <span>{best.channel_name || channelName(best.channel)}</span>}</div>{best ? <><p className="detail-price">{money(best.effective_cents, best.currency)}</p><div className="detail-price-math"><span>当下实付<strong>{hasPrice(best.paid_now_cents) ? money(best.paid_now_cents, best.currency) : "尚未提供"}</strong></span><span>事后返利<strong>{best.rebate_cents != null ? money(best.rebate_cents, best.currency) : "尚未提供"}</strong></span></div><p className="detail-price-sub">{best.checked_at ? `最近核验 ${timeAgo(best.checked_at)}。` : ""}本页已核验人民币渠道中最低，结算价请在渠道确认。</p></> : <><p className="detail-price-unknown">暂无可比较的核验报价</p><p className="detail-price-sub">{hasPrice(reported) ? `历史线报最低 ${money(reported, variant.currency || "CNY")}，不代表当前可买。` : "线报只能作为价格线索；确认同款、同色、同码后再比较。"}</p></>}</div>
      {!confirmed && <div className="notice"><strong>规格还需核对</strong><br />{variant.match_note || "尚未确认完整款号、颜色或尺码。请以来源文章和商家规格为准。"}</div>}
      <div className="detail-actions"><a href={actionHref} className="btn-primary" target={merchantUrl ? "_blank" : undefined} rel={merchantUrl ? "noopener noreferrer" : undefined}>{actionLabel}<Icon name={merchantUrl ? "external" : "arrow"} /></a>{canSubscribe ? <a href="#price-alert" className="btn btn-ghost"><Icon name="bell" />降价提醒</a> : <Link href="/calculator" className="btn btn-ghost"><Icon name="calculator" />算到手价</Link>}</div>
      {!canSubscribe && <p className="detail-price-sub mt-3">补齐规格和可信报价后，才能关注精确降价。</p>}
      <dl className="detail-meta"><dt>比较范围</dt><dd>同款 · 同色 · 同码，外币渠道分别展示</dd><dt>相关记录</dt><dd>{variant.deals.length} 条线报 · {variant.channels.length} 个渠道记录</dd></dl>
    </div></section>
    <div className="detail-body"><div><section className="content-section" id="channel-quotes"><h2><span className="section-number">01</span>渠道报价与购买条件</h2><QuoteList channels={variant.channels} bestListingId={best?.listing_id} /></section><section className="content-section" id="deal-plan"><h2><span className="section-number">02</span>各平台现价与最优方案</h2>{plan.isPending ? <div className="notice"><strong>正在整理各平台参考价…</strong></div> : plan.data ? <PlanPanel plan={plan.data} /> : <div className="notice"><strong>这件装备还没有带价格的线报。</strong><br />采集到相关优惠后会自动给出各平台对比与叠加方案。</div>}</section><section className="content-section"><h2><span className="section-number">03</span>到手价历史</h2><PriceHistory quote={history} /></section></div><aside><SubscribeBox variantId={variant.id} canSubscribe={canSubscribe} historyDays={variant.history_days ?? history?.history_days} /><div className="mt-4 notice"><strong>核对后再出发</strong><br />不同颜色、尺码、会员身份和支付方式，可能影响最终价格。海淘还需核算运费、税费与汇率。</div></aside></div>
    {variant.deals.length > 0 && <section className="detail-related" id="deal-notes"><div className="section-heading"><h2>{confirmed ? "同规格的线报记录" : "相关装备线索"}<small>{variant.deals.length} 条</small></h2><span>来源文章记录的优惠，与上方方案互为出处</span></div><ul className="deal-notes">{variant.deals.map((deal) => {
      const item = asDealItem(deal);
      return <li key={item.id}><span className="notes-source">{item.source}</span><Link href={`/deals/${item.id}`} className="notes-title">{item.title}</Link><span className="notes-price num">{hasPrice(item.price_cents) ? money(item.price_cents, item.currency) : "价格见详情"}</span><span className="notes-time">{timeAgo(item.published_at)}</span></li>;
    })}</ul></section>}
    <div className="mobile-detail-bar"><Link href="/variants" className="mobile-back"><Icon name="grid" />目录</Link><div className="bar-price"><small>{best ? "当前核验到手价" : hasPrice(reported) ? "历史线报最低 · 非现价" : "当前报价"}</small><strong>{best ? money(best.effective_cents, best.currency) : hasPrice(reported) ? money(reported, variant.currency || "CNY") : "等待核验"}</strong></div><a href={merchantUrl ?? (canSubscribe ? "#price-alert" : cluesHref)} className="btn-primary" target={merchantUrl ? "_blank" : undefined} rel={merchantUrl ? "noopener noreferrer" : undefined}>{merchantUrl ? "前往渠道核对" : canSubscribe ? "关注降价" : "查看优惠线索"}<Icon name={merchantUrl ? "external" : "arrow"} /></a></div>
  </main>;
}
