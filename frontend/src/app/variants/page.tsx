"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrowseControls } from "@/components/BrowseControls";
import { DealCard, DealSkeletons } from "@/components/DealCard";
import { Icon } from "@/components/Icon";
import { ProductImage } from "@/components/ProductImage";
import { SiteHeader } from "@/components/SiteHeader";
import { api } from "@/lib/api";
import { hasPrice, isConfirmed, matchesCategory, officialStyleNumber, specs } from "@/lib/catalog";
import { money } from "@/lib/format";

export default function VariantsPage() {
  const [brand, setBrand] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [sort, setSort] = useState("");
  const [visible, setVisible] = useState(24);
  useEffect(() => setVisible(24), [brand, query, category, sort]);
  const trimmed = query.trim();
  // 服务端搜索：q/brand/sort 交给后端（含品牌中文名）；类别是轻量标题关键词，保留在前端。
  const variants = useQuery({
    queryKey: ["variants", brand, trimmed, sort],
    queryFn: () => api.variants({ brand, q: trimmed || undefined, sort: sort || undefined }),
  });
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const initial = params.get("q");
    if (initial) setQuery(initial);
    const initialSort = params.get("sort");
    if (initialSort === "price_asc" || initialSort === "price_desc") setSort(initialSort);
  }, []);
  const dealHits = useQuery({
    queryKey: ["deal-hits", trimmed],
    queryFn: () => api.deals({ q: trimmed, limit: 6 }),
    enabled: trimmed.length > 1,
  });
  const filtered = useMemo(() => {
    const rows = (variants.data ?? []).filter((variant) => {
      const text = `${variant.brand_name} ${variant.style_name} ${officialStyleNumber(variant.style_number)} ${variant.color} ${variant.size} ${variant.category}`;
      return matchesCategory(text, category);
    });
    if (sort) return rows; // 价格排序由后端给出
    return rows.sort((a, b) => Number(isConfirmed(b.match_status)) - Number(isConfirmed(a.match_status)));
  }, [variants.data, category, sort]);
  const reset = () => { setQuery(""); setBrand(""); setCategory("all"); setSort(""); };
  return <main>
    <SiteHeader kicker="GEAR INDEX" />
    <section className="catalog-intro rise"><div><p className="eyebrow">THE GEAR INDEX / 找到你的下一件装备</p><h1>装备各有长处，价格有据可查。</h1><p>按品牌、型号与规格找装备，核对每一条价格线索。</p></div><p className="catalog-intro-note">已确认规格与待补齐线索分明展示。核验报价、历史线报价分别标注。</p></section>
    <BrowseControls query={query} setQuery={setQuery} brand={brand} setBrand={setBrand} category={category} setCategory={setCategory} sort={sort} setSort={setSort} placeholder="搜索品牌、型号、颜色、尺码…" />
    <section aria-labelledby="catalog-results"><div className="section-heading"><h2 id="catalog-results">装备目录<small>{variants.data ? `${filtered.length} 个规格` : "GEAR INDEX"}</small></h2><span>{sort ? "已按价格排序" : "同款同色同码，才有比较意义"}</span></div>
      {variants.isPending ? <DealSkeletons /> : variants.isError ? <div className="empty-state"><Icon name="grid" /><h2>目录暂时无法加载</h2><p>请稍后重新载入装备目录。</p><button type="button" className="btn btn-ghost" onClick={() => void variants.refetch()}>重新加载</button></div> : filtered.length ? <>
        <ul className="deal-grid">{filtered.slice(0, visible).map((variant, index) => {
        const confirmed = isConfirmed(variant.match_status);
        const cnyVerified = confirmed && variant.currency === "CNY" && variant.price_basis === "verified" && hasPrice(variant.min_price_cents);
        const verified = confirmed && variant.price_basis === "verified" && hasPrice(variant.min_price_cents);
        const reported = variant.reported_min_price_cents ?? (variant.price_basis === undefined ? variant.min_price_cents : null);
        const value = verified ? variant.min_price_cents : reported;
        const specification = specs(variant.color, variant.size);
        const styleNumber = officialStyleNumber(variant.style_number);
        return <li key={variant.id} className={`rise rise-${(index % 5) + 1}`}><Link href={`/variants/${variant.id}`} className="deal-card catalog-card"><div className="deal-image"><ProductImage src={variant.image} alt={variant.style_name} /><span className="image-category">{variant.category || "户外装备"}</span><span className="image-index num">GEAR / {String(index + 1).padStart(2, "0")}</span></div><div className="deal-card-body"><div className="deal-meta"><span className="catalog-brand">{variant.brand_name || variant.brand}</span><span className={`badge catalog-match ${confirmed ? "badge-verified" : "badge-reported"}`}>{confirmed ? "规格已确认" : "规格待补齐"}</span></div><h2 className="catalog-title">{variant.style_name}</h2><p className="catalog-specs">{styleNumber && <span>款号 {styleNumber}</span>}{specification.map((spec) => <span key={spec}>{spec}</span>)}{!styleNumber && !specification.length && <span>颜色、尺码尚待确认</span>}</p><div className="deal-price-row"><div><span className="price-label">{cnyVerified ? "当前核验报价" : verified ? `官网核验价 · 原币（${variant.currency}）` : hasPrice(reported) ? "历史线报最低 · 非当前价" : "暂无核验报价"}</span>{hasPrice(value) ? <span className="deal-price">{money(value, variant.currency)}</span> : <span className="price-unknown">等待价格核验</span>}</div><span className="card-action">查看装备<Icon name="arrow" /></span></div><p className="mt-3 text-[9px] text-dim">{variant.deal_count} 条相关线报</p></div></Link></li>;
      })}</ul>
        {filtered.length > visible && <div className="load-more"><button type="button" className="btn btn-ghost" onClick={() => setVisible((count) => count + 24)}>加载更多装备<small className="ml-2 text-dim">还有 {filtered.length - visible} 件</small></button></div>}
      </> : <div className="empty-state"><Icon name="search" /><h2>暂时没有符合条件的装备</h2><p>试试其他关键词，或从最新优惠线索中寻找装备。</p>{brand || query || category !== "all" ? <button type="button" className="btn btn-ghost" onClick={reset}>清除筛选</button> : <Link href="/" className="btn btn-ghost">发现优惠<Icon name="arrow" /></Link>}</div>}
      <p className="results-note">历史线报最低只表示来源文章曾报告的价格。规格待补齐时，不据此推断同一商品的多渠道最低价。</p>
    </section>
    {trimmed.length > 1 && !!dealHits.data?.length && <section className="detail-related" aria-label="相关线报"><div className="section-heading"><h2>线报里也找到了<small>{dealHits.data.length} 条</small></h2><span>目录没有收录时，先看这些优惠线索</span></div><ul className="deal-grid">{dealHits.data.map((deal, index) => <DealCard deal={deal} index={index} key={deal.id} />)}</ul></section>}
  </main>;
}
