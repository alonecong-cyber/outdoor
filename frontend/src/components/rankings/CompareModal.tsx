"use client";

import { useEffect, type ReactNode } from "react";
import type { CompareMatrixResponse, GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { GearImage, rankLabel } from "@/components/rankings/RankingCard";

type Row = { label: string; render: (it: GearRankingItem) => ReactNode; best?: (it: GearRankingItem) => number | null; higherIsBetter?: boolean };

/** 横向对比表：行=维度，列=产品；数值维度自动高亮最优。 */
export function CompareModal({ matrix, onClose }: { matrix: CompareMatrixResponse | null; onClose: () => void }) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!matrix || matrix.items.length === 0) return null;
  const { items, gap_summary, category_name } = matrix;

  const subKeys = Array.from(new Set(items.flatMap((it) => Object.keys(it.sub_scores ?? {}))));
  const specKeys = Array.from(new Set(items.flatMap((it) => Object.keys(it.spec_table ?? {}))));

  const rows: Row[] = [
    { label: "品牌 / 产地", render: (it) => `${it.brand_name}${it.brand_country ? ` · ${it.brand_country}` : ""}` },
    { label: "款式", render: (it) => `${it.gender_name ?? ""} · ${it.price_tier_name}` },
    {
      label: "美标价",
      render: (it) => (
        <span className="font-mono">
          {it.price_guide.overseas_usd} <span className="text-[#687366]">{it.price_guide.deal_cny}</span>
        </span>
      ),
    },
    {
      label: "海淘落地估算",
      render: (it) => <span className="font-mono font-semibold">{it.price_guide.overseas_landed_cny}</span>,
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
                <strong>{a.source}</strong> <span className="font-mono">{rankLabel(a)}</span> {a.badge}
              </a>
            </li>
          ))}
        </ul>
      ),
    },
    ...subKeys.map<Row>((k) => ({
      label: `分项：${k}`,
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
    })),
    { label: "重量", render: (it) => it.specs.weight || "—" },
    ...specKeys.map<Row>((k) => ({ label: k, render: (it) => it.spec_table?.[k] ?? "—" })),
    { label: "优点", render: (it) => <ul className="list-disc pl-4">{it.pros.map((p) => <li key={p}>{p}</li>)}</ul> },
    { label: "缺点", render: (it) => <ul className="list-disc pl-4">{it.cons.map((p) => <li key={p}>{p}</li>)}</ul> },
    { label: "差价分析", render: (it) => it.gap_analysis },
    {
      label: "国内口碑",
      render: (it) => (
        <span className="flex flex-wrap gap-1">
          {(it.cn_links ?? []).map((l) => (
            <a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer" className="px-1.5 py-0.5 rounded border border-[#dce0d4] bg-white hover:bg-[#f2f4ec]">
              {l.label}
            </a>
          ))}
        </span>
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="compare-modal-title">
      <div className="bg-[#fffefa] w-full max-w-7xl max-h-[92vh] rounded-xl shadow-2xl flex flex-col border border-[#dce0d4] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#eceee5] bg-[#f8f7f2]">
          <div>
            <h2 id="compare-modal-title" className="text-lg font-bold text-[#213b2e] flex items-center gap-2">
              <span className="p-1.5 rounded-full bg-[#1d4434] text-white">
                <Icon name="compare" className="w-4 h-4" />
              </span>
              横向对比 · {category_name}
            </h2>
            <p className="text-xs text-[#687366] font-mono mt-0.5">已选 {items.length} 款 · 绿色高亮为该维度最优</p>
          </div>
          <button type="button" onClick={onClose} className="p-2 text-[#687366] hover:text-[#213b2e] hover:bg-[#eaece2] rounded-full" aria-label="关闭对比弹窗">
            <Icon name="close" className="w-5 h-5" />
          </button>
        </div>

        {gap_summary && (
          <div className="px-6 py-3 bg-[#f0f4ea] border-b border-[#d8e0ce] text-xs text-[#2c4731] leading-relaxed">
            <strong className="font-semibold">💡 对比结论：</strong>
            {gap_summary}
          </div>
        )}

        <div className="flex-1 overflow-auto">
          <table className="w-full text-xs text-[#36493b] border-collapse" style={{ minWidth: 200 + items.length * 220 }}>
            <thead className="sticky top-0 z-10 bg-[#fffefa]">
              <tr>
                <th className="w-40 p-3 text-left text-[#687366] font-mono border-b border-[#eceee5]">维度</th>
                {items.map((it) => (
                  <th key={it.id} className="p-3 text-left align-top border-b border-[#eceee5]">
                    <div className="relative w-full pt-[60%] bg-white rounded overflow-hidden mb-2">
                      <GearImage item={it} className="absolute inset-0 w-full h-full object-contain" />
                    </div>
                    <div className="font-semibold text-sm text-[#213b2e] leading-snug">{it.name_cn}</div>
                    <div className="text-[11px] text-[#687366] font-mono font-normal">{it.name}</div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => {
                const best = bestIds(row);
                return (
                  <tr key={row.label} className="border-b border-[#f0f1ea] align-top">
                    <th className="p-3 text-left font-medium text-[#687366] bg-[#fafaf6]">{row.label}</th>
                    {items.map((it) => (
                      <td key={it.id} className={`p-3 ${best.has(it.id) ? "bg-[#e3eedb] font-semibold" : ""}`}>
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
