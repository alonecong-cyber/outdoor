"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { DealCard } from "@/components/DealCard";
import { Icon } from "@/components/Icon";
import { ProductImage } from "@/components/ProductImage";
import { QuoteList } from "@/components/QuoteList";
import { SiteHeader } from "@/components/SiteHeader";
import { api, type DealDetail } from "@/lib/api";
import { bestQuote, externalUrl, hasPrice, isConfirmed, officialStyleNumber, specs } from "@/lib/catalog";
import { channelName, money, timeAgo } from "@/lib/format";

async function loadDeal(id: number): Promise<DealDetail> {
  try { return await api.deal(id); } catch (error) {
    // 新详情接口尚未部署时，以已有线报原字段提供完整站内阅读。
    const existing = (await api.deals({ limit: 100 })).find((deal) => deal.id === id);
    if (existing) return existing;
    throw error;
  }
}

export default function DealDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const validId = Number.isSafeInteger(id) && id > 0;
  const detail = useQuery({ queryKey: ["deal", id], queryFn: () => loadDeal(id), enabled: validId, retry: 1 });
  const client = useQueryClient();
  const [draft, setDraft] = useState("");
  const notesQuery = useQuery({ queryKey: ["deal-notes", id], queryFn: () => api.dealNotes(id), enabled: validId });
  const addNote = useMutation({
    mutationFn: () => api.addDealNote(id, draft.trim()),
    onSuccess: () => { setDraft(""); void client.invalidateQueries({ queryKey: ["deal-notes", id] }); },
  });
  const removeNote = useMutation({
    mutationFn: (noteId: number) => api.deleteDealNote(id, noteId),
    onSuccess: () => void client.invalidateQueries({ queryKey: ["deal-notes", id] }),
  });
  if (validId && detail.isPending) return <main><SiteHeader kicker="DEAL NOTES" /><div className="detail-hero"><div className="skeleton aspect-square" /><div className="space-y-5 py-6"><div className="skeleton h-7 w-3/4" /><div className="skeleton h-20" /><p className="micro-label" role="status">正在载入优惠详情…</p></div></div></main>;
  if (!validId || detail.isError || !detail.data) return <main><SiteHeader kicker="DEAL NOTES" /><div className="empty-state"><Icon name="mountain" /><h1 className="mb-3 text-xl font-semibold">暂时无法读取这条优惠</h1><p>线报可能不存在，或连接暂时不可用。返回首页继续寻找装备。</p><Link href="/" className="btn-primary">返回发现优惠<Icon name="arrow" /></Link></div></main>;
  const deal = detail.data;
  const canSubscribe = deal.can_subscribe === true;
  const confirmed = isConfirmed(deal.match_status);
  const best = confirmed ? bestQuote(deal.channels ?? []) : undefined;
  const sourceUrl = externalUrl(deal.url);
  const merchantUrl = externalUrl(best?.url);
  const expired = deal.price_status === "expired";
  const stale = deal.price_status === "stale";
  const specification = deal.variant ? [officialStyleNumber(deal.variant.style_number) ? `款号 ${officialStyleNumber(deal.variant.style_number)}` : "", ...specs(deal.variant.color, deal.variant.size)].filter(Boolean) : [];
  const notes = deal.purchase_notes?.filter((note) => note.trim()) ?? (deal.summary ? deal.summary.split(/\n\s*\n/).filter(Boolean) : []);
  const related = (deal.related_deals ?? []).filter((item) => item.id !== deal.id);
  const actionHref = merchantUrl ?? sourceUrl ?? "#purchase-notes";
  const actionLabel = merchantUrl ? "前往渠道核对" : sourceUrl ? "查看来源" : "阅读优惠条件";
  const externalAction = !!(merchantUrl || sourceUrl);
  return <main>
    <SiteHeader kicker="DEAL NOTES" />
    <nav className="breadcrumb" aria-label="面包屑"><Link href="/">发现优惠</Link><Icon name="chevron" /><span>优惠详情</span></nav>
    <section className="detail-hero rise"><figure className="detail-visual"><ProductImage src={deal.image} alt={deal.title} priority /><figcaption><span>来源配图 · 以实际规格为准</span><Icon name="mountain" /></figcaption></figure><div className="detail-summary"><div className="detail-topline"><span className="eyebrow">DEAL FIELD NOTES / 优惠线索</span><span className={`badge ${expired ? "badge-expired" : "badge-reported"}`}>{expired ? "线报已过期" : stale ? "较早线报 · 待复核" : "线报待核验"}</span></div><h1>{deal.title}</h1>{specification.length > 0 && <div className="spec-chips">{specification.map((spec) => <span className="spec-chip" key={spec}>{spec}</span>)}</div>}
      <div className="detail-price-block"><div className="detail-price-label"><span>{best ? "当前核验到手价 · 人民币" : expired ? "过期线报参考价" : stale ? "历史线报参考价" : "线报参考价"}</span><span>{best ? best.channel_name || channelName(best.channel) : channelName(deal.channel)}</span></div>{hasPrice(best?.effective_cents ?? deal.price_cents) ? <p className="detail-price">{money(best?.effective_cents ?? deal.price_cents, best?.currency ?? deal.currency)}</p> : <p className="detail-price-unknown">价格条件待核对</p>}{best ? <><div className="detail-price-math"><span>当下实付<strong>{hasPrice(best.paid_now_cents) ? money(best.paid_now_cents, best.currency) : "尚未提供"}</strong></span><span>事后返利<strong>{best.rebate_cents != null ? money(best.rebate_cents, best.currency) : "尚未提供"}</strong></span></div><p className="detail-price-sub">本条线报参考 {hasPrice(deal.price_cents) ? money(deal.price_cents, deal.currency) : "未提供价格"}。核验报价以渠道结算页为准。</p></> : <p className="detail-price-sub">{deal.status_note || (expired ? "来源优惠已过期，保留文章内容供核对。" : "来自来源文章，尚未验证当前能否按此价格购买。")}</p>}</div>
      <div className="notice">{expired ? "这条线报已过期，请查看是否有更新的渠道报价。" : stale ? "这条线报发布时间较早，价格与活动条件需要重新核对。" : "先核对适用颜色、尺码、会员与领券条件，再前往渠道确认结算价。"}</div>
      <div className="detail-actions"><a href={actionHref} target={externalAction ? "_blank" : undefined} rel={externalAction ? "noopener noreferrer" : undefined} className="btn-primary">{actionLabel}<Icon name={externalAction ? "external" : "arrow"} /></a><Link href="/watch" className="btn btn-ghost"><Icon name="bell" />关注这类好价</Link></div>
      <dl className="detail-meta"><dt>线报渠道</dt><dd>{channelName(deal.channel)}</dd><dt>文章来源</dt><dd>{deal.source === "smzdm" ? "什么值得买" : deal.source || "来源未标明"} · {timeAgo(deal.published_at) || "发布时间未提供"}</dd><dt>内容检查</dt><dd>{deal.last_checked_at ? `来源最近检查 ${timeAgo(deal.last_checked_at)}` : "尚无来源检查时间"}</dd>{deal.expires_at && <><dt>有效期</dt><dd>{new Date(deal.expires_at).toLocaleString("zh-CN")}</dd></>}</dl>
    </div></section>
    <div className="detail-body"><div><section className="content-section" id="purchase-notes"><h2><span className="section-number">01</span>优惠条件与来源说明</h2><div className="purchase-notes"><div className="notes-caption">以下保留来源内容，请留意活动时间与适用规格。</div>{notes.length ? notes.map((note, index) => <p key={index}>{note}</p>) : <p>来源尚未提供详细优惠条件，请前往文章来源核对。</p>}{sourceUrl && <div className="notes-source"><a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="text-link">查看来源原文<Icon name="external" /></a><p className="mt-2 text-[10px] text-dim">原文用于核对优惠信息，进入后不一定是商家购买页面。</p></div>}</div></section><section className="content-section"><h2><span className="section-number">02</span>渠道报价</h2><QuoteList channels={deal.channels ?? []} bestListingId={best?.listing_id} /></section><section className="content-section"><h2><span className="section-number">03</span>我的备注</h2><div className="tool-surface">
      <p className="mb-3 text-xs leading-6 text-dim">记下这条优惠的核对结论或入手计划，只属于你自己。评论来自来源文章本身，见上方优惠条件。</p>
      {(notesQuery.data?.length ?? 0) > 0 && <ul className="mb-4 space-y-3">{notesQuery.data!.map((note) => <li key={note.id} className="flex items-start justify-between gap-3 border-b border-line pb-3 text-xs"><div><p className="leading-6">{note.body}</p><p className="mt-1 text-[10px] text-dim">{timeAgo(note.created_at)}</p></div><button type="button" className="btn btn-ghost shrink-0 text-[11px]" disabled={removeNote.isPending} onClick={() => { if (window.confirm("删除这条备注？")) removeNote.mutate(note.id); }}>删除</button></li>)}</ul>}
      {notesQuery.isError && <p className="error-text">备注暂时无法加载。</p>}
      <form onSubmit={(e) => { e.preventDefault(); if (draft.trim() && !addNote.isPending) addNote.mutate(); }}><textarea className="field mb-3" rows={3} maxLength={500} placeholder="例如：已核对 88VIP 券可用，L 码有货；等 10-30 再下手" value={draft} onChange={(e) => setDraft(e.target.value)} /><div className="flex items-center justify-between gap-3"><span className="text-[10px] text-dim">{draft.length}/500</span><button type="submit" className="btn btn-ghost text-xs" disabled={!draft.trim() || addNote.isPending}>{addNote.isPending ? "保存中…" : "保存备注"}</button></div></form>
      {addNote.isError && <p className="error-text">保存失败：{addNote.error.message}</p>}
    </div></section></div><aside><div className="match-box"><h2>{confirmed && deal.variant ? "已关联到具体规格" : "这是一条待核对的装备线索"}</h2><p>{canSubscribe && confirmed && deal.variant ? "查看同一规格的渠道报价、价格历史与降价提醒。" : "补齐准确款号、颜色、尺码和可信报价后，才能关注精确降价。"}</p>{deal.variant && <Link href={`/variants/${deal.variant.variant_id}`} className="text-link">{confirmed ? "查看装备与价格历史" : "查看待补齐的装备记录"}<Icon name="arrow" /></Link>}{!canSubscribe && <button type="button" className="btn btn-ghost mt-4 w-full text-[11px]" disabled>暂不可创建精确降价提醒</button>}</div><div className="mt-4 notice"><strong>价格怎么看？</strong><br />线报价是文章报告的参考；核验报价来自已匹配且有货的渠道；返利在支付后到账。三者需分别核对。</div></aside></div>
    {related.length > 0 && <section className="detail-related"><div className="section-heading"><h2>继续看看相关线索</h2><Link href="/" className="text-link">发现更多<Icon name="arrow" /></Link></div><ul className="deal-grid">{related.map((item, index) => <DealCard key={item.id} deal={item} index={index} />)}</ul></section>}
    <div className="mobile-detail-bar"><Link href="/" className="mobile-back"><Icon name="grid" />发现</Link><div className="bar-price"><small>{best ? "当前核验到手价" : expired ? "已过期 · 线报参考" : stale ? "较早线报 · 历史参考" : "线报参考价"}</small><strong>{hasPrice(best?.effective_cents ?? deal.price_cents) ? money(best?.effective_cents ?? deal.price_cents, best?.currency ?? deal.currency) : "价格待核对"}</strong></div><a href={actionHref} target={externalAction ? "_blank" : undefined} rel={externalAction ? "noopener noreferrer" : undefined} className="btn-primary">{actionLabel}<Icon name={externalAction ? "external" : "arrow"} /></a></div>
  </main>;
}
