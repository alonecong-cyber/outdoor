"use client";

import { Icon } from "@/components/Icon";
import { CATEGORIES } from "@/lib/catalog";

export const BRANDS = [
  { slug: "arcteryx", label: "始祖鸟" },
  { slug: "the-north-face", label: "北面" },
  { slug: "patagonia", label: "巴塔哥尼亚" },
  { slug: "columbia", label: "哥伦比亚" },
  { slug: "camel", label: "骆驼" },
  { slug: "pelliot", label: "伯希和" },
  { slug: "kailas", label: "凯乐石" },
  { slug: "mammut", label: "猛犸象" },
  { slug: "marmot", label: "土拨鼠" },
];

export const SORT_OPTIONS = [
  { value: "", label: "最新入库" },
  { value: "price_asc", label: "价格 低→高" },
  { value: "price_desc", label: "价格 高→低" },
];

export function BrowseControls({ query, setQuery, brand, setBrand, category, setCategory, sort, setSort, placeholder = "搜索品牌、型号、装备…" }: {
  query: string; setQuery: (value: string) => void;
  brand: string; setBrand: (value: string) => void;
  category: string; setCategory: (value: string) => void;
  sort: string; setSort: (value: string) => void;
  placeholder?: string;
}) {
  return <section className="browse-controls rise rise-2" aria-label="搜索和筛选装备">
    <div className="search-row">
      <div className="search-field"><Icon name="search" /><input type="search" className="field" aria-label="搜索装备" placeholder={placeholder} value={query} onChange={(e) => setQuery(e.target.value)} />{query && <button type="button" className="clear-search" onClick={() => setQuery("")} aria-label="清空搜索"><Icon name="close" /></button>}</div>
      <div className="brand-select"><select className="field" aria-label="选择品牌" value={brand} onChange={(e) => setBrand(e.target.value)}><option value="">全部品牌</option>{BRANDS.map((item) => <option key={item.slug} value={item.slug}>{item.label}</option>)}</select><Icon name="chevron" /></div>
      <div className="brand-select"><select className="field" aria-label="排序方式" value={sort} onChange={(e) => setSort(e.target.value)}>{SORT_OPTIONS.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select><Icon name="chevron" /></div>
    </div>
    <div className="category-row" role="group" aria-label="按装备类别筛选">{CATEGORIES.map((item) => <button key={item.id} type="button" aria-pressed={category === item.id} className={category === item.id ? "is-active" : ""} onClick={() => setCategory(item.id)}>{item.label}</button>)}</div>
  </section>;
}
