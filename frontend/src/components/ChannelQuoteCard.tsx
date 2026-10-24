"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";

import { api, type QuoteResult } from "@/lib/api";
import { fen, money, promoName } from "@/lib/format";

/**
 * 渠道到手价：点「算到手价」→ POST /api/pricing/quote {listing_id}
 * → 展示逐项瀑布（每张券减多少）+ 实付/返利/到手分列。
 */
export function ChannelQuoteCard({
  listingId,
  channel,
  priceCents,
  currency = "CNY",
}: {
  listingId: number;
  channel: string;
  priceCents: number | null;
  currency?: string;
}) {
  const [result, setResult] = useState<QuoteResult | null>(null);
  const mutation = useMutation({
    mutationFn: () => api.quoteByListing(listingId),
    onSuccess: setResult,
  });

  return (
    <div className="mt-2">
      <button
        type="button"
        className="btn btn-ghost text-xs"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
      >
        {mutation.isPending ? "计算中…" : result ? "重新计算" : "算到手价 →"}
      </button>
      {mutation.isError && (
        <p className="mt-2 text-xs text-accent">失败：{(mutation.error as Error).message}</p>
      )}
      {result && (
        <div className="rise mt-3 rounded-sm border border-line bg-bg/60 p-3">
          <p className="micro-label mb-2">{channel} · 优惠瀑布</p>
          <ol className="space-y-1">
            <li className="flex justify-between text-sm">
              <span className="text-dim">标价</span>
              <span className="num">{money(result.base_price_cents, currency)}</span>
            </li>
            {result.steps.map((s) => (
              <li key={s.promo_id} className="flex justify-between text-sm">
                <span>
                  {promoName(s.kind)}
                  <span className="ml-1 text-xs text-dim">{s.promo_name}</span>
                </span>
                <span className="num text-moss">−{fen(s.delta_cents)}</span>
              </li>
            ))}
            {result.steps.length === 0 && (
              <li className="text-xs text-dim">无可用优惠</li>
            )}
          </ol>
          <div className="mt-3 space-y-1 border-t border-line pt-2 text-sm">
            <div className="flex justify-between">
              <span className="text-dim">当下实付</span>
              <span className="num">{money(result.paid_now_cents, currency)}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-dim">事后返利</span>
              <span className="num text-moss">−{fen(result.rebate_cents)}</span>
            </div>
            <div className="flex items-baseline justify-between">
              <span className="font-display font-bold">到手价</span>
              <span className="num text-lg font-semibold text-accent">
                {money(result.effective_cents, currency)}
              </span>
            </div>
          </div>
        </div>
      )}
      {priceCents == null && (
        <p className="micro-label mt-1">该 listing 暂无价格快照</p>
      )}
    </div>
  );
}
