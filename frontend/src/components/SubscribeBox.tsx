"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import Link from "next/link";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { alertKindName, cny } from "@/lib/format";

export function SubscribeBox({ variantId, canSubscribe, historyDays = 0 }: { variantId: number; canSubscribe: boolean; historyDays?: number }) {
  const client = useQueryClient();
  const targetId = useId();
  const [target, setTarget] = useState("");
  const [kinds, setKinds] = useState<string[]>(["price_below"]);
  const subscriptions = useQuery({ queryKey: ["subscriptions"], queryFn: api.subscriptions });
  const mine = (subscriptions.data ?? []).filter((item) => item.variant_id === variantId);
  const validTarget = /^\d+(\.\d{1,2})?$/.test(target.trim()) && Number(target) > 0 && Number.isSafeInteger(Math.round(Number(target) * 100));
  const create = useMutation({
    mutationFn: () => api.createSubscription({ variant_id: variantId, target_price_cents: Math.round(Number(target) * 100), kinds }),
    onSuccess: () => { setTarget(""); void client.invalidateQueries({ queryKey: ["subscriptions"] }); },
  });
  const remove = useMutation({ mutationFn: api.deleteSubscription, onSuccess: () => client.invalidateQueries({ queryKey: ["subscriptions"] }) });
  return <section className="subscribe-box" id="price-alert"><h2><Icon name="bell" />等一个合适的价格</h2>
    {canSubscribe ? <><p>关注这个颜色、尺码的人民币到手价。返利事后到账，与当下实付分开核算。</p><form onSubmit={(e) => { e.preventDefault(); if (validTarget && kinds.length > 0 && !create.isPending) create.mutate(); }}><div className="subscribe-kinds" role="group" aria-label="选择提醒类型">{[{ id: "price_below", label: "低于目标价" }, { id: "new_low", label: "历史新低" }].map((kind) => <button key={kind.id} type="button" disabled={kind.id === "new_low" && historyDays < 14} aria-pressed={kinds.includes(kind.id)} onClick={() => setKinds((old) => old.includes(kind.id) ? old.filter((item) => item !== kind.id) : [...old, kind.id])}>{kind.label}</button>)}</div>{historyDays < 14 && <p className="mb-3">历史样本不足 14 天，暂不判断历史新低。</p>}<label htmlFor={targetId}>目标到手价（人民币元）</label><div className="subscribe-row"><input id={targetId} className="field" inputMode="decimal" placeholder="例如 800.00" value={target} onChange={(e) => setTarget(e.target.value)} required /><button type="submit" className="btn-primary shrink-0" disabled={!validTarget || !kinds.length || create.isPending}>{create.isPending ? "保存中…" : "创建提醒"}</button></div>{target && !validTarget && <p className="error-text">请输入大于 0 的金额，最多两位小数。</p>}{create.isError && <p className="error-text">创建失败：{create.error.message}</p>}{create.isSuccess && <p className="success-text" role="status">提醒已保存，可在降价提醒页管理。</p>}</form></> : <><p>这条装备的规格或当前报价仍待核验。补齐颜色、尺码和可信报价后，才能关注精确降价。</p><button type="button" className="btn btn-ghost mt-4 w-full" disabled>暂不可创建精确降价提醒</button></>}
    {mine.length > 0 && <ul className="sub-list">{mine.map((item) => <li key={item.id}><span>{cny(item.target_price_cents)} · {item.kinds.map(alertKindName).join(" / ")}</span><button type="button" disabled={remove.isPending} onClick={() => remove.mutate(item.id)} aria-label={`删除 ${cny(item.target_price_cents)} 的提醒`}>删除</button></li>)}</ul>}
    {remove.isError && <p className="error-text">删除失败：{remove.error.message}</p>}<Link href="/alerts" className="text-link mt-4">管理我的提醒<Icon name="arrow" /></Link>
  </section>;
}
