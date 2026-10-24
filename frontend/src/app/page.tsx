"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { BrowseControls } from "@/components/BrowseControls";
import { DealCard, DealSkeletons } from "@/components/DealCard";
import { Icon } from "@/components/Icon";
import { SiteHeader } from "@/components/SiteHeader";
import { StatusStrip } from "@/components/StatusStrip";
import { api } from "@/lib/api";
import { matchesCategory } from "@/lib/catalog";

export default function DealFeedPage() {
  const [brand, setBrand] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const deals = useQuery({ queryKey: ["deals", brand], queryFn: () => api.deals({ brand, limit: 100 }), staleTime: 60_000 });
  const filtered = useMemo(() => (deals.data ?? []).filter((deal) => deal.title.toLowerCase().includes(query.trim().toLowerCase()) && matchesCategory(deal.title, category)), [deals.data, query, category]);
  const reset = () => { setQuery(""); setBrand(""); setCategory("all"); };
  return <main>
    <SiteHeader kicker="DISCOVER" />
    <section className="feed-hero rise">
      <svg className="hero-landscape" viewBox="0 0 680 260" fill="none" preserveAspectRatio="xMidYMid slice" aria-hidden="true"><path d="m0 260 206-240 90 113 87-85 141 212H0Z" fill="#93ad7a" opacity=".13" /><path d="m125 260 215-240 68 98 82-63 190 205H125Z" fill="#b8c38c" opacity=".15" /><path d="M-20 216 110 155 173 184 339 20 405 119 489 56 700 256M-20 239 110 177 175 205 338 45 402 145 488 80 680 267M-20 260 112 200 179 227 338 71 401 171 488 107 659 279M91 275 180 250 338 97 397 198 489 135 636 285M219 275 339 124 395 223 489 162 615 291M240 287 339 151 393 249 490 190 595 299M268 299 339 178 390 275 491 219 573 307" stroke="#dce7bc" strokeWidth=".7" /><circle cx="540" cy="57" r="22" stroke="#dce7bc" strokeWidth=".7" /><path d="M540 28v11m0 36v11m-29-29h11m36 0h11" stroke="#dce7bc" strokeWidth=".7" /></svg>
      <div><p className="eyebrow">GOOD GEAR. CLEAR PRICES. / 户外装备价格手册</p><h1>装备选得对，<br /><span>下一程走得远。</span></h1><p>看清价格、规格和优惠条件，<br className="sm:hidden" />为每一次出发认真挑选。</p></div>
      <div className="hero-aside"><span className="field-note">BE READY<br />FOR OUT THERE.</span><p>从一条优惠线索，找到适合自己的装备。</p><Link className="btn-primary" href="/variants">逛逛装备目录<Icon name="arrow" /></Link></div>
    </section>
    <StatusStrip />
    <BrowseControls query={query} setQuery={setQuery} brand={brand} setBrand={setBrand} category={category} setCategory={setCategory} />
    <section aria-labelledby="latest-deals"><div className="section-heading"><h2 id="latest-deals">出发前的好价线索<small>{deals.data ? `${filtered.length} 条` : "FIELD NOTES"}</small></h2><span>最新入库 · 按标题分类</span></div>
      {deals.isPending ? <DealSkeletons /> : deals.isError ? <div className="empty-state"><Icon name="mountain" /><h2>优惠暂时没有加载出来</h2><p>连接恢复后可重新载入已有线报。</p><button type="button" className="btn btn-ghost" onClick={() => void deals.refetch()}>重新加载</button></div> : filtered.length > 0 ? <ul className="deal-grid">{filtered.map((deal, index) => <DealCard key={deal.id} deal={deal} index={index} />)}</ul> : <div className="empty-state"><Icon name="search" /><h2>{deals.data?.length || brand || query || category !== "all" ? "暂时没有符合条件的装备" : "优惠线索正在准备中"}</h2><p>{brand || query || category !== "all" ? "试试其他关键词，或查看全部装备。" : "线报由后台更新。新的优惠入库后，会出现在这里。"}</p>{(brand || query || category !== "all") && <button type="button" className="btn btn-ghost" onClick={reset}>清除筛选</button>}</div>}
      <p className="results-note">线报价格来自来源文章，可能已过期或附有特定条件。进入详情核对适用规格、优惠说明与核验状态。</p>
    </section>
  </main>;
}
