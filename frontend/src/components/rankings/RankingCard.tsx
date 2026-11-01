"use client";

import { useState } from "react";
import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";

export const TIER_STYLE: Record<string, string> = {
  budget: "bg-[#e8eee2] text-[#2e5631] border-[#cbd8bf]",
  mid: "bg-[#e6eef5] text-[#2b4c68] border-[#bed0e2]",
  flagship: "bg-[#f7eee3] text-[#7e4a1a] border-[#e8cfb5]",
};

/** 本地图 → 原站图 → 占位图，三级回退，保证每张卡片都有图。 */
export function GearImage({ item, className }: { item: GearRankingItem; className?: string }) {
  const chain = [item.image, item.image_remote, "/products/placeholder.svg"].filter(Boolean) as string[];
  const [idx, setIdx] = useState(0);
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={chain[Math.min(idx, chain.length - 1)]}
      alt={item.name_cn}
      className={className}
      loading="lazy"
      onError={() => setIdx((i) => (i < chain.length - 1 ? i + 1 : i))}
    />
  );
}

const PLATFORM_COLORS: Record<string, string> = {
  什么值得买: "#c8102e",
  B站: "#fb7299",
  小红书: "#ff2442",
};

export function shortSource(source: string) {
  return source === "Switchback Travel" ? "Switchback" : source === "OutdoorGearLab" ? "OGL" : source;
}

export function fmtCount(n?: number) {
  if (!n) return "";
  return n >= 10000 ? `${(n / 10000).toFixed(1)}万` : String(n);
}

export function cnPriceLabel(item: GearRankingItem) {
  const p = item.cn_price;
  if (!p) return "";
  const f = (v: number) => `¥${Math.round(v).toLocaleString()}`;
  return p.min_cny === p.median_cny ? f(p.min_cny) : `${f(p.min_cny)}~${f(p.median_cny)}`;
}

export function rankLabel(a: { rank?: number | null; rank_total?: number | null }) {
  return a.rank ? `#${a.rank}${a.rank_total ? `/${a.rank_total}` : ""}` : "";
}

export const isCnPick = (item: GearRankingItem) => item.id.startsWith("cn_");

