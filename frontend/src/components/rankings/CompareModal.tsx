"use client";

import { useState, type ReactNode } from "react";
import type { CompareMatrixResponse, GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { CnReviewList, GearImage, cnPriceLabel, rankLabel } from "@/components/rankings/RankingCard";
import { useOverlay } from "@/components/rankings/RankingDetail";

type Row = { label: string; render: (it: GearRankingItem) => ReactNode; best?: (it: GearRankingItem) => number | null; higherIsBetter?: boolean; text?: (it: GearRankingItem) => string };

/** 横向对比表：行=维度，列=产品；数值维度自动高亮最优。 */
export function CompareModal({ matrix, onClose, onRemove }: { matrix: CompareMatrixResponse | null; onClose: () => void; onRemove?: (id: string) => void }) {
  const [diffOnly, setDiffOnly] = useState(false);
  useOverlay(true, onClose);

  if (!matrix || matrix.items.length === 0) return null;
  const { items, gap_summary, category_name } = matrix;

  const subKeys = Array.from(new Set(items.flatMap((it) => Object.keys(it.sub_scores ?? {}))));
  const subName = (k: string) => items.find((it) => it.sub_scores_zh?.[k])?.sub_scores_zh?.[k] || k;
  const specKeys = Array.from(new Set(items.flatMap((it) => Object.keys(it.spec_table ?? {}))));

  const rows: Row[] = [
    { label: "品牌 / 产地", text: (it) => `${it.brand_name}${it.brand_country}`, render: (it) => `${it.brand_name}${it.brand_country ? ` · ${it.brand_country}` : ""}` },
    { label: "款式", text: (it) => `${it.gender_name}${it.price_tier_name}`, render: (it) => `${it.gender_name ?? ""} · ${it.price_tier_name}` },
    {
      label: "美标价",
      render: (it) =>
        it.price_guide.overseas_usd ? (
          <span className="font-mono">
            {it.price_guide.overseas_usd} <span className="text-[#687366]">{it.price_guide.deal_cny}</span>
          </span>
        ) : (
          <span className="text-[#889280]">国内款</span>
        ),
    },
    {
      label: "国内好价（什么值得买）",
      render: (it) =>
        it.cn_price ? (
          <span className="font-mono font-semibold text-[#9a3b22]" title={(it.cn_price.malls ?? []).join("、")}>
            {cnPriceLabel(it)} <span className="font-normal text-[#687366]">· {it.cn_price.count} 条</span>
          </span>
        ) : (
          <span className="text-[#889280]">暂无</span>
        ),
      best: (it) => it.cn_price?.min_cny ?? null,
      higherIsBetter: false,
    },
    {
      label: "海淘落地估算",
      render: (it) => <span className="font-mono font-semibold">{it.price_guide.overseas_landed_cny || "—"}</span>,
      best: (it) => it.price_guide.price_cents,
      higherIsBetter: false,
    },
    {
      label: "OGL 实测总分",
      render: (it) => (it.rating_score ? <span className="font-mono font-bold">{it.rating_score}</span> : <span className="text-[#889280]">无打分</span>),
      best: (it) => it.rating_score ?? null,
      higherIsBetter: true,
    },
    {
      label: "每千元得分",
      render: (it) => (it.rating_score ? <span className="font-mono">{((it.rating_score / it.price_guide.price_cents) * 100000).toFixed(1)}</span> : "—"),
      best: (it) => (it.rating_score ? it.rating_score / it.price_guide.price_cents : null),
      higherIsBetter: true,
    },
    {
      label: "权威榜单",
      render: (it) => (
        <ul className="space-y-1">
          {it.authorities.map((a, i) => (
            <li key={i}>
              <a href={a.url} target="_blank" rel="noopener noreferrer" className="hover:underline">
                <strong>{a.source}</strong> <span className="font-mono">{rankLabel(a)}</span> {a.badge_zh || a.badge}
              </a>
            </li>
          ))}
        </ul>
      ),
    },
    ...subKeys.map<Row>((k) => ({
      label: `分项：${subName(k)}`,
      render: (it) => {
        const v = it.sub_scores?.[k];
        return v == null ? "—" : (
          <span className="flex items-center gap-2">
            <span className="flex-1 h-1.5 bg-[#eceee5] rounded">
              <span className="block h-1.5 rounded bg-[#1d4434]" style={{ width: `${v * 10}%` }} />
            </span>
            <span className="font-mono">{v.toFixed(1)}</span>
          </span>
        );
      },
      best: (it) => it.sub_scores?.[k] ?? null,
      higherIsBetter: true,
      text: (it) => String(it.sub_scores?.[k] ?? "—"),
    })),
    { label: "重量", text: (it) => it.specs.weight || "—", render: (it) => it.specs.weight || "—" },
    ...specKeys.map<Row>((k) => ({ label: k, text: (it) => it.spec_table?.[k] ?? "—", render: (it) => it.spec_table?.[k] ?? "—" })),
    {
      label: "优点",
      render: (it) => (
        <ul className="list-disc pl-4">
          {(it.pros_zh?.length ? it.pros_zh : it.pros).map((p, i) => (
            <li key={`${p}-${i}`} title={it.pros[i]}>{p}</li>
          ))}
        </ul>
      ),
    },
    {
      label: "缺点",
      render: (it) => (
        <ul className="list-disc pl-4">
          {(it.cons_zh?.length ? it.cons_zh : it.cons).map((p, i) => (
            <li key={`${p}-${i}`} title={it.cons[i]}>{p}</li>
          ))}
        </ul>
      ),
    },
    { label: "差价分析", render: (it) => it.gap_analysis },
    {
      label: "国内口碑",
      render: (it) => (
        <div className="space-y-1.5">
          <CnReviewList item={it} limit={4} />
        <span className="flex flex-wrap gap-1">
          {(it.cn_links ?? []).map((l) => (
            <a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer" className="px-1.5 py-0.5 rounded border border-[#dce0d4] bg-white hover:bg-[#f2f4ec]">
              {l.label}
            </a>
          ))}
        </span>
        </div>
      ),
    },
  ];

  const bestIds = (row: Row): Set<string> => {
    if (!row.best) return new Set();
    const vals = items.map((it) => [it.id, row.best!(it)] as const).filter(([, v]) => v != null) as [string, number][];
    if (vals.length < 2) return new Set();
    const target = row.higherIsBetter ? Math.max(...vals.map(([, v]) => v)) : Math.min(...vals.map(([, v]) => v));
    return new Set(vals.filter(([, v]) => v === target).map(([id]) => id));
  };

  const visibleRows = diffOnly ? rows.filter((r) => !r.text || new Set(items.map((it) => r.text!(it))).size > 1) : rows;

  return (
    <div className="fixed inset-0 z-[60] flex items-stretch justify-center bg-[#10201899] backdrop-blur-sm sm:items-center sm:p-6" role="dialog" aria-modal="true" aria-labelledby="compare-modal-title">
      <div className="flex w-full max-w-7xl flex-col overflow-hidden bg-panel shadow-2xl sm:max-h-[92vh] sm:rounded-xl sm:border sm:border-line">
        <div className="flex items-center gap-3 border-b border-line bg-[#f8f7f2] px-4 py-3 sm:px-6">
          <div className="min-w-0 flex-1">
            <h2 id="compare-modal-title" className="truncate text-base font-semibold text-ink sm:text-lg">横向对比 · {category_name}</h2>
            <p className="text-xs text-dim">{items.length} 款 · 绿色为该维度最优</p>
          </div>
          <label className="flex shrink-0 cursor-pointer items-center gap-2 text-[13px] text-ink">
            <input type="checkbox" checked={diffOnly} onChange={(e) => setDiffOnly(e.target.checked)} className="h-4 w-4 accent-[#1d4434]" />
            只看差异
          </label>
          <button type="button" onClick={onClose} className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-dim hover:bg-panel-2 hover:text-ink" aria-label="关闭对比">
            <Icon name="close" />
          </button>
        </div>

        {gap_summary && (
          <div className="border-b border-[#d8e0ce] bg-[#f0f4ea] px-4 py-2.5 text-[13px] leading-relaxed text-[#2c4731] sm:px-6">
            <strong className="font-semibold">对比结论：</strong>
            {gap_summary}
          </div>
        )}

        <div className="flex-1 overflow-auto overscroll-contain">
          <table className="w-full border-separate border-spacing-0 text-[13px] text-[#36493b]" style={{ minWidth: 112 + items.length * 190 }}>
            <thead className="sticky top-0 z-20 bg-panel">
              <tr>
                <th className="sticky left-0 z-10 w-28 border-b border-r border-line bg-panel p-2 text-left text-xs font-normal text-dim sm:w-40 sm:p-3">维度</th>
                {items.map((it) => (
                  <th key={it.id} className="border-b border-line p-2 text-left align-top font-normal sm:p-3">
                    <div className="relative mb-2 aspect-[16/10] w-full overflow-hidden rounded bg-white">
                      <GearImage item={it} className="absolute inset-0 h-full w-full object-contain p-1" />
                      {onRemove && (
                        <button type="button" onClick={() => onRemove(it.id)} className="absolute right-1 top-1 grid h-8 w-8 place-items-center rounded-full bg-white/90 text-dim shadow hover:text-accent" aria-label={`从对比中移除 ${it.name_cn}`}>
                          <Icon name="close" className="!h-4 !w-4" />
                        </button>
                      )}
                    </div>
                    <div className="line-clamp-2 text-[13px] font-semibold leading-snug text-ink">{it.name_cn}</div>
                    <div className="truncate font-mono text-[11px] text-dim">{it.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row) => {
                const best = bestIds(row);
                return (
                  <tr key={row.label} className="align-top">
                    <th className="sticky left-0 z-10 border-b border-r border-line bg-[#fafaf6] p-2 text-left text-xs font-medium text-dim sm:p-3">{row.label}</th>
                    {items.map((it) => (
                      <td key={it.id} className={`border-b border-[#f0f1ea] p-2 sm:p-3 ${best.has(it.id) ? "bg-[#e3eedb] font-semibold" : ""}`}>
                        {row.render(it)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
