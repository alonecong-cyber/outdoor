"use client";

import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type CompareMatrixResponse, type GearRankingItem } from "@/lib/api";
import { Icon } from "@/components/Icon";
import { SiteHeader } from "@/components/SiteHeader";
import { RankingCard } from "@/components/rankings/RankingCard";
import { RankingDetail } from "@/components/rankings/RankingDetail";
import { CompareDrawer } from "@/components/rankings/CompareDrawer";
import { CompareModal } from "@/components/rankings/CompareModal";

const PAGE = 24;
const MAX_COMPARE = 4;

const TIERS = [
  { id: "all", name: "全部价位" },
  { id: "budget", name: "入门性价比" },
  { id: "mid", name: "进阶主力" },
  { id: "flagship", name: "顶级旗舰" },
];
const GENDERS = [
  { id: "all", name: "不限" },
  { id: "men", name: "男款" },
  { id: "women", name: "女款" },
];
const SORTS = [
  { id: "score_desc", name: "综合得分最高" },
  { id: "value_desc", name: "性价比最高" },
  { id: "awards_desc", name: "上榜次数最多" },
  { id: "price_asc", name: "价格从低到高" },
  { id: "price_desc", name: "价格从高到低" },
];
const SOURCE_NAMES: Record<string, string> = {
  OutdoorGearLab: "OutdoorGearLab 实测",
  "Switchback Travel": "Switchback 编辑榜",
  什么值得买: "什么值得买 好价/原创",
  B站: "B站 测评视频",
  小红书: "小红书 笔记",
  国货: "只看国货品牌",
};

type Filters = { category: string; tier: string; source: string; gender: string; brand: string; q: string; sort: string };
const DEFAULTS: Filters = { category: "hardshell", tier: "all", source: "all", gender: "all", brand: "all", q: "", sort: "score_desc" };

function readUrl(): Filters {
  const p = new URLSearchParams(window.location.search);
  const f = { ...DEFAULTS };
  (Object.keys(DEFAULTS) as (keyof Filters)[]).forEach((k) => {
    const v = p.get(k);
    if (v) f[k] = v;
  });
  return f;
}

function Select({ label, value, onChange, children }: { label: string; value: string; onChange: (v: string) => void; children: React.ReactNode }) {
  return (
    <label className="rk-select">
      <span className="sr-only">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>{children}</select>
      <Icon name="chevron" />
    </label>
  );
}

function Seg({ label, options, value, onChange }: { label: string; options: { id: string; name: string }[]; value: string; onChange: (v: string) => void }) {
  return (
    <div className="rk-seg" role="group" aria-label={label}>
      {options.map((o) => (
        <button key={o.id} type="button" aria-pressed={value === o.id} onClick={() => onChange(o.id)}>{o.name}</button>
      ))}
    </div>
  );
}

