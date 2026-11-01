import type { VariantPlan } from "@/lib/api";
import { money, promoName } from "@/lib/format";

const KIND_LABEL: Record<string, string> = {
  store_coupon: "店铺券",
  platform_coupon: "平台券",
  direct_discount: "直接折扣",
  payment_discount: "支付立减",
  rebate: "返利",
  red_packet: "红包",
};

export function PlanPanel({ plan }: { plan: VariantPlan }) {
  const best = plan.best_plan;
  const lowestPlatform = plan.platforms.length ? Math.min(...plan.platforms.map((p) => p.min_price_cents)) : null;
  const platforms = [...plan.platforms].sort((a, b) => a.min_price_cents - b.min_price_cents);
  return (
    <div className="space-y-4">
      <p className="notice"><strong>参考口径</strong><br />{plan.note}</p>
      {plan.platforms.length > 1 && (
        <div className="quote-list" aria-label="各平台参考现价">
          {platforms.map((platform) => {
            const isLowest = platform.min_price_cents === lowestPlatform;
            const width = lowestPlatform ? Math.round((lowestPlatform / platform.min_price_cents) * 100) : 0;
            return (
              <article className={`quote-card ${isLowest ? "is-best" : ""}`} key={platform.channel}>
                <div className="quote-head">
                  <div>
                    <h3>{platform.channel}<span className="badge badge-reported">线报参考</span>{isLowest && <span className="badge badge-best">参考最低</span>}</h3>
                    <p className="quote-subtitle">{platform.deal_count} 条线报 · 非当前可买价</p>
                  </div>
                  <div className="text-right">
                    <span className="quote-main-price">{money(platform.min_price_cents, "CNY")}</span>
                    {!isLowest && lowestPlatform != null && <span className="quote-delta mt-1 block">较最低 +{money(platform.min_price_cents - lowestPlatform, "CNY")}</span>}
                  </div>
                </div>
                <div className="quote-bar" aria-hidden="true"><span className={isLowest ? "is-lowest" : ""} style={{ width: `${width}%` }} /></div>
              </article>
            );
          })}
        </div>
      )}
      <article className="quote-card is-best">
        <div className="quote-head">
          <div>
            <h3>最优参考方案 · {best.channel}<span className="badge badge-reported">摘要估算</span></h3>
            <p className="quote-subtitle">{best.title}</p>
          </div>
          <div className="text-right">
            <span className="quote-main-price">{money(best.effective_cents, "CNY")}</span>
            <span className="mt-1 block text-[11px] text-moss">估算到手价</span>
          </div>
        </div>
        <div className="quote-breakdown">
          <div>标注原价<strong>{money(best.base_price_cents, "CNY")}</strong></div>
          <div>估算实付<strong>{money(best.paid_now_cents, "CNY")}</strong></div>
          {best.rebate_cents > 0 && <div>事后返利<strong>−{money(best.rebate_cents, "CNY")}</strong></div>}
          {best.claimed_final_cents != null && <div>线报标注到手<strong>{money(best.claimed_final_cents, "CNY")}</strong></div>}
        </div>
        {best.steps.length > 0 && (
          <details className="quote-steps" open>
            <summary>优惠叠加步骤（{best.promo_count} 条规则）</summary>
            <ol>
              {best.steps.map((step, index) => (
                <li key={`${step.promo_name}-${index}`}>
                  <span>{step.promo_name || promoName(step.kind)} · {money(step.amount_before_cents, "CNY")} → {money(step.amount_after_cents, "CNY")}</span>
                  <p>{KIND_LABEL[step.kind] ? `〔${KIND_LABEL[step.kind]}〕` : ""}{step.note}</p>
                </li>
              ))}
            </ol>
          </details>
        )}
        {best.notes.length > 0 && <ul className="mt-3 space-y-1 text-[11px] text-dim">{best.notes.map((note) => <li key={note}>· {note}</li>)}</ul>}
        {best.url && <a href={best.url} target="_blank" rel="noopener noreferrer" className="text-link mt-4">查看来源线报核对优惠条件</a>}
      </article>
    </div>
  );
}
