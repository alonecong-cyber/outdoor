"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { ChannelQuoteCard } from "@/components/ChannelQuoteCard";
import { ProductImage } from "@/components/ProductImage";
import { SiteHeader } from "@/components/SiteHeader";
import { Sparkline } from "@/components/Sparkline";
import { api, type ChannelQuote } from "@/lib/api";
import { cny, alertKindName, channelName, money, timeAgo } from "@/lib/format";

function SubscribeBox({ variantId }: { variantId: number }) {
  const qc = useQueryClient();
  const [target, setTarget] = useState("");
  const [kinds, setKinds] = useState<string[]>(["price_below"]);

  const subs = useQuery({ queryKey: ["subscriptions"], queryFn: api.subscriptions });
  const mine = (subs.data ?? []).filter((s) => s.variant_id === variantId);

  const create = useMutation({
    mutationFn: () =>
      api.createSubscription({
        variant_id: variantId,
        target_price_cents: Math.round(parseFloat(target) * 100),
        kinds,
      }),
    onSuccess: () => {
      setTarget("");
      qc.invalidateQueries({ queryKey: ["subscriptions"] });
    },
  });
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });

  const toggle = (k: string) =>
    setKinds((prev) => (prev.includes(k) ? prev.filter((x) => x !== k) : [...prev, k]));

  return (
    <section className="card p-4">
      <p className="micro-label">降价提醒</p>
      <div className="mt-3 space-y-3">
        <div className="flex flex-wrap gap-2">
          {[
            { id: "price_below", label: "低于目标价" },
            { id: "new_low", label: "历史新低" },
          ].map((k) => (
            <button
              key={k.id}
              type="button"
              onClick={() => toggle(k.id)}
              className={`btn rounded-full px-3 py-1.5 text-xs ${
                kinds.includes(k.id)
                  ? "bg-accent text-[#140b06]"
                  : "border border-line text-dim hover:text-ink"
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <input
            className="field"
            placeholder="目标价，如 3500"
            inputMode="decimal"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
          <button
            type="button"
            className="btn btn-primary shrink-0"
            disabled={!target || create.isPending || kinds.length === 0}
            onClick={() => create.mutate()}
          >
            订阅
          </button>
        </div>
        {create.isError && <p className="text-xs text-accent">{(create.error as Error).message}</p>}
        <ul className="space-y-1.5">
          {mine.map((s) => (
            <li key={s.id} className="flex items-center justify-between rounded-sm border border-line px-3 py-1.5 text-sm">
              <span>
                <span className="num">{cny(s.target_price_cents)}</span>
                <span className="micro-label ml-2">
                  {s.kinds.map((k) => alertKindName(k)).join(" / ")}
                </span>
              </span>
              <button
                type="button"
                className="btn text-xs text-dim hover:text-accent"
                onClick={() => remove.mutate(s.id)}
              >
                删除
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export default function VariantPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);
  const detail = useQuery({ queryKey: ["variant", id], queryFn: () => api.variant(id) });

  if (detail.isLoading) {
    return (
      <main>
        <SiteHeader />
        <p className="micro-label">载入商品…</p>
      </main>
    );
  }
  if (detail.isError || !detail.data) {
    return (
      <main>
        <SiteHeader />
        <p className="text-sm text-accent">载入失败：{(detail.error as Error)?.message ?? "未知"}</p>
      </main>
    );
  }

  const v = detail.data;
  const heroImage = v.channels.find((c) => c.image)?.image ?? v.image;
  const dealPoints = v.deals.filter((d) => d.price_cents > 0);
  const live = v.channels.filter((c) => c.price_cents != null);
  // 跨币种不可直接比：最低徽章只在国内人民币渠道里选，没有再退到外币渠道
  const cnyLive = live.filter((c) => c.currency === "CNY");
  const cheapest = (cnyLive.length > 0 ? cnyLive : live).reduce<ChannelQuote | undefined>(
    (a, b) => ((a?.price_cents ?? Infinity) <= (b.price_cents ?? Infinity) ? a : b),
    undefined,
  );
  // 人民币渠道按价由低到高；外币渠道单列在后（折算交给海淘计算器）
  const sorted = [
    ...[...cnyLive].sort((a, b) => (a.price_cents ?? 0) - (b.price_cents ?? 0)),
    ...live
      .filter((c) => c.currency !== "CNY")
      .sort((a, b) => (a.price_cents ?? 0) - (b.price_cents ?? 0)),
  ];

  return (
    <main>
      <SiteHeader kicker={`#${v.style_number}`} />

      <section className="rise card mb-4 overflow-hidden">
        {heroImage && (
          <ProductImage
            src={heroImage}
            alt={`${v.style_name} ${v.color}`}
            className="h-52 w-full object-cover sm:h-64"
          />
        )}
        <div className="p-5">
          <p className="micro-label">{v.brand}</p>
          <h1 className="font-display mt-1 text-2xl font-black tracking-tight">{v.style_name}</h1>
          <div className="mt-2 flex flex-wrap gap-2 text-sm text-dim">
            <span className="rounded-sm border border-line px-2 py-0.5">{v.color}</span>
            <span className="rounded-sm border border-line px-2 py-0.5">尺码 {v.size}</span>
            {cheapest && (
              <span className="rounded-sm border border-accent px-2 py-0.5 text-ink">
                最低 <span className="num text-accent">{money(cheapest.price_cents, cheapest.currency)}</span> ·{" "}
                {channelName(cheapest.channel)}
              </span>
            )}
          </div>
        </div>
      </section>

      <section className="rise rise-2 mb-4 space-y-3">
        <p className="micro-label">各渠道现价{cnyLive.length > 0 ? "（人民币渠道由低到高，外币渠道单列）" : ""}</p>
        {v.channels.length === 0 && <p className="text-sm text-dim">该款暂无渠道 listing。</p>}        {sorted.map((c) => {
          const isMin = cheapest && c.listing_id === cheapest.listing_id;
          const isCny = c.currency === "CNY";
          return (
            <article key={c.listing_id} className={`card p-4 ${isMin ? "border-accent/70" : ""}`}>
              <div className="flex items-start gap-3">
                <ProductImage
                  src={c.image}
                  alt={c.title || channelName(c.channel)}
                  className="h-14 w-14 shrink-0 rounded-sm border border-line object-cover"
                />
                <div className="min-w-0 flex-1">
                  <h2 className="font-display text-sm font-bold">
                    {channelName(c.channel)}
                    {isMin && <span className="micro-label ml-2 text-accent">当前最低</span>}
                  </h2>
                  <a
                    href={c.url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block truncate text-xs text-dim underline-offset-2 hover:text-ink hover:underline"
                  >
                    {c.title || c.url}
                  </a>
                </div>
                <div className="shrink-0 text-right">
                  <p className="num text-lg font-semibold">{money(c.price_cents, c.currency)}</p>
                  <p className={`micro-label ${c.in_stock === false ? "text-accent" : "text-moss"}`}>
                    {c.in_stock === false ? "缺货" : "有货"}
                  </p>
                </div>
              </div>
              {c.history.length >= 2 && (
                <div className="mt-3 border-t border-line pt-2">
                  <Sparkline points={c.history} width={280} height={44} />
                </div>
              )}
              {isCny ? (
                <ChannelQuoteCard
                  listingId={c.listing_id}
                  channel={channelName(c.channel)}
                  priceCents={c.price_cents}
                  currency={c.currency}
                />
              ) : (
                <Link
                  href={`/calculator?tab=overseas&usd=${((c.price_cents ?? 0) / 100).toFixed(2)}`}
                  className="btn mt-3 w-full border border-line py-2 text-xs text-dim hover:border-dim hover:text-ink"
                >
                  外币渠道 · 去海淘到手价计算器 →
                </Link>
              )}
            </article>
          );
        })}
      </section>

      {v.deals.length > 0 && (
        <section className="rise rise-3 mb-4 space-y-3">
          <p className="micro-label">同款线报价格点（{v.deals.length}）</p>
          {v.deals.map((d) => (
            <article key={d.id} className="card p-3.5">
              <div className="flex items-center gap-2">
                <span className="rounded-sm bg-panel-2 px-1.5 py-0.5 text-[11px] text-ink">
                  {channelName(d.channel)}
                </span>
                <span className="micro-label">{timeAgo(d.published_at)}</span>
                {d.price_cents > 0 && (
                  <span className="num ml-auto text-base font-semibold text-accent">
                    {money(d.price_cents, "CNY")}
                  </span>
                )}
                <a
                  href={d.url}
                  target="_blank"
                  rel="noreferrer"
                  className="micro-label shrink-0 text-dim hover:text-accent"
                >
                  原文 ↗
                </a>
              </div>
              <p className="mt-1.5 line-clamp-2 text-sm text-dim">{d.title}</p>
            </article>
          ))}
          {dealPoints.length >= 2 && (
            <div className="card p-3.5">
              <p className="micro-label mb-2">线报价格走势</p>
              <Sparkline points={dealPoints.map((d) => ({
                ts: d.published_at ?? "",
                price_cents: d.price_cents,
              }))} width={280} height={44} />
            </div>
          )}
        </section>
      )}

      <div className="rise rise-3">
        <SubscribeBox variantId={v.id} />
      </div>
    </main>
  );
}
