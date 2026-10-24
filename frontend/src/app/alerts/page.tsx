"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { SiteHeader } from "@/components/SiteHeader";
import { api } from "@/lib/api";
import { alertKindName, cny } from "@/lib/format";

export default function AlertsPage() {
  const qc = useQueryClient();
  const [variantId, setVariantId] = useState("");
  const [target, setTarget] = useState("");

  const variants = useQuery({ queryKey: ["variants", ""], queryFn: () => api.variants() });
  const subs = useQuery({ queryKey: ["subscriptions"], queryFn: api.subscriptions });
  const events = useQuery({ queryKey: ["events"], queryFn: () => api.events() });

  const variantName = (id: number) => {
    const v = (variants.data ?? []).find((x) => x.id === id);
    return v ? `${v.style_name} ${v.color} ${v.size}` : `#${id}`;
  };

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteSubscription(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["subscriptions"] }),
  });
  const resend = useMutation({
    mutationFn: (id: number) => api.resendEvent(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["events"] }),
  });

  return (
    <main>
      <SiteHeader kicker="WATCH" />

      <section className="rise rise-1 card mb-4 p-4">
        <p className="micro-label">触发记录（最新 50 条）</p>
        <ul className="mt-3 space-y-2">
          {(events.data ?? []).map((e) => (
            <li key={e.id} className="rounded-sm border border-line p-3 text-sm">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p>
                    <span className={`micro-label ${e.kind === "new_low" ? "text-accent" : "text-moss"}`}>
                      {e.kind === "new_low" ? "历史新低" : "低于目标价"}
                    </span>
                  </p>
                  <p className="mt-1">
                    {variantName(e.variant_id)}
                    {typeof e.payload.price_cents === "number" && (
                      <span className="num ml-2 text-accent">{cny(e.payload.price_cents)}</span>
                    )}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  {e.sent_at ? (
                    <p className="micro-label text-moss">已发送</p>
                  ) : (
                    <button
                      type="button"
                      className="btn btn-ghost text-xs"
                      disabled={resend.isPending}
                      onClick={() => resend.mutate(e.id)}
                    >
                      立即发送
                    </button>
                  )}
                  {e.send_error && <p className="micro-label mt-1 max-w-40 text-accent">{e.send_error}</p>}
                </div>
              </div>
            </li>
          ))}
          {(events.data ?? []).length === 0 && <p className="text-sm text-dim">还没有触发记录。</p>}
        </ul>
      </section>

      <section className="rise rise-2 card p-4">
        <p className="micro-label">全部订阅</p>
        <ul className="mt-3 space-y-2">
          {(subs.data ?? []).map((s) => (
            <li
              key={s.id}
              className="flex items-center justify-between rounded-sm border border-line px-3 py-2 text-sm"
            >
              <div>
                <p>{variantName(s.variant_id)}</p>
                <p className="micro-label mt-0.5">
                  ≤ <span className="num text-ink">{cny(s.target_price_cents)}</span> ·{" "}
                  {s.kinds.map((k) => alertKindName(k)).join(" / ")}
                </p>
              </div>
              <button
                type="button"
                className="btn text-xs text-dim hover:text-accent"
                onClick={() => remove.mutate(s.id)}
              >
                删除
              </button>
            </li>
          ))}
          {(subs.data ?? []).length === 0 && (
            <li className="text-sm text-dim">暂无订阅。去商品页添加，或在下方快捷新建。</li>
          )}
        </ul>

        <form
          className="mt-4 flex flex-col gap-2 border-t border-line pt-4 sm:flex-row"
          onSubmit={(e) => {
            e.preventDefault();
            if (!variantId || !target) return;
            api
              .createSubscription({
                variant_id: Number(variantId),
                target_price_cents: Math.round(parseFloat(target) * 100),
                kinds: ["price_below"],
              })
              .then(() => {
                setTarget("");
                qc.invalidateQueries({ queryKey: ["subscriptions"] });
              })
              .catch(() => undefined);
          }}
        >
          <select
            className="field"
            value={variantId}
            onChange={(e) => setVariantId(e.target.value)}
          >
            <option value="">选择商品…</option>
            {(variants.data ?? []).map((v) => (
              <option key={v.id} value={v.id}>
                {v.style_name} {v.color} {v.size}
              </option>
            ))}
          </select>
          <input
            className="field"
            placeholder="目标价（元）"
            inputMode="decimal"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          />
          <button type="submit" className="btn btn-primary shrink-0">
            订阅
          </button>
        </form>
      </section>
    </main>
  );
}
