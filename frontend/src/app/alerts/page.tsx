"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Icon } from "@/components/Icon";
import { SiteHeader } from "@/components/SiteHeader";
import { api } from "@/lib/api";
import { specs } from "@/lib/catalog";
import { alertKindName, cny, timeAgo } from "@/lib/format";

export default function AlertsPage() {
  const client = useQueryClient();
  const [variantId, setVariantId] = useState("");
  const [target, setTarget] = useState("");
  const variants = useQuery({ queryKey: ["variants", ""], queryFn: () => api.variants() });
  const subscriptions = useQuery({ queryKey: ["subscriptions"], queryFn: api.subscriptions });
  const events = useQuery({ queryKey: ["events"], queryFn: () => api.events() });
  const selected = useQuery({ queryKey: ["variant", Number(variantId)], queryFn: () => api.variant(Number(variantId)), enabled: !!variantId });
  const validTarget = /^\d+(\.\d{1,2})?$/.test(target.trim()) && Number(target) > 0 && Number.isSafeInteger(Math.round(Number(target) * 100));
  const canCreate = selected.data?.can_subscribe === true && validTarget;
  const variantName = (id: number) => {
    const variant = variants.data?.find((item) => item.id === id);
    return variant ? [variant.style_name, ...specs(variant.color, variant.size)].join(" · ") : `装备记录 ${id}`;
  };
  const remove = useMutation({ mutationFn: api.deleteSubscription, onSuccess: () => client.invalidateQueries({ queryKey: ["subscriptions"] }) });
  const resend = useMutation({ mutationFn: api.resendEvent, onSuccess: () => client.invalidateQueries({ queryKey: ["events"] }) });
  const create = useMutation({
    mutationFn: () => api.createSubscription({ variant_id: Number(variantId), target_price_cents: Math.round(Number(target) * 100), kinds: ["price_below"] }),
    onSuccess: () => { setTarget(""); void client.invalidateQueries({ queryKey: ["subscriptions"] }); },
  });
  return <main>
    <SiteHeader kicker="PRICE WATCH" />
    <div className="tool-intro rise"><p className="eyebrow">YOUR GEAR WATCH / 慢慢选，等好价</p><h1>把心仪装备，留给合适的价格。</h1><p>在明确的颜色、尺码和可信报价上建立提醒，避免把不同规格混在一起比较。</p></div>
    <div className="detail-body"><div><section className="content-section"><h2><span className="section-number">01</span>我的价格提醒</h2><div className="tool-surface">
      {subscriptions.isPending ? <p className="micro-label" role="status">正在载入提醒…</p> : subscriptions.isError ? <p className="error-text">暂时无法加载提醒，请稍后重试。</p> : subscriptions.data?.length ? <ul className="space-y-3">{subscriptions.data.map((subscription) => <li key={subscription.id} className="flex items-center justify-between gap-4 border-b border-line pb-4 text-xs"><div><Link href={`/variants/${subscription.variant_id}`} className="font-medium hover:underline">{variantName(subscription.variant_id)}</Link><p className="mt-2 text-dim">目标 <span className="num text-accent">{cny(subscription.target_price_cents)}</span> · {subscription.kinds.map(alertKindName).join(" / ")}</p></div><button type="button" className="btn btn-ghost shrink-0 text-xs" disabled={remove.isPending} onClick={() => remove.mutate(subscription.id)}>删除</button></li>)}</ul> : <div className="py-4"><p className="mb-3 text-sm">还没有关注的装备。</p><p className="mb-4 text-xs leading-7 text-dim">先到目录挑选装备，也可以在这里选择已核验规格新建提醒。</p><Link href="/variants" className="text-link">逛逛装备目录<Icon name="arrow" /></Link></div>}
      {remove.isError && <p className="error-text">删除失败：{remove.error.message}</p>}
    </div></section><section className="content-section"><h2><span className="section-number">02</span>最近触发记录</h2><div className="tool-surface">
      {events.isPending ? <p className="micro-label" role="status">正在载入记录…</p> : events.isError ? <p className="error-text">暂时无法加载触发记录。</p> : events.data?.length ? <ul className="space-y-4">{events.data.map((event) => <li key={event.id} className="border-b border-line pb-4 text-xs"><div className="mb-2 flex items-center justify-between gap-3"><span className="badge badge-verified">{alertKindName(event.kind)}</span>{event.sent_at ? <span className="text-[10px] text-dim">已发送 · {timeAgo(event.sent_at)}</span> : <button type="button" className="text-link" disabled={resend.isPending} onClick={() => resend.mutate(event.id)}>发送通知</button>}</div><Link href={`/variants/${event.variant_id}`} className="leading-7 hover:underline">{variantName(event.variant_id)}</Link>{typeof event.payload.price_cents === "number" && <span className="num ml-2 text-accent">{cny(event.payload.price_cents)}</span>}{event.send_error && <p className="error-text">{event.send_error}</p>}</li>)}</ul> : <p className="text-xs leading-7 text-dim">还没有触发记录。达到你设定的条件后，记录会显示在这里。</p>}
      {resend.isError && <p className="error-text">发送失败：{resend.error.message}</p>}{resend.data && !resend.data.ok && <p className="error-text">发送失败：{resend.data.error || "请检查通知配置"}</p>}
    </div></section></div>
    <aside><section className="subscribe-box"><h2><Icon name="bell" />新建价格提醒</h2><p>选择具体规格，设置人民币目标到手价。</p><form onSubmit={(e) => { e.preventDefault(); if (canCreate && !create.isPending) create.mutate(); }}><label htmlFor="watch-variant">选择装备</label><select id="watch-variant" className="field mb-4" value={variantId} onChange={(e) => { setVariantId(e.target.value); create.reset(); }} required><option value="">选择装备规格…</option>{(variants.data ?? []).map((variant) => <option key={variant.id} value={variant.id}>{variantName(variant.id)}</option>)}</select>{variants.isError && <p className="error-text">装备目录暂时无法加载。</p>}{variantId && selected.isPending && <p className="mb-3" role="status">正在确认规格与报价状态…</p>}{variantId && selected.isError && <p className="mb-3 error-text">暂时无法确认该装备状态，请稍后重试。</p>}{selected.data && selected.data.can_subscribe !== true && <p className="notice mb-4">该装备的规格或报价仍待核验。补齐颜色、尺码和可信报价后，才能关注精确降价。</p>}<label htmlFor="watch-target">目标到手价（人民币元）</label><input id="watch-target" className="field" inputMode="decimal" placeholder="例如 800.00" value={target} onChange={(e) => setTarget(e.target.value)} required />{target && !validTarget && <p className="error-text">请输入大于 0 的金额，最多两位小数。</p>}<button type="submit" className="btn-primary mt-4 w-full" disabled={!canCreate || create.isPending}>{create.isPending ? "保存中…" : "创建提醒"}</button>{create.isError && <p className="error-text">创建失败：{create.error.message}</p>}{create.isSuccess && <p className="success-text" role="status">提醒已保存。</p>}</form></section><div className="notice mt-4">历史样本至少积累 14 天才判断历史新低。返利事后到账，具体领取与支付条件请以渠道说明为准。</div></aside></div>
  </main>;
}
