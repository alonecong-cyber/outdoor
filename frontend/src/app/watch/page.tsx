"use client";

import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { SiteHeader } from "@/components/SiteHeader";
import { api, type WatchItem } from "@/lib/api";
import { alertKindName, cny, timeAgo } from "@/lib/format";

function splitList(value: string): string[] {
  return value.split(/[,，、\s]+/).map((item) => item.trim()).filter(Boolean);
}

export default function WatchPage() {
  const client = useQueryClient();
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const [mustWords, setMustWords] = useState("");
  const [excludeWords, setExcludeWords] = useState("");
  const [target, setTarget] = useState("");
  const [platforms, setPlatforms] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);

  // 从榜单「关注降价」跳转时预填名称与关键词
  useEffect(() => {
    const p = new URLSearchParams(window.location.search);
    const n = p.get("name");
    if (n) setName(n);
    const k = p.get("keywords");
    if (k) setKeywords(k);
    if (n || k) document.getElementById("watch-target")?.focus();
  }, []);
  const watches = useQuery({ queryKey: ["watches"], queryFn: api.watches });
  const selected = watches.data?.find((watch) => watch.id === selectedId) ?? null;
  const alerts = useQuery({
    queryKey: ["watch-alerts", selectedId],
    queryFn: () => api.watchAlerts(selectedId as number),
    enabled: selectedId != null,
  });

  const invalidate = () => {
    void client.invalidateQueries({ queryKey: ["watches"] });
    void client.invalidateQueries({ queryKey: ["watch-alerts"] });
  };
  const create = useMutation({ mutationFn: api.createWatch, onSuccess: () => { setName(""); setKeywords(""); setMustWords(""); setExcludeWords(""); setTarget(""); setPlatforms(""); invalidate(); } });
  const toggle = useMutation({ mutationFn: (watch: WatchItem) => api.setWatchActive(watch.id, !watch.active), onSuccess: invalidate });
  const remove = useMutation({ mutationFn: api.deleteWatch, onSuccess: () => { if (selectedId != null) setSelectedId(null); invalidate(); } });
  const check = useMutation({ mutationFn: api.checkWatches, onSuccess: invalidate });

  const validTarget = target.trim() === "" || (/^\d+(\.\d{1,2})?$/.test(target.trim()) && Number(target) > 0);
  const canCreate = name.trim().length > 0 && validTarget && (splitList(keywords).length > 0 || true);
  const body = () => ({
    name: name.trim(),
    keywords: splitList(keywords),
    must_words: splitList(mustWords),
    exclude_words: splitList(excludeWords),
    target_price: target.trim() === "" ? 0 : Number(target),
    platforms: splitList(platforms),
  });

  return <main>
    <SiteHeader kicker="MY WATCH" />
    <div className="tool-intro rise"><p className="eyebrow">MY GEAR WATCH / 关注一类好价</p><h1>盯住一类装备，等对的价格。</h1><p>按关键词关注一类线报；后台每次更新线报后自动检查，达到目标价或出现新低时记录提醒。精确到色码的提醒仍走「降价提醒」。</p></div>
    <div className="detail-body"><div>
      <section className="content-section"><h2><span className="section-number">01</span>我的关注</h2><div className="tool-surface">
        <div className="mb-4 flex items-center justify-between gap-3">
          <p className="text-xs text-dim">只匹配站内线报的人民币报价；海外原币价单列计数，不混算。</p>
          <button type="button" className="btn btn-ghost shrink-0 text-xs" disabled={check.isPending} onClick={() => check.mutate()}>{check.isPending ? "检查中…" : "立即检查"}</button>
        </div>
        {check.isSuccess && <p className="success-text" role="status">本轮检查 {check.data.checked} 个关注，触发 {check.data.triggered} 条记录。</p>}
        {check.isError && <p className="error-text">检查失败：{check.error.message}</p>}
        {watches.isPending ? <p className="micro-label" role="status">正在载入关注…</p> : watches.isError ? <p className="error-text">暂时无法载入关注，请稍后重试。</p> : watches.data?.length ? <ul className="space-y-3">{watches.data.map((watch) => <li key={watch.id} className={`border-b border-line pb-4 text-xs ${selectedId === watch.id ? "watch-item-selected" : ""}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <button type="button" className="text-left font-medium hover:underline" onClick={() => setSelectedId(selectedId === watch.id ? null : watch.id)}>{watch.name}</button>
                <span className={`badge ${watch.active ? "badge-verified" : "badge-reported"}`}>{watch.active ? "关注中" : "已暂停"}</span>
                {watch.target_price_cents > 0 && <span className="num text-accent">目标 {cny(watch.target_price_cents)}</span>}
              </div>
              <p className="mt-2 leading-6 text-dim">关键词：{watch.keywords.length ? watch.keywords.join(" / ") : watch.name}{watch.platforms.length > 0 && <span> · 渠道：{watch.platforms.join(" / ")}</span>}{watch.exclude_words.length > 0 && <span> · 排除：{watch.exclude_words.join(" / ")}</span>}</p>
              <p className="mt-1 leading-6 text-dim">{watch.last_checked_at ? `最近检查 ${timeAgo(watch.last_checked_at)} · ` : ""}{watch.last_result || "尚未检查"}</p>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-2">
              <div className="flex gap-2">
                <button type="button" className="btn btn-ghost text-xs" disabled={toggle.isPending} onClick={() => toggle.mutate(watch)}>{watch.active ? "暂停" : "恢复"}</button>
                <button type="button" className="btn btn-ghost text-xs" disabled={remove.isPending} onClick={() => { if (window.confirm(`删除关注「${watch.name}」？`)) remove.mutate(watch.id); }}>删除</button>
              </div>
              <button type="button" className="text-link" onClick={() => setSelectedId(selectedId === watch.id ? null : watch.id)}>{selectedId === watch.id ? "收起记录" : "命中记录"}</button>
            </div>
          </div>
        </li>)}</ul> : <div className="py-4"><p className="mb-3 text-sm">还没有关注任何一类装备。</p><p className="mb-4 text-xs leading-7 text-dim">在右侧填一个名字和几个关键词，比如「始祖鸟 Beta AR」，设一个目标价，之后线报一更新就会自动检查。</p><Link href="/variants" className="text-link">先逛逛装备目录<Icon name="arrow" /></Link></div>}
        {remove.isError && <p className="error-text">删除失败：{remove.error.message}</p>}
      </div></section>
      <section className="content-section"><h2><span className="section-number">02</span>命中记录</h2><div className="tool-surface">
        {selected == null ? <p className="text-xs leading-7 text-dim">点上方任一关注的「命中记录」，查看为什么提醒、当时线报是多少钱。</p> : alerts.isPending ? <p className="micro-label" role="status">正在载入记录…</p> : alerts.isError ? <p className="error-text">暂时无法载入记录。</p> : alerts.data?.length ? <ul className="space-y-4">{alerts.data.map((alert) => <li key={alert.id} className="border-b border-line pb-4 text-xs">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
            <span className={`badge ${alert.kind === "target_hit" ? "badge-verified" : "badge-reported"}`}>{alertKindName(alert.kind)}</span>
            <span className="text-[11px] text-dim">{timeAgo(alert.created_at)}</span>
          </div>
          <p className="num mb-2 text-accent">{cny(alert.price_cents)}</p>
          <p className="leading-7">{alert.reason}</p>
          {alert.deal_url && <a href={alert.deal_url} target="_blank" rel="noopener noreferrer" className="text-link mt-2 inline-flex items-center gap-1">查看线报原文<Icon name="external" /></a>}
        </li>)}</ul> : <p className="text-xs leading-7 text-dim">「{selected.name}」还没有命中记录。达到目标价或出现新低后会记录在这里。</p>}
      </div></section>
    </div>
    <aside>
      <section className="subscribe-box"><h2><Icon name="bell" />新建关注</h2><p>关注一类装备的线报，而不是单个色码。</p>
        <form onSubmit={(e) => { e.preventDefault(); if (canCreate && !create.isPending) create.mutate(body()); }}>
          <label htmlFor="watch-name">名称</label>
          <input id="watch-name" className="field mb-4" placeholder="例如：始祖鸟 Beta AR" value={name} onChange={(e) => setName(e.target.value)} required />
          <label htmlFor="watch-keywords">关键词（任一命中即算匹配）</label>
          <input id="watch-keywords" className="field mb-4" placeholder="始祖鸟 Beta AR, Arc'teryx Beta AR" value={keywords} onChange={(e) => setKeywords(e.target.value)} required />
          <label htmlFor="watch-must">必含词（都要出现，可留空）</label>
          <input id="watch-must" className="field mb-4" placeholder="Beta AR" value={mustWords} onChange={(e) => setMustWords(e.target.value)} />
          <label htmlFor="watch-exclude">排除词（出现即忽略，如「保护套」）</label>
          <input id="watch-exclude" className="field mb-4" value={excludeWords} onChange={(e) => setExcludeWords(e.target.value)} />
          <label htmlFor="watch-platforms">限定渠道（可留空，如 京东 / 天猫）</label>
          <input id="watch-platforms" className="field mb-4" value={platforms} onChange={(e) => setPlatforms(e.target.value)} />
          <label htmlFor="watch-target">目标价（人民币元，可留空）</label>
          <input id="watch-target" className="field" inputMode="decimal" placeholder="例如 800.00" value={target} onChange={(e) => setTarget(e.target.value)} />
          {target.trim() !== "" && !validTarget && <p className="error-text">请输入大于 0 的金额，最多两位小数。</p>}
          <button type="submit" className="btn-primary mt-4 w-full" disabled={!canCreate || create.isPending}>{create.isPending ? "保存中…" : "开始关注"}</button>
          {create.isError && <p className="error-text">创建失败：{create.error.message}</p>}
          {create.isSuccess && <p className="success-text" role="status">关注已保存，下一次线报更新时自动检查。</p>}
        </form>
      </section>
      <div className="notice mt-4"><strong>提醒怎么算？</strong><br />达到目标价、自开始记录以来出现新低各算一条；同一线报 24 小时内不重复提醒。提醒只记录在站内，配置通知渠道后可外发。</div>
    </aside>
    </div>
  </main>;
}
