"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CompareMatrixResponse } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { SiteHeader } from "@/components/SiteHeader";
import { RankingCard } from "@/components/rankings/RankingCard";
import { CompareDrawer } from "@/components/rankings/CompareDrawer";
import { CompareModal } from "@/components/rankings/CompareModal";

export default function RankingsPage() {
  const [category, setCategory] = useState<string>("hardshell");
  const [tier, setTier] = useState<string>("all");
  const [source, setSource] = useState<string>("all");
  const [query, setQuery] = useState<string>("");
  const [sort, setSort] = useState<string>("score_desc");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [compareMatrix, setCompareMatrix] = useState<CompareMatrixResponse | null>(null);
  const [isComparing, setIsComparing] = useState<boolean>(false);

  // 获取品类元数据与数量
  const categoriesQuery = useQuery({
    queryKey: ["rankingCategories"],
    queryFn: () => api.rankingCategories(),
    staleTime: 60_000,
  });

  // 获取榜单装备列表
  const rankingsQuery = useQuery({
    queryKey: ["rankings", category, tier, source, query, sort],
    queryFn: () =>
      api.rankings({
        category: category === "all" ? undefined : category,
        tier: tier === "all" ? undefined : tier,
        source: source === "all" ? undefined : source,
        q: query.trim() || undefined,
        sort: sort || undefined,
      }),
    staleTime: 30_000,
  });

  const items = rankingsQuery.data ?? [];

  // 映射已选条目
  const selectedItems = useMemo(
    () => items.filter((it) => selectedIds.includes(it.id)),
    [items, selectedIds]
  );

  const toggleSelect = (id: string) => {
    setSelectedIds((prev) => {
      if (prev.includes(id)) {
        return prev.filter((i) => i !== id);
      }
      if (prev.length >= 4) {
        alert("最多同时选择 4 款装备进行横向对比");
        return prev;
      }
      return [...prev, id];
    });
  };

  const clearSelection = () => {
    setSelectedIds([]);
  };

  // 触发横向对比
  const handleStartCompare = async (idsToCompare?: string[]) => {
    const ids = idsToCompare || selectedIds;
    if (ids.length < 2) return;
    try {
      setIsComparing(true);
      const res = await api.rankingCompare(ids);
      setCompareMatrix(res);
    } catch (err) {
      console.error("Failed to load compare matrix", err);
      alert("对比数据加载失败，请重试");
      setIsComparing(false);
    }
  };

  // 跨价位一键对比（当前品类的入门 vs 进阶 vs 旗舰）
  const handleQuickTierCompare = () => {
    if (!items || items.length === 0) return;
    // 从当前品类中挑选 budget, mid, flagship 各 1 款
    const budgetItem = items.find((it) => it.price_tier === "budget");
    const midItem = items.find((it) => it.price_tier === "mid");
    const flagshipItem = items.find((it) => it.price_tier === "flagship");

    const picked = [budgetItem, midItem, flagshipItem].filter(Boolean).map((it) => it!.id);
    if (picked.length >= 2) {
      setSelectedIds(picked);
      void handleStartCompare(picked);
    }
  };

  const sourcesList = [
    { id: "all", name: "全部机构" },
    { id: "OutdoorGearLab", name: "OutdoorGearLab (美)" },
    { id: "Switchback", name: "Switchback Travel (美)" },
    { id: "CleverHiker", name: "CleverHiker (轻量)" },
    { id: "RunRepeat", name: "RunRepeat (鞋靴实验室)" },
    { id: "SMZDM", name: "什么值得买 (国内好价)" },
    { id: "8264", name: "8264 (国内驴友口碑)" },
  ];

  const priceTiers = [
    { id: "all", name: "全部价位段" },
    { id: "budget", name: "百元入门平替 (<¥1,000)" },
    { id: "mid", name: "千元进阶主力 (¥1,000~¥2,500)" },
    { id: "flagship", name: "顶级专业旗舰 (¥2,500+)" },
  ];

  return (
    <main className="pb-24">
      <SiteHeader kicker="BENCHMARKS" />

      {/* 头部 Hero */}
      <section className="feed-hero rise relative overflow-hidden mb-6">
        <svg
          className="hero-landscape"
          viewBox="0 0 680 260"
          fill="none"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <path d="m0 260 206-240 90 113 87-85 141 212H0Z" fill="#93ad7a" opacity=".13" />
          <path d="m125 260 215-240 68 98 82-63 190 205H125Z" fill="#b8c38c" opacity=".15" />
          <path
            d="M-20 216 110 155 173 184 339 20 405 119 489 56 700 256M-20 239 110 177 175 205 338 45 402 145 488 80 680 267"
            stroke="#dce7bc"
            strokeWidth=".7"
          />
        </svg>

        <div>
          <p className="eyebrow">GLOBAL BENCHMARKS & REVIEW MATRIX / 权威榜单与多维横评</p>
          <h1>
            装备买对不买贵，<br />
            <span>看懂差价买到了什么。</span>
          </h1>
          <p>
            整合国外公认四大机构（OutdoorGearLab / Switchback / CleverHiker / RunRepeat）与国内真实实测，
            <br className="hidden sm:inline" />
            各价位段完整阶梯覆盖，支持多款装备同屏参数与差价深度对比。
          </p>
        </div>

        <div className="hero-aside">
          <span className="field-note">
            ALL TIERS<br />IN DEPTH.
          </span>
          <p>百元入门 · 千元进阶 · 顶级旗舰</p>
          <button
            type="button"
            onClick={handleQuickTierCompare}
            className="btn-primary text-xs mt-3 flex items-center gap-1.5"
          >
            <Icon name="compare" className="w-3.5 h-3.5" />
            <span>跨价位一键 PK (入门 vs 旗舰)</span>
          </button>
        </div>
      </section>

      {/* 10 大核心品类导航横向 Tab */}
      <nav className="mb-6 overflow-x-auto pb-2 scrollbar-none" aria-label="装备品类分类">
        <div className="flex gap-2 min-w-max">
          <button
            type="button"
            onClick={() => setCategory("all")}
            className={`px-3.5 py-2 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
              category === "all"
                ? "bg-[#1d4434] text-white shadow-sm"
                : "bg-white text-[#213b2e] border border-[#dce0d4] hover:bg-[#f2f4ec]"
            }`}
          >
            <Icon name="grid" className="w-3.5 h-3.5" />
            <span>全品类汇总</span>
          </button>

          {(categoriesQuery.data ?? []).map((cat) => {
            const active = category === cat.id;
            return (
              <button
                key={cat.id}
                type="button"
                onClick={() => setCategory(cat.id)}
                className={`px-3.5 py-2 rounded-md text-xs font-semibold flex items-center gap-1.5 transition-all ${
                  active
                    ? "bg-[#1d4434] text-white shadow-sm"
                    : "bg-white text-[#213b2e] border border-[#dce0d4] hover:bg-[#f2f4ec]"
                }`}
              >
                <span>{cat.name}</span>
                <span
                  className={`text-[10px] font-mono px-1.5 py-0.2 rounded-full ${
                    active ? "bg-white/20 text-white" : "bg-[#eceee5] text-[#687366]"
                  }`}
                >
                  {cat.total_count}
                </span>
              </button>
            );
          })}
        </div>
      </nav>

      {/* 筛选与检索控制区 */}
      <section className="card p-4 sm:p-5 mb-6 border border-[#dce0d4] bg-[#fffefa] space-y-4">
        {/* 价位段梯队快速切片 */}
        <div>
          <span className="text-[11px] font-bold text-[#687366] uppercase tracking-wider block mb-2 font-mono">
            价格梯队筛选 (PRICE TIER)
          </span>
          <div className="flex flex-wrap gap-2">
            {priceTiers.map((pTier) => {
              const active = tier === pTier.id;
              return (
                <button
                  key={pTier.id}
                  type="button"
                  onClick={() => setTier(pTier.id)}
                  className={`px-3 py-1.5 rounded text-xs font-medium transition-all ${
                    active
                      ? "bg-[#1d4434] text-white font-semibold"
                      : "bg-[#f5f4ee] text-[#4a5547] hover:bg-[#eaece2] border border-[#dce0d4]"
                  }`}
                >
                  {pTier.name}
                </button>
              );
            })}
          </div>
        </div>

        {/* 权威机构与检索/排序控制栏 */}
        <div className="pt-3 border-t border-[#eceee5] flex flex-col md:flex-row items-stretch md:items-center justify-between gap-3">
          {/* 权威测评来源 */}
          <div className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0">
            <span className="text-[11px] font-bold text-[#687366] font-mono flex-shrink-0">
              评测源:
            </span>
            {sourcesList.map((src) => {
              const active = source === src.id;
              return (
                <button
                  key={src.id}
                  type="button"
                  onClick={() => setSource(src.id)}
                  className={`px-2.5 py-1 rounded text-xs whitespace-nowrap transition-all ${
                    active
                      ? "bg-[#2b4c68] text-white font-semibold"
                      : "bg-[#f5f4ee] text-[#556251] hover:bg-[#eaece2] border border-[#dce0d4]"
                  }`}
                >
                  {src.name}
                </button>
              );
            })}
          </div>

          {/* 搜索与排序 */}
          <div className="flex items-center gap-2.5 flex-shrink-0">
            <div className="relative flex-1 sm:w-56">
              <input
                type="text"
                placeholder="搜索装备名、面料、场景..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="field text-xs pl-8 pr-3 py-1.5 min-h-[36px]"
              />
              <span className="absolute left-2.5 top-2.5 text-[#889280]">
                <Icon name="search" className="w-3.5 h-3.5" />
              </span>
            </div>

            <select
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              className="field text-xs py-1.5 px-2 min-h-[36px] w-auto bg-white border-[#dce0d4]"
              aria-label="排序方式"
            >
              <option value="score_desc">综合评分最高</option>
              <option value="price_asc">建议价格: 从低到高</option>
              <option value="price_desc">建议价格: 从高到低</option>
            </select>
          </div>
        </div>
      </section>

      {/* 结果标题与快捷跨价位对比按钮 */}
      <div className="flex items-center justify-between mb-4 px-1">
        <div>
          <h2 className="text-base font-bold text-[#213b2e]">
            {category === "all" ? "全品类装备推荐榜" : `${categoriesQuery.data?.find((c) => c.id === category)?.name || "装备"} 权威推荐`}
            <span className="text-xs text-[#687366] font-mono ml-2 font-normal">
              共收录 {items.length} 款装备
            </span>
          </h2>
        </div>

        <button
          type="button"
          onClick={handleQuickTierCompare}
          className="text-xs text-[#1d4434] font-semibold hover:underline flex items-center gap-1"
        >
          <Icon name="compare" className="w-3.5 h-3.5" />
          <span>跨价位一键对比 (入门 vs 进阶 vs 旗舰)</span>
        </button>
      </div>

      {/* 卡片网格 */}
      {rankingsQuery.isPending ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div key={i} className="card p-6 h-96 animate-pulse bg-white/60" />
          ))}
        </div>
      ) : items.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {items.map((item) => (
            <RankingCard
              key={item.id}
              item={item}
              selected={selectedIds.includes(item.id)}
              onToggleSelect={toggleSelect}
            />
          ))}
        </div>
      ) : (
        <div className="card p-12 text-center bg-white border border-[#dce0d4] rounded-lg">
          <Icon name="search" className="w-8 h-8 text-[#889280] mx-auto mb-3" />
          <h3 className="font-bold text-base text-[#213b2e] mb-1">未找到匹配条件的装备</h3>
          <p className="text-xs text-[#687366] mb-4">
            试试重置筛选条件或换一个搜索词。
          </p>
          <button
            type="button"
            onClick={() => {
              setTier("all");
              setSource("all");
              setQuery("");
            }}
            className="btn-primary text-xs"
          >
            重置全部筛选
          </button>
        </div>
      )}

      {/* 底部悬浮对比抽屉 */}
      <CompareDrawer
        selectedItems={selectedItems}
        onRemove={toggleSelect}
        onClear={clearSelection}
        onCompare={() => void handleStartCompare()}
      />

      {/* 横向全维对比弹窗 */}
      {isComparing && (
        <CompareModal
          matrix={compareMatrix}
          onClose={() => {
            setIsComparing(false);
            setCompareMatrix(null);
          }}
        />
      )}
    </main>
  );
}