/** 国内口碑内容列表：什么值得买原创/好价、B站视频、小红书笔记。 */
export function CnReviewList({ item, limit = 6 }: { item: GearRankingItem; limit?: number }) {
  const rows = (item.cn_reviews ?? []).slice(0, limit);
  if (!rows.length) return null;
  return (
    <ul className="divide-y divide-line">
      {rows.map((c) => (
        <li key={c.url}>
          <a
            href={c.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group flex items-start gap-2 py-2 text-[13px] leading-snug"
            title={c.summary || c.title}
          >
            <span
              className="mt-0.5 shrink-0 rounded px-1.5 py-px text-[11px] text-white"
              style={{ background: PLATFORM_COLORS[c.platform] || "#4a5547" }}
            >
              {c.platform === "什么值得买" ? "值得买" : c.platform}·{c.kind}
            </span>
            <span className="line-clamp-2 flex-1 text-ink group-hover:underline">{c.title}</span>
            <span className="shrink-0 font-mono text-xs text-dim">
              {c.price_cny ? `¥${Math.round(c.price_cny)}` : c.metric_value ? `${c.metric_label}${fmtCount(c.metric_value)}` : ""}
            </span>
          </a>
        </li>
      ))}
    </ul>
  );
}

/** 卡片 / 详情共用的价格摘要：主价格 + 次要价格行。 */
export function PriceSummary({ item, compact = false }: { item: GearRankingItem; compact?: boolean }) {
  const g = item.price_guide;
  const cn = cnPriceLabel(item);
  const rows: { label: string; value: string; tone?: string; title?: string }[] = [];
  if (g.overseas_usd && cn) rows.push({ label: `国内好价 · 值得买 ${item.cn_price?.count} 条`, value: cn, tone: "text-accent", title: `检索词「${item.cn_query}」，已剔除离群价` });
  if (g.overseas_landed_cny) rows.push({ label: "海淘落地（含转运+税）", value: g.overseas_landed_cny, title: g.promo_tips });
  return (
    <div>
      <div className="flex items-baseline gap-2">
        <span className={`font-mono font-semibold tracking-tight text-accent ${compact ? "text-xl" : "text-3xl"}`}>
          {g.overseas_usd || cn || g.deal_cny}
        </span>
        <span className="text-xs text-dim">
          {g.overseas_usd ? `美标价 ${g.deal_cny}` : `国内好价${item.cn_price ? ` · ${item.cn_price.count} 条` : ""}`}
        </span>
      </div>
      {rows.length > 0 && (
        <dl className={`mt-1.5 space-y-0.5 ${compact ? "text-xs" : "text-[13px]"}`}>
          {rows.map((r) => (
            <div key={r.label} className="flex justify-between gap-3" title={r.title}>
              <dt className="truncate text-dim">{r.label}</dt>
              <dd className={`shrink-0 font-mono font-medium ${r.tone ?? "text-ink"}`}>{r.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </div>
  );
}

export function ScoreBars({ item, limit }: { item: GearRankingItem; limit?: number }) {
  const zh = item.sub_scores_zh ?? {};
  const rows = Object.entries(item.sub_scores ?? {}).slice(0, limit);
  if (!rows.length) return null;
  return (
    <ul className="space-y-1.5">
      {rows.map(([k, v]) => (
        <li key={k} className="grid grid-cols-[6.5rem_1fr_2rem] items-center gap-2 text-xs text-ink/80">
          <span className="truncate" title={k}>{zh[k] || k}</span>
          <span className="h-1.5 rounded-full bg-panel-2">
            <span className="block h-1.5 rounded-full bg-forest" style={{ width: `${v * 10}%` }} />
          </span>
          <span className="text-right font-mono">{v.toFixed(1)}</span>
        </li>
      ))}
    </ul>
  );
}

export function CompareToggle({ selected, onClick, className = "" }: { selected: boolean; onClick: () => void; className?: string }) {
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); onClick(); }}
      aria-pressed={selected}
      className={`inline-flex min-h-9 items-center justify-center gap-1.5 rounded-md border px-3 text-[13px] font-medium transition-colors ${
        selected ? "border-forest bg-forest text-white" : "border-line bg-panel text-ink hover:border-forest"
      } ${className}`}
    >
      <Icon name={selected ? "check" : "compare"} className="!h-4 !w-4" />
      {selected ? "已加入对比" : "加入对比"}
    </button>
  );
}

export function RankingCard({
  item,
  rank,
  selected,
  onToggleSelect,
  onOpen,
}: {
  item: GearRankingItem;
  rank?: number;
  selected: boolean;
  onToggleSelect: (id: string) => void;
  onOpen: (item: GearRankingItem) => void;
}) {
  const top = item.authorities[0];
  const more = item.authorities.length - 1;
  return (
    <article
      className={`group relative flex flex-col overflow-hidden rounded-lg border bg-panel transition-[border-color,box-shadow,transform] duration-200 hover:-translate-y-0.5 hover:shadow-[0_8px_24px_#1c38250f] ${
        selected ? "border-forest ring-2 ring-forest/30" : "border-line hover:border-[#a4b59b]"
      }`}
    >
      <button
        type="button"
        onClick={() => onOpen(item)}
        className="flex flex-1 flex-row text-left sm:flex-col"
        aria-label={`查看详情：${item.name_cn}`}
      >
        <div className="relative w-[38%] shrink-0 overflow-hidden border-r border-[#eceee5] bg-white sm:aspect-[4/3] sm:w-full sm:border-b sm:border-r-0">
          <GearImage item={item} className="absolute inset-0 h-full w-full object-contain p-3 transition-transform duration-300 group-hover:scale-[1.04]" />
          <div className="absolute left-2 top-2 flex flex-wrap gap-1 sm:left-2.5 sm:top-2.5 sm:gap-1.5">
            {rank != null && (
              <span className="rounded bg-ink/85 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-white">No.{rank}</span>
            )}
            <span className={`rounded border px-1.5 py-0.5 text-[11px] font-semibold ${TIER_STYLE[item.price_tier] ?? TIER_STYLE.budget}`}>
              {item.price_tier_name}
            </span>
            {item.is_cn_brand && <span className="rounded bg-accent px-1.5 py-0.5 text-[11px] font-semibold text-white">国货</span>}
          </div>
          <div className="absolute bottom-2 left-2 sm:bottom-auto sm:left-auto sm:right-2.5 sm:top-2.5" title={item.score_basis}>
            {item.rating_score ? (
              <span className="flex h-10 w-10 flex-col items-center justify-center rounded-full bg-forest text-white shadow sm:h-11 sm:w-11">
                <span className="font-mono text-base font-bold leading-none">{item.rating_score}</span>
                <span className="text-[11px] leading-tight opacity-80">实测分</span>
              </span>
            ) : (
              <span className="rounded bg-[#2b4c68] px-1.5 py-0.5 text-[11px] font-semibold text-white">
                {isCnPick(item) ? "国内口碑" : "编辑推荐"}
              </span>
            )}
          </div>
          {item.image_credit && (
            <span className="absolute bottom-1 right-1.5 hidden sm:inline rounded bg-black/35 px-1 text-[11px] text-white/90">图：{item.image_credit}</span>
          )}
        </div>

        <div className="flex min-w-0 flex-1 flex-col gap-2 p-3 sm:gap-2.5 sm:p-4">
          <div>
            <p className="flex justify-between gap-2 text-xs text-dim">
              <span className="truncate">{item.brand_name}{item.brand_country ? ` · ${item.brand_country}` : ""}</span>
              <span className="shrink-0">{[item.gender_name, item.category_name].filter(Boolean).join(" · ")}</span>
            </p>
            <h3 className="mt-1 line-clamp-2 text-[15px] font-semibold leading-snug text-ink">{item.name_cn}</h3>
            <p className="truncate font-mono text-xs text-dim">{item.name}</p>
          </div>

          {top && (
            <p className="flex items-center gap-1.5 text-xs text-[#335338]">
              <Icon name="award" className="!h-4 !w-4 shrink-0 text-forest" />
              <span className="truncate">
                <strong className="font-semibold">{shortSource(top.source)} {rankLabel(top)}</strong> {top.badge_zh || top.badge}
              </span>
              {more > 0 && <span className="shrink-0 rounded bg-panel-2 px-1.5 text-[11px] text-dim">+{more} 榜</span>}
            </p>
          )}

          <div className="rounded-md bg-bg px-2.5 py-2 sm:px-3 sm:py-2.5">
            <PriceSummary item={item} compact />
          </div>

          <div className="hidden sm:block"><ScoreBars item={item} limit={3} /></div>

          <div className="mt-auto hidden sm:block"><p className="line-clamp-2 text-xs leading-relaxed text-dim">{item.bottom_line}</p></div>
        </div>
      </button>

      <div className="flex items-center gap-2 border-t border-[#eceee5] px-4 py-2.5">
        <CompareToggle selected={selected} onClick={() => onToggleSelect(item.id)} className="flex-1" />
        <button
          type="button"
          onClick={() => onOpen(item)}
          className="inline-flex min-h-9 flex-1 items-center justify-center gap-1 rounded-md text-[13px] font-semibold text-forest hover:bg-[#edf0e5]"
        >
          优缺点与口碑
          <Icon name="arrow" className="!h-4 !w-4" />
        </button>
      </div>
    </article>
  );
}
