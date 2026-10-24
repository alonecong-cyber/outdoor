/** 后端 API 类型与请求封装。价格一律为整数「分」。 */

export type VariantListItem = {
  id: number;
  brand: string;
  brand_name: string;
  style_number: string;
  style_name: string;
  category: string;
  color: string;
  size: string;
  min_price_cents: number | null;
  currency: string;
  deal_count: number;
  image: string;
};

export type ChannelQuote = {
  listing_id: number;
  channel: string;
  channel_kind: string;
  currency: string;
  title: string;
  url: string;
  image: string;
  in_stock: boolean | null;
  price_cents: number | null;
  history: { ts: string; price_cents: number; in_stock: boolean }[];
};

export type VariantDeal = {
  id: number;
  title: string;
  price_cents: number;
  channel: string;
  url: string;
  image: string;
  published_at: string | null;
};

export type VariantDetail = {
  id: number;
  brand: string;
  style_number: string;
  style_name: string;
  color: string;
  size: string;
  image: string;
  channels: ChannelQuote[];
  deals: VariantDeal[];
};

export type QuoteStep = {
  promo_id: string;
  promo_name: string;
  kind: string;
  amount_before_cents: number;
  delta_cents: number;
  amount_after_cents: number;
  note: string;
};

export type QuoteResult = {
  base_price_cents: number;
  paid_now_cents: number;
  rebate_cents: number;
  effective_cents: number;
  steps: QuoteStep[];
  applied_promo_ids: string[];
};

export type OverseasResult = {
  goods_paid_usd: number;
  total_usd: number;
  goods_shipping_cny: number;
  tax_cny: number;
  tax_exempt: boolean;
  transfer_fee_cny: number;
  cashback_cny: number;
  landed_cny: number;
  warnings: string[];
  notes: string[];
};

export type FillerResult = { ok: boolean; total_extra_cents: number; item_ids: string[] };

export type Subscription = {
  id: number;
  variant_id: number;
  target_price_cents: number;
  kinds: string[];
  destination: string;
};

export type AlertEventItem = {
  id: number;
  subscription_id: number;
  variant_id: number;
  kind: string;
  payload: Record<string, unknown>;
  sent_at: string | null;
  send_error: string | null;
};

export type DealVariantInfo = {
  variant_id: number;
  brand_slug: string;
  brand_name: string;
  style_number: string;
  style_name: string;
  color: string;
  size: string;
};

export type DealItem = {
  id: number;
  source: string;
  source_id: string;
  url: string;
  title: string;
  price_cents: number;
  currency: string;
  channel: string;
  image: string;
  tags: string[];
  published_at: string | null;
  variant: DealVariantInfo | null;
};

export type IngestResult = {
  ok: boolean;
  saved: number;
  created: number;
  matched: number;
  errors: string[];
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body);
    } catch {
      /* keep status text */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  variants: (params: { brand?: string } = {}) => {
    const q = params.brand ? `?brand=${encodeURIComponent(params.brand)}` : "";
    return request<VariantListItem[]>(`/api/variants${q}`);
  },
  variant: (id: number) => request<VariantDetail>(`/api/variants/${id}`),
  quoteByListing: (listing_id: number) =>
    request<QuoteResult>("/api/pricing/quote", {
      method: "POST",
      body: JSON.stringify({ listing_id }),
    }),
  quoteByBody: (body: unknown) =>
    request<QuoteResult>("/api/pricing/quote", { method: "POST", body: JSON.stringify(body) }),
  overseas: (body: unknown) =>
    request<OverseasResult>("/api/pricing/overseas", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  filler: (body: unknown) =>
    request<FillerResult>("/api/pricing/filler", { method: "POST", body: JSON.stringify(body) }),
  subscriptions: () => request<Subscription[]>("/api/alerts/subscriptions"),
  createSubscription: (body: {
    variant_id: number;
    target_price_cents: number;
    kinds: string[];
    destination?: string;
  }) =>
    request<Subscription>("/api/alerts/subscriptions", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteSubscription: (id: number) =>
    request<void>(`/api/alerts/subscriptions/${id}`, { method: "DELETE" }),
  events: (unsent = false) =>
    request<AlertEventItem[]>(`/api/alerts/events${unsent ? "?unsent=true" : ""}`),
  resendEvent: (id: number) =>
    request<{ ok: boolean; error: string | null }>(`/api/alerts/events/${id}/send`, {
      method: "POST",
    }),
  deals: (params: { q?: string; brand?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.brand) qs.set("brand", params.brand);
    if (params.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<DealItem[]>(`/api/deals${suffix}`);
  },
  ingestDeals: (details = 5) =>
    request<IngestResult>(`/api/deals/ingest?details=${details}`, { method: "POST" }),
};
