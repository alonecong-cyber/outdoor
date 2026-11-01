"use client";

import Link from "next/link";
import { useState } from "react";
import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";

export function RankingCard({
  item,
  selected,
  onToggleSelect,
}: {
  item: GearRankingItem;
  selected: boolean;
  onToggleSelect: (id: string) => void;
}) {
  const [showAnalysis, setShowAnalysis] = useState(false);

  const tierColors: Record<string, { bg: string; text: string; border: string }> = {
    budget: { bg: "#e8eee2", text: "#2e5631", border: "#cbd8bf" },
    mid: { bg: "#e6eef5", text: "#2b4c68", border: "#bed0e2" },
    flagship: { bg: "#f7eee3", text: "#7e4a1a", border: "#e8cfb5" },
  };

  const currentTier = tierColors[item.price_tier] || tierColors.budget;

  return (
    <article
      className={`card ranking-card relative flex flex-col transition-all duration-200 overflow-hidden ${
        selected ? "ring-2 ring-[#1d4434] shadow-md" : "hover:border-[#96a58a]"
      }`}
      style={{ background: "#fffefa" }}
    >
      {/* 顶部图片区域 */}
      <div className="relative w-full pt-[68%] bg-white border-b border-[#eceee5] overflow-hidden group">
        <img
          src={item.image}
          alt={item.name_cn}
          className="absolute inset-0 w-full h-full object-contain p-4 transition-transform duration-300 group-hover:scale-105"
          loading="lazy"
          onError={(e) => {
            // 图片加载异常时安全降级
            (e.target as HTMLImageElement).src =
              "https://www.rei.com/media/50cb5e27-0447-4887-a8c1-e270ea93daac.jpg?size=784x588";
          }}
        />

        {/* 顶部标签栏 */}
        <div className="absolute top-2.5 left-2.5 flex flex-wrap gap-1.5 z-10">
          <span
            className="text-[10px] font-semibold px-2 py-0.5 rounded"
            style={{
              backgroundColor: currentTier.bg,
              color: currentTier.text,
              border: `1px solid ${currentTier.border}`,
            }}
          >
            {item.price_tier_name}
          </span>
          <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded bg-[#1d4434] text-white">
            ★ {item.rating_score}分
          </span>
        </div>

        {/* 对比选择按钮 */}
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
      </div>

      {/* 主体信息 */}
      <div className="p-4 flex-1 flex flex-col justify-between">
        <div>
          {/* 品类与权威背书 */}
          <div className="flex items-center justify-between gap-2 text-[11px] text-[#687366] font-mono mb-1">
            <span>{item.brand_name}</span>
            <span>{item.category_name}</span>
          </div>

          {/* 标题 */}
          <h3 className="font-semibold text-base leading-snug text-[#213b2e] mb-1">
            {item.name_cn}
          </h3>
          <p className="text-xs text-[#687366] font-mono mb-3 line-clamp-1">
            {item.name}
          </p>

          {/* 权威榜单奖项徽章 */}
          <div className="flex flex-wrap gap-1.5 mb-3">
            {item.authorities.map((auth, idx) => (
              <span
                key={idx}
                className="inline-flex items-center gap-1 text-[10px] bg-[#f0f3eb] text-[#335338] px-2 py-0.5 rounded border border-[#d6decb] font-medium"
                title={auth.quote}
              >
                <Icon name="award" className="w-3 h-3 text-[#1d4434]" />
                <strong>{auth.source}</strong> {auth.badge}
              </span>
            ))}
          </div>

          {/* 价格板块 (国内券后 vs 海淘折算) */}
          <div className="p-2.5 rounded bg-[#f5f4ee] border border-[#e4e7dd] mb-3">
            <div className="flex items-baseline justify-between mb-1">
              <div>
                <span className="text-[10px] text-[#687366] mr-1">建议券后到手:</span>
                <span className="text-base font-bold text-[#be482b] font-mono">
                  {item.price_guide.deal_cny}
                </span>
              </div>
              <span className="text-[11px] text-[#899181] line-through font-mono">
                专柜 {item.price_guide.msrp_cny}
              </span>
            </div>

            {item.price_guide.overseas_landed_cny && (
              <div className="text-[11px] text-[#456d80] flex items-center justify-between font-mono pt-1 border-t border-[#e3e7da]">
                <span>海淘预估落地:</span>
                <span className="font-semibold">{item.price_guide.overseas_landed_cny}</span>
              </div>
            )}
          </div>

          {/* 核心规格属性 */}
          <div className="grid grid-cols-2 gap-2 text-[11px] text-[#4a5547] bg-[#fafaf6] p-2 rounded border border-[#e8ebe0] mb-3 font-mono">
            <div>
              <span className="text-[#889280]">重量：</span>
              <span className="font-semibold">{item.specs.weight || "轻量设计"}</span>
            </div>
            <div>
              <span className="text-[#889280]">面料：</span>
              <span className="font-semibold truncate" title={item.specs.material}>
                {item.specs.material.split("(")[0]}
              </span>
            </div>
            <div className="col-span-2">
              <span className="text-[#889280]">防护/透湿：</span>
              <span className="font-semibold">{item.specs.waterproof_rating}</span>
            </div>
          </div>

          {/* 权威一句话结论 */}
          <p className="text-xs text-[#36493b] leading-relaxed mb-3 italic bg-[#edf1e8] p-2 rounded border-l-2 border-[#1d4434]">
            “{item.bottom_line}”
          </p>
        </div>

        {/* 底部操作与差价分析折叠 */}
        <div>
          {/* 展开深度差价买到了什么 */}
          <button
            type="button"
            onClick={() => setShowAnalysis(!showAnalysis)}
            className="w-full text-left text-xs font-semibold text-[#1d4434] py-1 flex items-center justify-between border-t border-[#eceee5] pt-2 mb-2"
          >
            <span>💡 差价买到了什么？(深度解析)</span>
            <span className="text-[10px] text-[#687366]">{showAnalysis ? "收起 ▲" : "展开 ▼"}</span>
          </button>

          {showAnalysis && (
            <div className="text-xs text-[#4b5847] leading-relaxed p-2.5 rounded bg-[#f3f6ee] border border-[#dce3d2] mb-3">
              <p className="font-medium text-[#1d4434] mb-1">【选购取舍建议】：</p>
              <p>{item.gap_analysis}</p>
            </div>
          )}

          {/* 快捷跳转与系统比价联动 */}
          <div className="flex gap-2 pt-1 border-t border-[#eceee5]">
            <Link
              href={`/variants?q=${encodeURIComponent(item.name_cn.split(" ")[1] || item.name.split(" ")[0])}`}
              className="flex-1 btn-ghost text-xs py-1.5 rounded text-center font-medium"
            >
              查系统到手价
            </Link>
            <Link
              href={`/watch`}
              className="flex-1 btn-ghost text-xs py-1.5 rounded text-center font-medium"
            >
              加入降价监控
            </Link>
          </div>
        </div>
      </div>
    </article>
  );
}
