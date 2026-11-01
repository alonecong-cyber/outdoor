"use client";

import Link from "next/link";
import { useState } from "react";
import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";

const TIER_COLORS: Record<string, { bg: string; text: string; border: string }> = {
  budget: { bg: "#e8eee2", text: "#2e5631", border: "#cbd8bf" },
  mid: { bg: "#e6eef5", text: "#2b4c68", border: "#bed0e2" },
  flagship: { bg: "#f7eee3", text: "#7e4a1a", border: "#e8cfb5" },
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

/** 国内口碑内容列表：什么值得买原创/好价、B站视频、小红书笔记。 */
export function CnReviewList({ item, limit = 6 }: { item: GearRankingItem; limit?: number }) {
  const rows = (item.cn_reviews ?? []).slice(0, limit);
  if (!rows.length) return null;
  return (
    <ul className="space-y-1">
      {rows.map((c) => (
        <li key={c.url} className="flex items-start gap-1.5">
          <span
            className="shrink-0 text-[9px] text-white px-1 rounded mt-0.5"
            style={{ background: PLATFORM_COLORS[c.platform] || "#4a5547" }}
          >
            {c.platform}·{c.kind}
          </span>
          <a
            href={c.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex-1 hover:underline line-clamp-2"
            title={c.summary || c.title}
          >
            {c.title}
          </a>
          <span className="shrink-0 font-mono text-[10px] text-[#687366]">
            {c.price_cny ? `¥${Math.round(c.price_cny)}` : c.metric_value ? `${c.metric_label}${fmtCount(c.metric_value)}` : ""}
            {c.date ? ` ${c.date.slice(2)}` : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function rankLabel(a: { rank?: number | null; rank_total?: number | null }) {
  return a.rank ? `#${a.rank}${a.rank_total ? `/${a.rank_total}` : ""}` : "";
}

export function RankingCard({
  item,
  selected,
  onToggleSelect,
}: {
  item: GearRankingItem;
  selected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const [showMore, setShowMore] = useState(false);
  const tier = TIER_COLORS[item.price_tier] || TIER_COLORS.budget;
  const subScores = Object.entries(item.sub_scores ?? {});
  const zh = item.sub_scores_zh ?? {};
  const isCnPick = item.id.startsWith("cn_");
  const pros = item.pros_zh?.length ? item.pros_zh : item.pros;
  const cons = item.cons_zh?.length ? item.cons_zh : item.cons;

  return (
    <article
      className={`card ranking-card relative flex flex-col transition-all duration-200 overflow-hidden ${
        selected ? "ring-2 ring-[#1d4434] shadow-md" : "hover:border-[#96a58a]"
      }`}
      style={{ background: "#fffefa" }}
    >
      <div className="relative w-full pt-[62%] bg-white border-b border-[#eceee5] overflow-hidden group">
        <GearImage
          item={item}
          className="absolute inset-0 w-full h-full object-contain p-2 transition-transform duration-300 group-hover:scale-105"
        />
        <div className="absolute top-2.5 left-2.5 flex flex-wrap gap-1.5 z-10">
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded"
            style={{ backgroundColor: tier.bg, color: tier.text, border: `1px solid ${tier.border}` }}
          >
            {item.price_tier_name}
          </span>
          {item.rating_score ? (
            <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#1d4434] text-white" title={item.score_basis}>
              ★ {item.rating_score} 分
            </span>
          ) : (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#2b4c68] text-white" title={item.score_basis}>
              {isCnPick ? "国内口碑" : "编辑推荐"}
            </span>
          )}
          {item.is_cn_brand && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-[#be482b] text-white">国货</span>
          )}
          {item.gender_name && (
            <span className="text-[10px] px-2 py-0.5 rounded bg-white/90 text-[#4a5547] border border-[#dce0d4]">
              {item.gender_name}
            </span>
          )}
        </div>
        <button
          type="button"
          onClick={() => onToggleSelect(item.id)}
          className={`absolute top-2.5 right-2.5 z-10 flex items-center gap-1.5 px-2 py-1 rounded text-xs font-semibold shadow-sm transition-all ${
            selected
              ? "bg-[#1d4434] text-white ring-2 ring-white"
              : "bg-white/95 text-[#213b2e] hover:bg-white border border-[#cdd4c5]"
          }`}
          aria-label={selected ? "取消加入对比" : "加入横向对比"}
        >
          <Icon name={selected ? "check" : "compare"} className="w-3.5 h-3.5" />
          <span>{selected ? "已选对比" : "加入对比"}</span>
        </button>
        {item.image_credit && (
          <span className="absolute bottom-1 right-1.5 text-[9px] text-white/90 bg-black/35 px-1 rounded">
            图：{item.image_credit}
          </span>
        )}
      </div>

      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          <div className="flex items-center justify-between gap-2 text-[11px] text-[#687366] font-mono mb-1">
            <span>
              {item.brand_name}
              {item.brand_country ? ` · ${item.brand_country}` : ""}
            </span>
            <span>{item.category_name}</span>
          </div>
          <h3 className="font-semibold text-base leading-snug text-[#213b2e] mb-0.5">{item.name_cn}</h3>
          <p className="text-xs text-[#687366] font-mono mb-3 line-clamp-1">{item.name}</p>

          <div className="flex flex-wrap gap-1.5 mb-3">
            {item.authorities.map((auth, idx) => (
              <a
                key={idx}
                href={auth.url || undefined}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1 text-[10px] bg-[#f0f3eb] text-[#335338] px-2 py-0.5 rounded border border-[#d6decb] font-medium hover:bg-[#e3eadb]"
                title={`${auth.badge}${auth.quote ? `\n${auth.quote_zh || auth.quote}` : ""}`}
              >
                <Icon name="award" className="w-3 h-3 text-[#1d4434]" />
                <strong>{shortSource(auth.source)}</strong>
                <span className="font-mono">{rankLabel(auth)}</span>
                <span className="line-clamp-1 max-w-[150px]">{auth.badge_zh || auth.badge}</span>
              </a>
            ))}
          </div>

          <div className="p-2.5 rounded bg-[#f5f4ee] border border-[#e4e7dd] mb-3">
            <div className="flex items-baseline justify-between mb-1">
              {item.price_guide.overseas_usd ? (
                <div>
                  <span className="text-[10px] text-[#687366] mr-1">美标价</span>
                  <span className="text-base font-bold text-[#be482b] font-mono">{item.price_guide.overseas_usd}</span>
                  <span className="text-[11px] text-[#687366] font-mono ml-1.5">{item.price_guide.deal_cny}</span>
                </div>
              ) : (
                <div>
                  <span className="text-[10px] text-[#687366] mr-1">国内好价</span>
                  <span className="text-base font-bold text-[#be482b] font-mono">{cnPriceLabel(item) || item.price_guide.deal_cny}</span>
                </div>
              )}
            </div>
            {item.cn_price && item.price_guide.overseas_usd && (
              <div
                className="text-[11px] text-[#9a3b22] flex items-center justify-between font-mono pt-1 border-t border-[#e3e7da]"
                title={`什么值得买近期 ${item.cn_price.count} 条好价（剔除离群价），检索词「${item.cn_query}」`}
              >
                <span>国内好价（值得买 {item.cn_price.count} 条）</span>
                <span className="font-semibold">{cnPriceLabel(item)}</span>
              </div>
            )}
            {item.cn_price && !item.price_guide.overseas_usd && (
              <div className="text-[10px] text-[#687366] pt-1 border-t border-[#e3e7da]">
                什么值得买 {item.cn_price.count} 条好价 · {(item.cn_price.malls ?? []).join("、")}
              </div>
            )}
            {item.price_guide.overseas_landed_cny && (
              <div
                className="text-[11px] text-[#456d80] flex items-center justify-between font-mono pt-1 border-t border-[#e3e7da]"
                title={item.price_guide.promo_tips}
              >
                <span>海淘落地估算（含转运+税）</span>
                <span className="font-semibold">{item.price_guide.overseas_landed_cny}</span>
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-2 text-[11px] text-[#4a5547] bg-[#fafaf6] p-2 rounded border border-[#e8ebe0] mb-3 font-mono">
            <div className="truncate">
              <span className="text-[#889280]">重量：</span>
              <span className="font-semibold">{item.specs.weight || "—"}</span>
            </div>
            <div className="truncate" title={item.specs.material}>
              <span className="text-[#889280]">材质：</span>
              <span className="font-semibold">{item.specs.material || "—"}</span>
            </div>
          </div>

          {subScores.length > 0 && (
            <div className="space-y-1 mb-3">
              {subScores.slice(0, 5).map(([k, v]) => (
                <div key={k} className="flex items-center gap-2 text-[10px] text-[#4a5547]">
                  <span className="w-32 truncate" title={k}>{zh[k] || k}</span>
                  <span className="flex-1 h-1.5 bg-[#eceee5] rounded">
                    <span className="block h-1.5 rounded bg-[#1d4434]" style={{ width: `${v * 10}%` }} />
                  </span>
                  <span className="font-mono w-6 text-right">{v.toFixed(1)}</span>
                </div>
              ))}
            </div>
          )}

          <p className="text-xs text-[#36493b] leading-relaxed mb-3 bg-[#edf1e8] p-2 rounded border-l-2 border-[#1d4434]">
            {item.bottom_line}
          </p>
        </div>

        <div>
          <button
            type="button"
            onClick={() => setShowMore(!showMore)}
            className="w-full text-left text-xs font-semibold text-[#1d4434] py-1 flex items-center justify-between border-t border-[#eceee5] pt-2 mb-2"
          >
            <span>优缺点 · 差价分析 · 国内口碑</span>
            <span className="text-[10px] text-[#687366]">{showMore ? "收起 ▲" : "展开 ▼"}</span>
          </button>

          {showMore && (
            <div className="text-xs text-[#4b5847] leading-relaxed p-2.5 rounded bg-[#f3f6ee] border border-[#dce3d2] mb-3 space-y-2">
              <div>
                <p className="font-medium text-[#2e5631]">👍 优点{isCnPick ? "" : "（测评译文，悬停看原文）"}</p>
                <ul className="list-disc pl-4">
                  {pros.map((p, i) => (
                    <li key={`${p}-${i}`} title={item.pros[i]}>{p}</li>
                  ))}
                </ul>
              </div>
              <div>
                <p className="font-medium text-[#9a3b22]">👎 缺点{isCnPick ? "" : "（测评译文，悬停看原文）"}</p>
                <ul className="list-disc pl-4">
                  {cons.map((p, i) => (
                    <li key={`${p}-${i}`} title={item.cons[i]}>{p}</li>
                  ))}
                </ul>
              </div>
              {!isCnPick && item.authorities.some((a) => a.quote) && (
                <div>
                  <p className="font-medium text-[#1d4434]">📝 测评结论</p>
                  {item.authorities
                    .filter((a) => a.quote)
                    .map((a, i) => (
                      <p key={i} title={a.quote}>
                        <strong>{a.source}：</strong>“{a.quote_zh || a.quote}”
                      </p>
                    ))}
                </div>
              )}
              <div>
                <p className="font-medium text-[#1d4434]">💡 差价分析</p>
                <p>{item.gap_analysis}</p>
              </div>
              {(item.cn_reviews?.length ?? 0) > 0 && (
                <div>
                  <p className="font-medium text-[#1d4434]">🇨🇳 国内口碑（什么值得买 / B站 / 小红书）</p>
                  <CnReviewList item={item} />
                </div>
              )}
              {item.cn_links && item.cn_links.length > 0 && (
                <div>
                  <p className="font-medium text-[#1d4434]">🇨🇳 国内口碑 / 购买</p>
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {item.cn_links.map((l) => (
                      <a
                        key={l.label}
                        href={l.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="px-2 py-0.5 rounded bg-white border border-[#dce0d4] hover:bg-[#f2f4ec]"
                      >
                        {l.label}
                      </a>
                    ))}
                  </div>
                </div>
              )}
              {item.buy_links && item.buy_links.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {item.buy_links.map((l, i) => (
                    <a
                      key={`${l.label}-${i}`}
                      href={l.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-2 py-0.5 rounded bg-white border border-[#dce0d4] hover:bg-[#f2f4ec] text-[#2b4c68]"
                    >
                      {l.label}
                    </a>
                  ))}
                </div>
              )}
            </div>
          )}

          <div className="flex gap-2 pt-1 border-t border-[#eceee5]">
            <Link
              href={`/variants?q=${encodeURIComponent(item.name)}`}
              className="flex-1 btn-ghost text-xs py-1.5 rounded text-center font-medium"
            >
              查系统到手价
            </Link>
            <Link href={`/watch`} className="flex-1 btn-ghost text-xs py-1.5 rounded text-center font-medium">
              加入降价监控
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}
