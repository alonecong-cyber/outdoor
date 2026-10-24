"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { SiteHeader } from "@/components/SiteHeader";
import { api, type DealItem } from "@/lib/api";
import { channelName, money, timeAgo } from "@/lib/format";

const BRANDS = [
  { slug: "", label: "全部" },
  { slug: "arcteryx", label: "始祖鸟" },
  { slug: "the-north-face", label: "北面" },
  { slug: "patagonia", label: "巴塔哥尼亚" },
  { slug: "columbia", label: "哥伦比亚" },
  { slug: "camel", label: "骆驼" },
  { slug: "pelliot", label: "伯希和" },
  { slug: "kailas", label: "凯乐石" },
  { slug: "mammut", label: "猛犸象" },
  { slug: "marmot", label: "土拨鼠" },
];

function DealCard({ deal, index }: { deal: DealItem; index: number }) {
  const variant = deal.variant;
  const ratingTag = deal.tags.find((t) => t.includes("好评率"));
  const lowTag = deal.tags.find((t) => t.includes("新低") || t.includes("低价") || t.includes("低于"));
  const hotTag = deal.tags.find((t) => t.includes("热度"));
  return (
    <li className={`rise rise-${(index % 5) + 1}`}>
      <article className="card p-4">
        <div className="flex items-center gap-2">
          <span className="rounded-sm bg-panel-2 px-1.5 py-0.5 text-[11px] text-ink">
            {channelName(deal.channel)}
          </span>
          {ratingTag && (
            <span className="rounded-sm border border-moss/60 px-1.5 py-0.5 text-[11px] text-moss">
              {ratingTag}
            </span>
          )}
          {lowTag && (
            <span className="rounded-sm border border-accent-soft px-1.5 py-0.5 text-[11px] text-accent">
              {lowTag}
            </span>
          )}
          {hotTag && (
            <span className="rounded-sm border border-line px-1.5 py-0.5 text-[11px] text-dim">
              {hotTag}
            </span>
          )}
          <span className="micro-label ml-auto">{timeAgo(deal.published_at)}</span>
          <a
            href={deal.url}
            target="_blank"
            rel="noreferrer"
            className="micro-label shrink-0 text-dim hover:text-accent"
          >
            原文 ↗
          </a>
        </div>

        <div className="mt-2.5 flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold leading-snug">{deal.title}</h2>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              {deal.price_cents > 0 ? (
                <span className="num font-display text-xl font-bold text-accent">
                  {money(deal.price_cents, deal.currency)}
                </span>
              ) : (
                <span className="micro-label">见原文</span>
              )}
              {variant && (
                <Link
                  href={`/variants/${variant.variant_id}`}
                  className="rounded-sm border border-accent-soft px-1.5 py-0.5 text-[11px] text-accent hover:bg-accent-soft/20"
                >
                  {variant.brand_name} #{variant.style_number}
                </Link>
              )}
            </div>
          </div>
          {deal.image && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={deal.image}
              alt=""
              loading="lazy"
              className="h-16 w-16 shrink-0 rounded-sm border border-line object-cover"
              onError={(e) => {
                (e.target as HTMLImageElement).style.display = "none";
              }}
            />
          )}
        </div>
      </article>
    </li>
  );
}

/** 线报流首页：smzdm 优惠线报，商品从线报里长出来。 */
export default function DealFeedPage() {
  const [brand, setBrand] = useState("");
  const [q, setQ] = useState("");
  const queryClient = useQueryClient();

  const dealsQuery = useQuery({
    queryKey: ["deals", brand],
    queryFn: () => api.deals(brand ? { brand } : { limit: 100 }),
  });

  const ingest = useMutation({
    mutationFn: () => api.ingestDeals(5),
    onSuccess: (res) => {
      void queryClient.invalidateQueries({ queryKey: ["deals"] });
      void queryClient.invalidateQueries({ queryKey: ["variants"] });
      return res;
    },
  });

  const deals = dealsQuery.data ?? [];
  const filtered = useMemo(
    () => (q ? deals.filter((d) => d.title.toLowerCase().includes(q.toLowerCase())) : deals),
    [deals, q],
  );

  const ingestNote = ingest.isPending
    ? "正在拉取线报（约 1 分钟）…"
    : ingest.isError
      ? `拉取失败：${(ingest.error as Error).message}`
      : ingest.data
        ? ingest.data.ok
          ? `新拉取 ${ingest.data.created} 条线报`
          : `拉取失败：${ingest.data.errors[0] ?? "未知错误"}`
        : null;

  return (
    <main>
      <SiteHeader kicker="FEED" />

      <div className="rise rise-1 mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex flex-wrap gap-2">
          {BRANDS.map((b) => (
            <button
              key={b.slug}
              type="button"
              onClick={() => setBrand(b.slug)}
              className={`btn rounded-full px-3.5 py-1.5 text-xs ${
                brand === b.slug
                  ? "bg-accent text-[#140b06]"
                  : "border border-line text-dim hover:text-ink"
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
        <input
          className="field sm:ml-auto sm:max-w-56"
          placeholder="搜线报…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      <div className="rise rise-2 mb-4 flex items-center gap-3">
        <button
          type="button"
          onClick={() => ingest.mutate()}
          disabled={ingest.isPending}
          className="btn-primary w-full py-2.5 text-sm"
        >
          {ingest.isPending ? "拉取中…" : "⚡ 拉取最新线报"}
        </button>
      </div>
      {ingestNote && <p className="micro-label mb-4">{ingestNote}</p>}

      {dealsQuery.isLoading && <p className="micro-label">载入线报…</p>}
      {dealsQuery.isError && (
        <p className="text-sm text-accent">后端不可达：{(dealsQuery.error as Error).message}</p>
      )}

      <ul className="space-y-3">
        {filtered.map((d, i) => (
          <DealCard key={d.id} deal={d} index={i} />
        ))}
      </ul>

      {filtered.length === 0 && !dealsQuery.isLoading && !ingest.isPending && (
        <div className="card rise rise-3 flex flex-col items-center gap-4 p-8 text-center">
          <p className="text-sm text-dim">还没有线报。拉取一轮 smzdm 最新优惠，商品会自动从线报里长出来。</p>
          <button
            type="button"
            onClick={() => ingest.mutate()}
            className="btn-primary px-6 py-2.5 text-sm"
          >
            ⚡ 拉取最新线报
          </button>
        </div>
      )}
    </main>
  );
}
