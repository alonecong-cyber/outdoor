"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import { SiteHeader } from "@/components/SiteHeader";
import { Sparkline } from "@/components/Sparkline";
import { ProductImage } from "@/components/ProductImage";
import { api, type VariantDetail } from "@/lib/api";
import { channelName, money } from "@/lib/format";

const BRANDS = [
  { slug: "", label: "全部" },
  { slug: "arcteryx", label: "始祖鸟" },
  { slug: "the-north-face", label: "北面" },
  { slug: "patagonia", label: "巴塔哥尼亚" },
  { slug: "columbia", label: "哥伦比亚" },
  { slug: "camel", label: "骆驼" },
  { slug: "pelliot", label: "伯希和" },
  { slug: "kailas", label: "凯乐石" },
];

function bestPrice(d: VariantDetail | undefined) {
  if (!d) return null;
  const live = d.channels.filter((c) => c.price_cents != null);
  const image = (d.channels.find((c) => c.image)?.image) ?? d.image ?? "";
  if (live.length === 0) return image ? { image, noPrice: true } : null;
  // 跨币种不能直接比分：最低价只在国内人民币渠道里选；没有人民币渠道再退到外币渠道
  const pool = live.filter((c) => c.currency === "CNY");
  const candidates = pool.length > 0 ? pool : live;
  const best = candidates.reduce((a, b) => ((a.price_cents ?? 0) <= (b.price_cents ?? 0) ? a : b));
  return {
    channel: best.channel,
    cents: best.price_cents!,
    currency: best.currency,
    history: best.history,
    image,
  };
}

/** 商品目录：从线报里长出来的款，聚合各渠道价格与历史。 */
export default function VariantsPage() {
  const [brand, setBrand] = useState("");
  const [q, setQ] = useState("");

  const variantsQuery = useQuery({
    queryKey: ["variants", brand],
    queryFn: () => api.variants(brand ? { brand } : {}),
  });

  const variants = variantsQuery.data ?? [];
  const filtered = useMemo(
    () =>
      variants.filter((v) =>
        q ? `${v.style_name} ${v.style_number} ${v.color}`.toLowerCase().includes(q.toLowerCase()) : true,
      ),
    [variants, q],
  );

  const details = useQueries({
    queries: filtered.slice(0, 24).map((v) => ({
      queryKey: ["variant", v.id] as const,
      queryFn: () => api.variant(v.id),
    })),
  });

  return (
    <main>
      <SiteHeader kicker="CATALOG" />

      <div className="rise rise-1 mb-5 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="flex flex-wrap gap-2">
          {BRANDS.map((b) => (
            <button
              key={b.slug}
              type="button"
              onClick={() => setBrand(b.slug)}
              className={`btn rounded-full px-3.5 py-1.5 text-xs ${
                brand === b.slug
                  ? "bg-accent text-[#140b06]"
                  : "border border-line text-dim hover:text-ink"
              }`}
            >
              {b.label}
            </button>
          ))}
        </div>
        <input
          className="field sm:ml-auto sm:max-w-56"
          placeholder="搜型号 / 颜色…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
      </div>

      {variantsQuery.isLoading && <p className="micro-label">载入目录…</p>}
      {variantsQuery.isError && (
        <p className="text-sm text-accent">后端不可达：{(variantsQuery.error as Error).message}</p>
      )}

      <ul className="space-y-3">
        {filtered.slice(0, 24).map((v, i) => {
          const d = details[i].data;
          const best = bestPrice(d);
          return (
            <li key={v.id} className={`rise rise-${(i % 5) + 1}`}>
              <Link href={`/variants/${v.id}`} className="card block p-4 transition-colors hover:border-dim">
                <div className="flex items-start gap-3.5">
                  <ProductImage
                    src={best?.image}
                    alt={`${v.style_name} ${v.color}`}
                    className="h-20 w-20 shrink-0 rounded-sm border border-line object-cover sm:h-24 sm:w-24"
                  />
                  <div className="min-w-0 flex-1">
                    <p className="micro-label">
                      {v.brand_name} · {v.category || "户外"}
                    </p>
                    <h2 className="font-display mt-1 truncate text-base font-bold">
                      {v.style_name}
                      <span className="num ml-2 text-xs text-dim">#{v.style_number}</span>
                    </h2>
                    <p className="mt-1 text-sm text-dim">
                      {v.color} · {v.size}
                    </p>
                    {best && !("noPrice" in best) ? (
                      <div className="mt-2">
                        <p className="num text-lg font-semibold text-accent">
                          {money(best.cents, best.currency)}
                          <span className="micro-label ml-2 not-italic">
                            {channelName(best.channel)}
                          </span>
                        </p>
                      </div>
                    ) : (
                      <p className="micro-label mt-2">无线报价格点</p>
                    )}
                  </div>
                </div>
                {best && !("noPrice" in best) && best.history.length >= 2 && (
                  <div className="mt-3 border-t border-line pt-2">
                    <Sparkline points={best.history} width={260} height={40} />
                  </div>
                )}
              </Link>
            </li>
          );
        })}
      </ul>

      {filtered.length === 0 && !variantsQuery.isLoading && (
        <p className="micro-label">
          目录还是空的——商品从线报里长出来：去「线报」页拉取最新优惠。
        </p>
      )}
    </main>
  );
}
