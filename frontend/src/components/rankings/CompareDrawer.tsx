"use client";

import type { GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { GearImage } from "@/components/rankings/RankingCard";

/** 底部对比托盘：移动端停在底部导航之上，最多 4 款。 */
export function CompareDrawer({
  selectedItems,
  onRemove,
  onClear,
  onCompare,
  loading = false,
}: {
  selectedItems: GearRankingItem[];
  onRemove: (id: string) => void;
  onClear: () => void;
  onCompare: () => void;
  loading?: boolean;
}) {
  if (selectedItems.length === 0) return null;
  const ready = selectedItems.length >= 2;
  return (
    <aside className="compare-tray" aria-label="对比托盘">
      <div className="mx-auto flex max-w-6xl items-center gap-3">
        <div className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto py-0.5">
          {selectedItems.map((item) => (
            <div key={item.id} className="relative flex shrink-0 items-center gap-2 rounded-md border border-line bg-bg py-1 pl-1 pr-7">
              <GearImage item={item} className="h-9 w-9 rounded bg-white object-contain" />
              <span className="hidden max-w-[120px] truncate text-xs font-medium text-ink sm:block">{item.name_cn}</span>
              <button
                type="button"
                onClick={() => onRemove(item.id)}
                className="absolute right-0.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center rounded text-dim hover:text-accent"
                aria-label={`移除 ${item.name_cn}`}
              >
                <Icon name="close" className="!h-3.5 !w-3.5" />
              </button>
            </div>
          ))}
          {Array.from({ length: Math.max(0, 2 - selectedItems.length) }).map((_, i) => (
            <span key={i} className="grid h-11 w-11 shrink-0 place-items-center rounded-md border border-dashed border-[#c9d0bf] text-[11px] text-dim">+1</span>
          ))}
        </div>
        <button type="button" onClick={onClear} className="hidden min-h-10 shrink-0 rounded-md px-3 text-[13px] text-dim hover:text-ink sm:block">
          清空
        </button>
        <button
          type="button"
          onClick={onCompare}
          disabled={!ready || loading}
          className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md bg-forest px-4 text-[13px] font-semibold text-white hover:bg-forest-2"
        >
          <Icon name="compare" className="!h-4 !w-4" />
          {loading ? "加载中…" : ready ? `开始对比 ${selectedItems.length}/4` : "再选 1 款"}
        </button>
      </div>
    </aside>
  );
}
