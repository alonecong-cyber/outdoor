import type { ChannelQuote, DealItem, VariantDeal } from "@/lib/api";

/** 无官方款号的 T + 7 位哈希仅供后端聚合，不作为商品规格展示。 */
export function officialStyleNumber(value: string | null | undefined): string {
  const text = value?.trim() ?? "";
  return !text || /^T[0-9A-F]{7}$/i.test(text) || /^[—–-]+$/.test(text) ? "" : text;
}

export function specValue(value: string | null | undefined): string {
  const text = value?.trim() ?? "";
  return !text || /^[—–-]+$/.test(text) || /^(unknown|null|none)$/i.test(text) ? "" : text;
}

export function specs(color?: string, size?: string): string[] {
  return [specValue(color), specValue(size) ? `${specValue(size)} 码` : ""].filter(Boolean);
}

export function isConfirmed(value?: string): boolean {
  return value === "confirmed";
}

export function hasPrice(value: number | null | undefined): value is number {
  return typeof value === "number" && Number.isFinite(value) && value > 0;
}

export function isVerifiedQuote(quote: ChannelQuote): boolean {
  return quote.price_status === "verified" && quote.in_stock === true && hasPrice(quote.effective_cents);
}

/** 仅在相同币种内比较，缺少新核验字段的旧接口响应不会提升为可信现价。 */
export function bestQuote(channels: ChannelQuote[], currency = "CNY"): ChannelQuote | undefined {
  return channels
    .filter((quote) => isVerifiedQuote(quote) && quote.currency === currency)
    .sort((a, b) => (a.effective_cents ?? Infinity) - (b.effective_cents ?? Infinity))[0];
}

export function externalUrl(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  try {
    const url = new URL(value);
    return url.protocol === "https:" || url.protocol === "http:" ? url.href : undefined;
  } catch {
    return undefined;
  }
}

export function summaryText(deal: { title: string; summary: string }): string {
  const text = deal.summary?.trim() ?? "";
  return text && text !== deal.title.trim() ? text : "";
}

/** 标签来自线报。评价、新低和热度未经站内核验，不作为站内推荐依据。 */
export function conditionTags(tags: string[] = []): string[] {
  return tags.filter((tag) => !/好评|评价|新低|史低|最低|低于|低价|热度|人气|推荐指数/.test(tag));
}

export function asDealItem(deal: VariantDeal): DealItem {
  return {
    ...deal,
    source: deal.source ?? "",
    source_id: String(deal.id),
    currency: deal.currency ?? "CNY",
    tags: deal.tags ?? [],
    variant: null,
  };
}

export const CATEGORIES = [
  { id: "all", label: "全部装备", terms: [] },
  { id: "shell", label: "冲锋衣", terms: ["冲锋", "硬壳", "软壳", "shell", "防水外套"] },
  { id: "down", label: "羽绒 / 棉服", terms: ["羽绒", "棉服", "棉衣", "保暖服", "down", "puffer"] },
  { id: "fleece", label: "抓绒", terms: ["抓绒", "绒衣", "fleece", "retro-x"] },
  { id: "footwear", label: "鞋靴", terms: ["鞋", "靴", "boot"] },
  { id: "other", label: "其他装备", terms: [] },
];

export function matchesCategory(text: string, category: string): boolean {
  if (category === "all") return true;
  const lower = text.toLowerCase();
  const matched = CATEGORIES.slice(1, -1).some((item) => item.terms.some((term) => lower.includes(term)));
  if (category === "other") return !matched;
  return CATEGORIES.find((item) => item.id === category)?.terms.some((term) => lower.includes(term)) ?? true;
}
