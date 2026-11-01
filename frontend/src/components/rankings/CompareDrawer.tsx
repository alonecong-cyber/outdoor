"use client";

import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";

export function CompareDrawer({
  selectedItems,
  onRemove,
  onClear,
  onCompare,
}: {
  selectedItems: GearRankingItem[];
  onRemove: (id: string) => void;
  onClear: () => void;
  onCompare: () => void;
}) {
  if (selectedItems.length === 0) return null;

  return (
    <aside
      className="fixed bottom-0 left-0 right-0 z-40 bg-[#fffefa] border-t-2 border-[#1d4434] shadow-2xl p-3 sm:px-8 transition-transform animate-in slide-in-from-bottom"
      aria-label="装备对比抽屉"
    >
      <div className="max-w-6xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-3">
        {/* 左侧说明与缩略图 */}
        <div className="flex items-center gap-4 w-full sm:w-auto overflow-x-auto py-1">
          <div className="flex-shrink-0">
            <span className="text-xs font-bold text-[#1d4434] block">
              已选对比装备
            </span>
            <span className="text-[10px] text-[#687366] font-mono">
              ({selectedItems.length}/4 款，建议选同类)
            </span>
          </div>

          <div className="flex items-center gap-2">
            {selectedItems.map((item) => (
              <div
                key={item.id}
                className="relative flex items-center gap-1.5 p-1 pr-2 rounded bg-[#f5f4ee] border border-[#dce0d4] flex-shrink-0"
              >
                <img
                  src={item.image}
                  alt={item.name_cn}
                  className="w-8 h-8 object-contain rounded bg-white p-0.5"
                />
                <div className="text-left max-w-[100px] truncate">
                  <p className="text-[11px] font-semibold text-[#213b2e] truncate">
                    {item.name_cn}
                  </p>
                  <p className="text-[9px] text-[#be482b] font-mono font-bold truncate">
                    {item.price_guide.deal_cny}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => onRemove(item.id)}
                  className="text-[#889280] hover:text-[#be482b] p-0.5"
                  aria-label={`移除 ${item.name_cn}`}
                >
                  <Icon name="close" className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* 右侧动作按钮 */}
        <div className="flex items-center gap-2.5 w-full sm:w-auto justify-end flex-shrink-0">
          <button
            type="button"
            onClick={onClear}
            className="btn-ghost text-xs py-2 px-3 rounded text-[#687366] hover:text-[#213b2e]"
          >
            清空已选
          </button>

          <button
            type="button"
            onClick={onCompare}
            disabled={selectedItems.length < 2}
            className="btn-primary text-xs py-2 px-4 shadow-sm"
          >
            <Icon name="compare" className="w-4 h-4" />
            <span>
              {selectedItems.length < 2
                ? "请至少选择 2 款装备"
                : `开始横向同屏 PK (${selectedItems.length} 款)`}
            </span>
          </button>
        </div>
      </div>
    </aside>
  );
}