export default function RankingsPage() {
  const [f, setF] = useState<Filters>(DEFAULTS);
  const [ready, setReady] = useState(false);
  const [visible, setVisible] = useState(PAGE);
  const [showFilters, setShowFilters] = useState(false);
  const [selected, setSelected] = useState<GearRankingItem[]>([]);
  const [detail, setDetail] = useState<GearRankingItem | null>(null);
  const [matrix, setMatrix] = useState<CompareMatrixResponse | null>(null);
  const [comparing, setComparing] = useState(false);
  const [toast, setToast] = useState("");
  const [stuck, setStuck] = useState(false);
  const deferredQ = useDeferredValue(f.q);
  const sentinel = useRef<HTMLDivElement>(null);
  const moreRef = useRef<HTMLDivElement>(null);
  const resultsTop = useRef<HTMLDivElement>(null);

  // URL ⇄ 筛选状态：可分享、刷新不丢、浏览器后退可用
  useEffect(() => {
    setF(readUrl());
    setReady(true);
    const onPop = () => setF(readUrl());
    window.addEventListener("popstate", onPop);
    return () => window.removeEventListener("popstate", onPop);
  }, []);
  useEffect(() => {
    if (!ready) return;
    const p = new URLSearchParams();
    (Object.keys(f) as (keyof Filters)[]).forEach((k) => f[k] !== DEFAULTS[k] && p.set(k, f[k]));
    const qs = p.toString();
    const url = `${window.location.pathname}${qs ? `?${qs}` : ""}`;
    if (url !== `${window.location.pathname}${window.location.search}`) window.history.replaceState(null, "", url);
  }, [f, ready]);

  const set = useCallback((patch: Partial<Filters>) => {
    setF((prev) => ({ ...prev, ...patch, ...(patch.category && patch.category !== prev.category ? { brand: "all" } : {}) }));
    setVisible(PAGE);
  }, []);

  const flash = useCallback((msg: string) => {
    setToast(msg);
    window.setTimeout(() => setToast(""), 2600);
  }, []);

  const categoriesQuery = useQuery({ queryKey: ["rankingCategories"], queryFn: () => api.rankingCategories(), staleTime: 60_000 });
  const sourcesQuery = useQuery({ queryKey: ["rankingSources"], queryFn: () => api.rankingSources(), staleTime: 60_000 });
  const brandsQuery = useQuery({
    queryKey: ["rankingBrands", f.category],
    queryFn: () => api.rankingBrands(f.category === "all" ? undefined : f.category),
    staleTime: 60_000,
  });
  const rankingsQuery = useQuery({
    queryKey: ["rankings", f.category, f.tier, f.source, deferredQ, f.sort, f.gender, f.brand],
    queryFn: () =>
      api.rankings({
        category: f.category === "all" ? undefined : f.category,
        tier: f.tier === "all" ? undefined : f.tier,
        source: f.source === "all" ? undefined : f.source,
        gender: f.gender === "all" ? undefined : f.gender,
        brand: f.brand === "all" ? undefined : f.brand,
        q: deferredQ.trim() || undefined,
        sort: f.sort || undefined,
      }),
    enabled: ready,
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });

  const items = useMemo(() => rankingsQuery.data ?? [], [rankingsQuery.data]);
  const shown = items.slice(0, visible);
  const categories = categoriesQuery.data ?? [];
  const totalItems = categories.reduce((n, c) => n + c.total_count, 0);
  const catName = f.category === "all" ? "全品类" : categories.find((c) => c.id === f.category)?.name ?? "装备";
  const sources = (sourcesQuery.data ?? []).filter((s) => s.count > 0);
  const selectedIds = selected.map((it) => it.id);

  // 吸顶工具栏阴影 + 滚到底自动加载更多
  useEffect(() => {
    const el = sentinel.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(([e]) => setStuck(!e.isIntersecting));
    io.observe(el);
    return () => io.disconnect();
  }, []);
  useEffect(() => {
    const el = moreRef.current;
    if (!el) return undefined;
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setVisible((v) => v + PAGE), { rootMargin: "600px" });
    io.observe(el);
    return () => io.disconnect();
  }, [items.length, visible]);

  const toggleSelect = (id: string) => {
    if (selectedIds.includes(id)) return setSelected((prev) => prev.filter((it) => it.id !== id));
    if (selected.length >= MAX_COMPARE) return flash(`最多同时对比 ${MAX_COMPARE} 款，先移除一款再加`);
    const found = items.find((it) => it.id === id) ?? (detail?.id === id ? detail : null);
    if (found) setSelected((prev) => [...prev, found]);
  };

  const startCompare = async (ids: string[] = selectedIds) => {
    if (ids.length < 2) return;
    setComparing(true);
    try {
      setMatrix(await api.rankingCompare(ids));
    } catch {
      flash("对比数据加载失败，请重试");
      setComparing(false);
    }
  };

  // 当前结果里各价位的第一名（按当前排序）一键 PK
  const tierPicks = useMemo(
    () => (["budget", "mid", "flagship"].map((t) => items.find((it) => it.price_tier === t)).filter(Boolean) as GearRankingItem[]),
    [items],
  );
  const quickCompare = () => {
    setSelected(tierPicks);
    void startCompare(tierPicks.map((it) => it.id));
  };

  const chips: { key: keyof Filters; label: string }[] = [];
  if (f.tier !== "all") chips.push({ key: "tier", label: TIERS.find((t) => t.id === f.tier)?.name ?? f.tier });
  if (f.gender !== "all") chips.push({ key: "gender", label: GENDERS.find((g) => g.id === f.gender)?.name ?? f.gender });
  if (f.source !== "all") chips.push({ key: "source", label: SOURCE_NAMES[f.source] ?? f.source });
  if (f.brand !== "all") chips.push({ key: "brand", label: brandsQuery.data?.find((b) => b.brand === f.brand)?.brand_name ?? f.brand });
  if (f.q) chips.push({ key: "q", label: `“${f.q}”` });
  const extraCount = chips.filter((c) => c.key !== "tier" && c.key !== "q").length;
  const resetAll = () => set({ tier: "all", gender: "all", source: "all", brand: "all", q: "" });

  const moreFilters = (
    <>
      <div className="md:hidden">
        <Select label="排序" value={f.sort} onChange={(v) => set({ sort: v })}>
          {SORTS.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
        </Select>
      </div>
      <Seg label="款式" options={GENDERS} value={f.gender} onChange={(v) => set({ gender: v })} />
      <Select label="评测来源" value={f.source} onChange={(v) => set({ source: v })}>
        <option value="all">全部来源</option>
        {sources.map((s) => (
          <option key={s.source} value={s.source}>{SOURCE_NAMES[s.source] ?? s.source}（{s.count}）</option>
        ))}
      </Select>
      <Select label="品牌" value={f.brand} onChange={(v) => set({ brand: v })}>
        <option value="all">全部品牌（{brandsQuery.data?.length ?? 0}）</option>
        {(brandsQuery.data ?? []).map((b) => (
          <option key={b.brand} value={b.brand}>{b.brand_name}（{b.count}）</option>
        ))}
      </Select>
    </>
  );

  return (
    <main className={selected.length ? "pb-28" : ""}>
      <SiteHeader kicker="BENCHMARKS" />

      <section className="mb-4 flex flex-col gap-3 rounded-xl bg-forest px-5 py-5 text-[#f7f6e9] sm:flex-row sm:items-end sm:justify-between sm:px-7 sm:py-6 rise">
        <div>
          <p className="font-mono text-[11px] tracking-[.16em] text-[#b5c5a8]">权威榜单 · 多维横评</p>
          <h1 className="mt-1.5 text-xl font-semibold tracking-tight sm:text-3xl">装备买对不买贵，<br className="sm:hidden" /><span className="text-[#c7d39d]">看懂差价买到了什么。</span></h1>
          <p className="mt-2 hidden max-w-2xl text-[13px] sm:block leading-relaxed text-[#c5cfb9]">
            OutdoorGearLab 实验室打分 + Switchback 编辑榜单，叠加什么值得买好价与国内口碑；每一条都能点回原文核对。
          </p>
        </div>
        {categories.length > 0 && (
          <dl className="flex shrink-0 gap-5 border-t border-white/10 pt-3 font-mono sm:border-0 sm:pt-0 text-[#e5ebd3]">
            <div><dt className="text-[11px] text-[#b5c5a8]">品类</dt><dd className="text-xl font-semibold">{categories.length}</dd></div>
            <div><dt className="text-[11px] text-[#b5c5a8]">装备</dt><dd className="text-xl font-semibold">{totalItems}</dd></div>
            {sources.find((s) => s.source === "国货") && (
              <div><dt className="text-[11px] text-[#b5c5a8]">国货</dt><dd className="text-xl font-semibold">{sources.find((s) => s.source === "国货")?.count}</dd></div>
            )}
          </dl>
        )}
      </section>

      <div ref={sentinel} aria-hidden="true" />
      <div className={`rk-toolbar ${stuck ? "is-stuck" : ""}`}>
        <nav className="rk-pills" aria-label="装备品类">
          <button type="button" className="rk-pill" aria-pressed={f.category === "all"} onClick={() => set({ category: "all" })}>
            全部 <small>{totalItems || ""}</small>
          </button>
          {categories.map((c) => (
            <button key={c.id} type="button" className="rk-pill" aria-pressed={f.category === c.id} onClick={() => set({ category: c.id })}>
              {c.name} <small>{c.total_count}</small>
            </button>
          ))}
        </nav>

        <div className="mt-2.5 flex items-center gap-2 md:flex-wrap">
          <div className="relative min-w-0 flex-1 md:basis-56">
            <Icon name="search" className="pointer-events-none absolute left-3 top-1/2 !h-4 !w-4 -translate-y-1/2 text-dim" />
            <input
              type="search"
              value={f.q}
              onChange={(e) => set({ q: e.target.value })}
              placeholder={`在${catName}里搜品牌 / 型号，如 始祖鸟、Speedgoat`}
              aria-label="搜索装备"
              className="h-[38px] w-full rounded-lg border border-line bg-panel pl-9 pr-3 text-[13px] text-ink outline-none placeholder:text-[#899181] focus:border-forest"
            />
          </div>
          <div className="hidden md:block">
            <Seg label="价格梯队" options={TIERS} value={f.tier} onChange={(v) => set({ tier: v })} />
          </div>
          <div className="hidden md:block">
            <Select label="排序" value={f.sort} onChange={(v) => set({ sort: v })}>
              {SORTS.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
            </Select>
          </div>
          <button
            type="button"
            onClick={() => setShowFilters((v) => !v)}
            aria-expanded={showFilters}
            className={`inline-flex min-h-[38px] items-center gap-1.5 rounded-lg border px-3 text-[13px] ${showFilters || extraCount ? "border-forest text-forest" : "border-line text-ink"} bg-panel`}
          >
            <Icon name="filter" className="!h-4 !w-4" />
            <span className="md:hidden">筛选排序</span><span className="hidden md:inline">更多筛选</span>{extraCount ? ` · ${extraCount}` : ""}
          </button>
        </div>

        <div className="rk-mobile-row mt-2 flex items-center gap-2 md:hidden">
          <div className="min-w-0 flex-1 overflow-x-auto" style={{ scrollbarWidth: "none" }}>
            <Seg label="价格梯队" options={TIERS} value={f.tier} onChange={(v) => set({ tier: v })} />
          </div>
        </div>
        {showFilters && <div className="mt-2 flex flex-wrap items-center gap-2">{moreFilters}</div>}

        {chips.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {chips.map((c) => (
              <button key={c.key} type="button" className="rk-chip" onClick={() => set({ [c.key]: DEFAULTS[c.key] } as Partial<Filters>)} aria-label={`移除筛选：${c.label}`}>
                {c.label}<Icon name="close" />
              </button>
            ))}
            <button type="button" onClick={resetAll} className="min-h-[30px] px-2 text-xs text-dim underline-offset-2 hover:underline">清除全部</button>
          </div>
        )}
      </div>

      <div ref={resultsTop} className="mb-3 flex flex-wrap items-end justify-between gap-2 px-0.5">
        <h2 className="text-lg font-semibold text-ink">
          {catName}推荐
          <span className="ml-2 font-mono text-xs font-normal text-dim">
            {rankingsQuery.isFetching && !rankingsQuery.isPending ? "更新中…" : `${items.length} 款`}
          </span>
        </h2>
        {f.category !== "all" && tierPicks.length >= 2 && (
          <button type="button" onClick={quickCompare} className="inline-flex min-h-9 items-center gap-1.5 rounded-md px-2 text-[13px] font-semibold text-forest hover:bg-[#edf0e5]">
            <Icon name="compare" className="!h-4 !w-4" />
            入门 vs 进阶 vs 旗舰 一键对比
          </button>
        )}
      </div>

      {rankingsQuery.isPending ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => <div key={i} className="h-[440px] animate-pulse rounded-lg border border-line bg-panel/70" />)}
        </div>
      ) : rankingsQuery.isError ? (
        <div className="empty-state">
          <Icon name="mountain" />
          <h2>榜单暂时没有加载出来</h2>
          <p>请确认后端已启动，然后重试。</p>
          <button type="button" className="btn btn-ghost" onClick={() => void rankingsQuery.refetch()}>重新加载</button>
        </div>
      ) : items.length > 0 ? (
        <>
          <div className={`grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 transition-opacity ${rankingsQuery.isFetching ? "opacity-60" : ""}`}>
            {shown.map((item, i) => (
              <RankingCard
                key={item.id}
                item={item}
                rank={i + 1}
                selected={selectedIds.includes(item.id)}
                onToggleSelect={toggleSelect}
                onOpen={setDetail}
              />
            ))}
          </div>
          {items.length > visible && (
            <div ref={moreRef} className="mt-6 flex justify-center">
              <button type="button" onClick={() => setVisible((v) => v + PAGE)} className="btn btn-ghost">
                加载更多 <small className="text-dim">还有 {items.length - visible} 款</small>
              </button>
            </div>
          )}
        </>
      ) : (
        <div className="empty-state">
          <Icon name="search" />
          <h2>没有符合条件的装备</h2>
          <p>{f.q ? `「${f.q}」在${catName}里没有结果，` : ""}试试放宽筛选，或切换到全部品类。</p>
          <div className="flex flex-wrap justify-center gap-2">
            <button type="button" onClick={resetAll} className="btn-primary">清除筛选</button>
            {f.category !== "all" && <button type="button" onClick={() => set({ category: "all" })} className="btn btn-ghost">在全部品类中查找</button>}
          </div>
        </div>
      )}

      <CompareDrawer
        selectedItems={selected}
        onRemove={toggleSelect}
        onClear={() => setSelected([])}
        onCompare={() => void startCompare()}
        loading={comparing && !matrix}
      />

      <RankingDetail
        item={detail}
        selected={detail ? selectedIds.includes(detail.id) : false}
        onToggleSelect={toggleSelect}
        onClose={() => setDetail(null)}
      />

      {comparing && matrix && (
        <CompareModal
          matrix={matrix}
          onRemove={(id) => {
            const ids = selectedIds.filter((x) => x !== id);
            setSelected((prev) => prev.filter((it) => it.id !== id));
            if (ids.length >= 2) void startCompare(ids);
            else { setComparing(false); setMatrix(null); }
          }}
          onClose={() => { setComparing(false); setMatrix(null); }}
        />
      )}

      {toast && (
        <div role="status" className="fixed left-1/2 top-4 z-[70] -translate-x-1/2 rounded-lg bg-ink px-4 py-2.5 text-[13px] text-white shadow-lg rise">{toast}</div>
      )}
    </main>
  );
}
