"use client";

import Link from "next/link";
import { useEffect } from "react";
import type { CompareMatrixResponse, GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";

export function CompareModal({
  matrix,
  onClose,
}: {
  matrix: CompareMatrixResponse | null;
  onClose: () => void;
}) {
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!matrix || matrix.items.length === 0) return null;

  const { items, gap_summary, category_name } = matrix;

  const tierColors: Record<string, { bg: string; text: string; border: string }> = {
    budget: { bg: "#e8eee2", text: "#2e5631", border: "#cbd8bf" },
    mid: { bg: "#e6eef5", text: "#2b4c68", border: "#bed0e2" },
    flagship: { bg: "#f7eee3", text: "#7e4a1a", border: "#e8cfb5" },
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/60 backdrop-blur-sm animate-in fade-in"
      role="dialog"
      aria-modal="true"
      aria-labelledby="compare-modal-title"
    >
      <div className="bg-[#fffefa] w-full max-w-7xl max-h-[92vh] rounded-xl shadow-2xl flex flex-col border border-[#dce0d4] overflow-hidden">
        {/* 顶部标题栏 */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#eceee5] bg-[#f8f7f2]">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-1.5 rounded-full bg-[#1d4434] text-white">
                <Icon name="compare" className="w-4 h-4" />
              </span>
              <h2 id="compare-modal-title" className="text-lg font-bold text-[#213b2e]">
                装备多维横向横评对比 · {category_name}
              </h2>
            </div>
            <p className="text-xs text-[#687366] font-mono mt-0.5">
              已选 {items.length} 款装备同屏 PK（支持价格、面料、防护、权威测评与差价解析）
            </p>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="p-2 text-[#687366] hover:text-[#213b2e] hover:bg-[#eaece2] rounded-full transition-colors"
            aria-label="关闭对比弹窗"
          >
            <Icon name="close" className="w-5 h-5" />
          </button>
        </div>

        {/* 跨价位差价核心分析 Callout */}
        {gap_summary && (
          <div className="px-6 py-3 bg-[#f0f4ea] border-b border-[#d8e0ce] text-xs text-[#2c4731] leading-relaxed flex items-start gap-2.5">
            <span className="text-base leading-none">💡</span>
            <div>
              <strong className="font-semibold block mb-0.5">【跨价位差价核心总结与选购建议】：</strong>
              <span>{gap_summary}</span>
            </div>
          </div>
        )}

        {/* 对比主体表格内容（横向滚动） */}
        <div className="flex-1 overflow-auto p-4 sm:p-6">
          <div
            className="grid gap-4 min-w-[720px]"
            style={{
              gridTemplateColumns: `repeat(${items.length}, minmax(240px, 1fr))`,
            }}
          >
            {items.map((item) => {
              const currentTier = tierColors[item.price_tier] || tierColors.budget;

              return (
                <div
                  key={item.id}
                  className="card p-4 flex flex-col justify-between border border-[#dce0d4] bg-white rounded-lg shadow-sm"
                >
                  <div>
                    {/* 产品图片 */}
                    <div className="w-full h-44 bg-[#fafaf6] rounded-md mb-3 flex items-center justify-center p-2 border border-[#eceee5] overflow-hidden">
                      <img
                        src={item.image}
                        alt={item.name_cn}
                        className="max-h-full max-w-full object-contain"
                      />
                    </div>

                    {/* 梯队与评分 */}
                    <div className="flex items-center justify-between mb-2">
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
                      <span className="text-xs font-mono font-bold text-[#1d4434]">
                        ★ {item.rating_score}分
                      </span>
                    </div>

                    {/* 标题 */}
                    <h3 className="font-bold text-base text-[#213b2e] leading-snug mb-0.5">
                      {item.name_cn}
                    </h3>
                    <p className="text-[11px] text-[#687366] font-mono mb-3">
                      {item.brand_name} · {item.name}
                    </p>

                    {/* 价格板块 */}
                    <div className="p-3 bg-[#f5f4ee] rounded border border-[#e2e6d9] mb-4">
                      <div className="flex items-baseline justify-between mb-1">
                        <span className="text-[11px] text-[#687366]">券后到手价:</span>
                        <span className="text-lg font-bold text-[#be482b] font-mono">
                          {item.price_guide.deal_cny}
                        </span>
                      </div>
                      <div className="flex items-center justify-between text-[11px] text-[#889280] font-mono">
                        <span>专柜原价:</span>
                        <span className="line-through">{item.price_guide.msrp_cny}</span>
                      </div>
                      {item.price_guide.overseas_landed_cny && (
                        <div className="flex items-center justify-between text-[11px] text-[#456d80] font-mono pt-1 mt-1 border-t border-[#e2e6d9]">
                          <span>海淘预估落地:</span>
                          <span className="font-semibold">{item.price_guide.overseas_landed_cny}</span>
                        </div>
                      )}
                    </div>

                    {/* 权威榜单奖项 */}
                    <div className="mb-4">
                      <h4 className="text-[11px] font-bold text-[#687366] uppercase tracking-wider mb-1 font-mono">
                        权威机构背书
                      </h4>
                      <div className="flex flex-col gap-1">
                        {item.authorities.map((auth, aIdx) => (
                          <div
                            key={aIdx}
                            className="text-xs p-1.5 rounded bg-[#f0f4ea] border border-[#d6decb] text-[#2c4731]"
                          >
                            <span className="font-bold">{auth.source}</span>: {auth.badge}
                            <p className="text-[11px] text-[#4a634e] italic mt-0.5">
                              “{auth.quote}”
                            </p>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* 核心面料与技术规格 */}
                    <div className="mb-4 text-xs space-y-1.5 font-mono">
                      <h4 className="text-[11px] font-bold text-[#687366] uppercase tracking-wider font-mono">
                        核心规格参数
                      </h4>
                      <div className="p-2 bg-[#f9faf7] rounded border border-[#e8ebe0] space-y-1">
                        <div>
                          <span className="text-[#899181]">重量: </span>
                          <strong className="text-[#213b2e]">{item.specs.weight}</strong>
                        </div>
                        <div>
                          <span className="text-[#899181]">材质: </span>
                          <span className="text-[#213b2e]">{item.specs.material}</span>
                        </div>
                        <div>
                          <span className="text-[#899181]">防护: </span>
                          <span className="text-[#213b2e]">{item.specs.waterproof_rating}</span>
                        </div>
                        <div>
                          <span className="text-[#899181]">透湿: </span>
                          <span className="text-[#213b2e]">{item.specs.breathability}</span>
                        </div>
                      </div>
                    </div>

                    {/* 适用场景 */}
                    <div className="mb-4">
                      <h4 className="text-[11px] font-bold text-[#687366] uppercase tracking-wider mb-1 font-mono">
                        适用场景
                      </h4>
                      <div className="flex flex-wrap gap-1">
                        {item.specs.scenarios.map((sc, sIdx) => (
                          <span
                            key={sIdx}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-[#eceee5] text-[#43523f]"
                          >
                            {sc}
                          </span>
                        ))}
                      </div>
                    </div>

                    {/* 实测优缺点 */}
                    <div className="grid grid-cols-1 gap-2 mb-4 text-xs">
                      <div className="p-2 bg-[#f0f7ed] rounded border border-[#cfe1cc]">
                        <strong className="text-[#2e6833] block mb-1">实测优点 (Pros):</strong>
                        <ul className="list-disc list-inside text-[#335338] space-y-0.5 text-[11px]">
                          {item.pros.map((p, pIdx) => (
                            <li key={pIdx}>{p}</li>
                          ))}
                        </ul>
                      </div>
                      <div className="p-2 bg-[#fbf3eb] rounded border border-[#e8d2c0]">
                        <strong className="text-[#8b451f] block mb-1">注意事项 (Cons):</strong>
                        <ul className="list-disc list-inside text-[#7d4829] space-y-0.5 text-[11px]">
                          {item.cons.map((c, cIdx) => (
                            <li key={cIdx}>{c}</li>
                          ))}
                        </ul>
                      </div>
                    </div>

                    {/* 差价买到了什么 */}
                    <div className="p-2.5 bg-[#f4f7ef] rounded border-l-2 border-[#1d4434] text-xs text-[#304734] leading-relaxed mb-4">
                      <strong className="block font-bold text-[#1d4434] mb-1">
                        差价买到了什么？
                      </strong>
                      <p className="text-[11px]">{item.gap_analysis}</p>
                    </div>
                  </div>

                  {/* 底部联动操作 */}
                  <div className="flex gap-2 pt-2 border-t border-[#eceee5]">
                    <Link
                      href={`/variants?q=${encodeURIComponent(item.name_cn.split(" ")[1] || item.name.split(" ")[0])}`}
                      className="flex-1 btn-primary text-xs py-2 text-center"
                    >
                      去查到手价
                    </Link>
                    <Link
                      href="/watch"
                      className="flex-1 btn-ghost text-xs py-2 text-center font-medium"
                    >
                      添加监控
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}
