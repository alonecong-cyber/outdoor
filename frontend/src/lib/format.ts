/** 展示格式化：分 → 人民币 / 美元文本。 */

export function fen(cents: number | null | undefined): string {
  if (cents == null) return "—";
  return (cents / 100).toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function cny(cents: number | null | undefined): string {
  return cents == null ? "—" : `¥${fen(cents)}`;
}

export function delta(cents: number): string {
  const sign = cents <= 0 ? "" : "+";
  return `${sign}${fen(cents)}`;
}

export function usd(v: number): string {
  return `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** 按币种渲染价格（分）。跨币种不可直接比大小，但符号必须对。 */
export function money(cents: number | null | undefined, currency = "CNY"): string {
  if (cents == null) return "—";
  if (currency === "USD") return `$${fen(cents)}`;
  if (currency === "CNY") return `¥${fen(cents)}`;
  return `${currency} ${fen(cents)}`;
}

export const CHANNEL_NAMES: Record<string, string> = {
  jd: "京东",
  taobao: "淘宝",
  avantlink: "AvantLink 海外",
  "official-us": "美国官网",
  "official-cn": "中国官网",
};

export function channelName(slug: string): string {
  return CHANNEL_NAMES[slug] ?? slug;
}

export const PROMO_KIND_NAMES: Record<string, string> = {
  direct_discount: "直降",
  member_price: "会员价",
  store_coupon: "店铺券",
  store_full_reduce: "店铺满减",
  cross_store_full_reduce: "跨店满减",
  platform_coupon: "平台券",
  red_packet: "红包",
  payment_discount: "支付立减",
  rebate: "返利",
  cashback: "返现",
};

export function promoName(kind: string): string {
  return PROMO_KIND_NAMES[kind] ?? kind;
}

export const ALERT_KIND_NAMES: Record<string, string> = {
  price_below: "低于目标价",
  new_low: "历史新低",
};

export function alertKindName(kind: string): string {
  return ALERT_KIND_NAMES[kind] ?? kind;
}
