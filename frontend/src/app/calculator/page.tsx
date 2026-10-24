"use client";

import { useMutation } from "@tanstack/react-query";
import { useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";

import { SiteHeader } from "@/components/SiteHeader";
import { api, type FillerResult, type OverseasResult, type QuoteResult } from "@/lib/api";
import { cny, delta, promoName, usd } from "@/lib/format";

type Tab = "cn" | "filler" | "overseas";
const TABS: { id: Tab; label: string }[] = [
  { id: "cn", label: "国内到手价" },
  { id: "filler", label: "凑单助手" },
  { id: "overseas", label: "海淘到手价" },
];

// ---------- 国内：优惠构造器 ----------

type PromoRow = {
  id: string;
  kind: string;
  name: string;
  threshold: string; // 元
  amount: string; // 元
  rate: string; // %
  exclusiveGroup: string;
};

const KIND_OPTIONS = [
  "direct_discount",
  "member_price",
  "store_coupon",
  "store_full_reduce",
  "cross_store_full_reduce",
  "platform_coupon",
  "red_packet",
  "payment_discount",
  "rebate",
  "cashback",
];

function yuanToCen(v: string): number {
  return Math.round(parseFloat(v || "0") * 100);
}

function CnQuote() {
  const [base, setBase] = useState("3998");
  const [rows, setRows] = useState<PromoRow[]>([
    { id: "s1", kind: "store_coupon", name: "店铺券", threshold: "3000", amount: "300", rate: "", exclusiveGroup: "" },
    { id: "p1", kind: "platform_coupon", name: "平台券", threshold: "", amount: "100", rate: "", exclusiveGroup: "" },
  ]);
  const [result, setResult] = useState<QuoteResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.quoteByBody({
        base_price_cents: yuanToCen(base),
        promos: rows.map((r) => ({
          id: r.id,
          kind: r.kind,
          name: r.name,
          threshold_cents: yuanToCen(r.threshold),
          amount_cents: yuanToCen(r.amount),
          rate: r.rate ? parseFloat(r.rate) / 100 : 0,
          exclusive_group: r.exclusiveGroup,
        })),
      }),
    onSuccess: setResult,
  });

  const setRow = (i: number, patch: Partial<PromoRow>) =>
    setRows((prev) => prev.map((r, j) => (j === i ? { ...r, ...patch } : r)));

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="micro-label">标价（元）</span>
        <input className="field mt-1" inputMode="decimal" value={base} onChange={(e) => setBase(e.target.value)} />
      </label>

      <div className="space-y-2">
        <p className="micro-label">可用优惠（按适用条件计算组合）</p>
        {rows.map((r, i) => (
          <div key={r.id} className="card grid grid-cols-2 gap-2 p-3 sm:grid-cols-6">
            <select
              className="field col-span-2"
              value={r.kind}
              onChange={(e) => setRow(i, { kind: e.target.value })}
            >
              {KIND_OPTIONS.map((k) => (
                <option key={k} value={k}>
                  {promoName(k)}
                </option>
              ))}
            </select>
            <input
              className="field"
              placeholder="名称"
              value={r.name}
              onChange={(e) => setRow(i, { name: e.target.value })}
            />
            <input
              className="field"
              placeholder="门槛元"
              inputMode="decimal"
              value={r.threshold}
              onChange={(e) => setRow(i, { threshold: e.target.value })}
            />
            <input
              className="field"
              placeholder="立减元"
              inputMode="decimal"
              value={r.amount}
              onChange={(e) => setRow(i, { amount: e.target.value })}
            />
            <input
              className="field"
              placeholder="折扣%（可空）"
              inputMode="decimal"
              value={r.rate}
              onChange={(e) => setRow(i, { rate: e.target.value })}
            />
            <div className="col-span-2 flex items-center gap-2 sm:col-span-6">
              <input
                className="field"
                placeholder="互斥组（同组只取一张）"
                value={r.exclusiveGroup}
                onChange={(e) => setRow(i, { exclusiveGroup: e.target.value })}
              />
              <button
                type="button"
                className="btn btn-ghost shrink-0 text-xs"
                onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
              >
                移除
              </button>
            </div>
          </div>
        ))}
        <button
          type="button"
          className="btn btn-ghost text-xs"
          onClick={() =>
            setRows((prev) => [
              ...prev,
              {
                id: `p${prev.length + 1}`,
                kind: "store_full_reduce",
                name: "",
                threshold: "",
                amount: "",
                rate: "",
                exclusiveGroup: "",
              },
            ])
          }
        >
          + 添加优惠
        </button>
      </div>

      <button type="button" className="btn btn-primary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        计算最低到手价
      </button>
      {mutation.isError && <p className="text-xs text-accent">{(mutation.error as Error).message}</p>}

      {result && (
        <div className="rise card p-4">
          <p className="micro-label mb-2">逐项瀑布（最优组合）</p>
          <ol className="space-y-1 text-sm">
            <li className="flex justify-between">
              <span className="text-dim">标价</span>
              <span className="num">{cny(result.base_price_cents)}</span>
            </li>
            {result.steps.map((s) => (
              <li key={s.promo_id} className="flex justify-between">
                <span>
                  {promoName(s.kind)} <span className="text-xs text-dim">{s.promo_name}</span>
                </span>
                <span className="num text-moss">{delta(s.delta_cents)}</span>
              </li>
            ))}
          </ol>
          <div className="mt-3 space-y-1 border-t border-line pt-2 text-sm">
            <div className="flex justify-between">
              <span className="text-dim">当下实付</span>
              <span className="num">{cny(result.paid_now_cents)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-dim">事后返利</span>
              <span className="num text-moss">−{cny(result.rebate_cents).slice(1)}</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="font-display font-bold">最低到手价</span>
              <span className="num text-xl font-semibold text-accent">{cny(result.effective_cents)}</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------- 海淘 ----------

function OverseasQuote({ initialUsd }: { initialUsd?: string }) {
  // 默认值 = PRD 验收样例：$450 25% 折扣 + 10% 码 + 8% 返现 + 7.1 汇率 + ¥220 转运 → 2635.42
  const [form, setForm] = useState({
    usd_price: initialUsd ?? "450",
    discount: "25",
    coupon_code: "10",
    cashback: "8",
    us_shipping: "0",
    rate: "7.1",
    transfer_fee_cny: "220",
  });
  const [result, setResult] = useState<OverseasResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.overseas({
        usd_price: parseFloat(form.usd_price),
        discount: parseFloat(form.discount || "0") / 100,
        coupon_code: parseFloat(form.coupon_code || "0") / 100,
        cashback: parseFloat(form.cashback || "0") / 100,
        us_shipping: parseFloat(form.us_shipping || "0"),
        rate: parseFloat(form.rate),
        transfer_fee_cny: parseFloat(form.transfer_fee_cny || "0"),
      }),
    onSuccess: setResult,
  });

  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((prev) => ({ ...prev, [k]: e.target.value }));

  const fields: [keyof typeof form, string][] = [
    ["usd_price", "美元标价 $"],
    ["discount", "活动折扣 %"],
    ["coupon_code", "折扣码 %"],
    ["cashback", "返现 %"],
    ["us_shipping", "美国运费 $"],
    ["rate", "汇率 USD→CNY"],
    ["transfer_fee_cny", "转运费 ¥"],
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {fields.map(([k, label]) => (
          <label key={k} className="block">
            <span className="micro-label">{label}</span>
            <input className="field mt-1" inputMode="decimal" value={form[k]} onChange={set(k)} />
          </label>
        ))}
      </div>
      <button type="button" className="btn btn-primary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        计算海淘到手价
      </button>
      {mutation.isError && <p className="text-xs text-accent">{(mutation.error as Error).message}</p>}

      {result && (
        <div className="rise card space-y-1 p-4 text-sm">
          <div className="flex justify-between">
            <span className="text-dim">商品实付</span>
            <span className="num">{usd(result.goods_paid_usd)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">含运费美元小计</span>
            <span className="num">{usd(result.total_usd)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">折人民币（含运费）</span>
            <span className="num">¥{result.goods_shipping_cny.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">行邮税 20%</span>
            <span className="num">
              ¥{result.tax_cny.toFixed(2)}
              {result.tax_exempt && <span className="micro-label ml-2 text-moss">≤50 免征</span>}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">转运费</span>
            <span className="num">¥{result.transfer_fee_cny.toFixed(2)}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-dim">返现（事后）</span>
            <span className="num text-moss">−¥{result.cashback_cny.toFixed(2)}</span>
          </div>
          <div className="flex items-baseline justify-between border-t border-line pt-2">
            <span className="font-display font-bold">海淘到手价</span>
            <span className="num text-xl font-semibold text-accent">¥{result.landed_cny.toFixed(2)}</span>
          </div>
          {result.warnings.map((w) => (
            <p key={w} className="text-xs text-accent">
              ⚠ {w}
            </p>
          ))}
          {result.notes.map((n) => (
            <p key={n} className="micro-label">
              {n}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- 凑单 ----------

type FillerRow = { id: string; name: string; price: string };

function FillerCalc() {
  const [threshold, setThreshold] = useState("3000");
  const [rows, setRows] = useState<FillerRow[]>([
    { id: "a", name: "袜子", price: "1000" },
    { id: "b", name: "帽子", price: "1500" },
    { id: "c", name: "腰带", price: "800" },
    { id: "d", name: "手套", price: "2000" },
  ]);
  const [result, setResult] = useState<FillerResult | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      api.filler({
        threshold_cents: yuanToCen(threshold),
        items: rows.map((r) => ({
          id: r.id,
          name: r.name,
          price_cents: yuanToCen(r.price),
        })),
      }),
    onSuccess: setResult,
  });

  const chosen = result?.ok
    ? rows.filter((r) => result.item_ids.includes(r.id))
    : [];

  return (
    <div className="space-y-4">
      <label className="block">
        <span className="micro-label">满减门槛（元）</span>
        <input className="field mt-1" inputMode="decimal" value={threshold} onChange={(e) => setThreshold(e.target.value)} />
      </label>
      <div className="space-y-2">
        <p className="micro-label">候选加购商品</p>
        {rows.map((r, i) => (
          <div key={r.id} className="card flex gap-2 p-3">
            <input
              className="field"
              placeholder="名称"
              value={r.name}
              onChange={(e) =>
                setRows((prev) => prev.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)))
              }
            />
            <input
              className="field"
              placeholder="价格元"
              inputMode="decimal"
              value={r.price}
              onChange={(e) =>
                setRows((prev) => prev.map((x, j) => (j === i ? { ...x, price: e.target.value } : x)))
              }
            />
            <button
              type="button"
              className="btn btn-ghost shrink-0 text-xs"
              onClick={() => setRows((prev) => prev.filter((_, j) => j !== i))}
            >
              移除
            </button>
          </div>
        ))}
        <button
          type="button"
          className="btn btn-ghost text-xs"
          onClick={() =>
            setRows((prev) => [...prev, { id: `x${prev.length + 1}`, name: "", price: "" }])
          }
        >
          + 添加商品
        </button>
      </div>
      <button type="button" className="btn btn-primary" disabled={mutation.isPending} onClick={() => mutation.mutate()}>
        求最小加购组合
      </button>
      {mutation.isError && <p className="text-xs text-accent">{(mutation.error as Error).message}</p>}

      {result && (
        <div className="rise card p-4 text-sm">
          {result.ok ? (
            <>
              <p className="micro-label mb-2">刚好跨过门槛（0-1 背包）</p>
              <ul className="space-y-1">
                {chosen.map((c) => (
                  <li key={c.id} className="flex justify-between">
                    <span>{c.name || c.id}</span>
                    <span className="num">{cny(yuanToCen(c.price))}</span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 flex items-baseline justify-between border-t border-line pt-2">
                <span className="font-display font-bold">加购合计</span>
                <span className="num text-lg font-semibold text-accent">{cny(result.total_extra_cents)}</span>
              </p>
            </>
          ) : (
            <p className="text-dim">这些商品凑不到门槛。</p>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- 页面 ----------

function CalculatorInner() {
  // 支持 /calculator?tab=overseas&usd=449 从商品页外币渠道带参跳入
  const search = useSearchParams();
  const tabParam = search.get("tab");
  const usdParam = search.get("usd") ?? undefined;
  const [tab, setTab] = useState<Tab>(
    tabParam === "overseas" || tabParam === "filler" ? tabParam : "cn",
  );
  return (
    <main>
      <SiteHeader kicker="CALC" />
      <div className="tool-intro rise"><p className="eyebrow">PRICE WORKSHOP / 一笔一笔，算清楚</p><h1>优惠条件看明白，到手价格算清楚。</h1><p>按实际可用优惠核算实付与返利。预填数据为计算示例，请替换成你的购买条件。</p></div>
      <div className="rise rise-1 mb-5 flex gap-2">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`btn rounded-full px-3.5 py-1.5 text-xs ${
              tab === t.id ? "border border-ink bg-ink text-panel" : "border border-line text-dim hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <section className="rise rise-2">
        <div className="calc-wrap">
          {tab === "cn" && <CnQuote />}
          {tab === "overseas" && <OverseasQuote key={usdParam ?? "default"} initialUsd={usdParam} />}
          {tab === "filler" && <FillerCalc />}
        </div>
      </section>
    </main>
  );
}

export default function CalculatorPage() {
  return (
    <Suspense fallback={<p className="micro-label">载入计算器…</p>}>
      <CalculatorInner />
    </Suspense>
  );
}
