/** 后端 API 类型与请求封装。价格一律为整数「分」；新增字段可选，兼容旧响应。 */

export type MatchStatus = "confirmed" | "needs_review";
export type ReportedPriceStatus = "reported" | "expired" | "stale";

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
  reported_min_price_cents?: number | null;
  price_basis?: "verified" | "reported" | "unknown";
  match_status?: MatchStatus;
  latest_reported_at?: string | null;
};

export type PriceTier = "budget" | "mid" | "flagship";

export type GearCategory =
  | "hardshell"
  | "rain_jacket"
  | "softshell"
  | "fleece"
  | "baselayer"
  | "down"
  | "insulated"
  | "hiking_pants"
  | "rain_pants"
  | "socks"
  | "shoes"
  | "hiking_boots"
  | "trail_running"
  | "approach"
  | "tents"
  | "poles"
  | "backpacks"
  | "daypacks"
  | "sleeping_bags"
  | "sleeping_pads"
  | "headlamps";

export type ReviewAuthority = {
  source: string;
  badge: string;
  score?: number | null;
  quote?: string;
  url?: string;
  rank?: number | null;
  rank_total?: number | null;
  badge_zh?: string;
  quote_zh?: string;
};

export type CnContent = {
  platform: string;
  kind: string;
  title: string;
  url: string;
  author?: string;
  metric_label?: string;
  metric_value?: number;
  date?: string;
  cover?: string;
  price_cny?: number | null;
  mall?: string;
  summary?: string;
};

export type CnPrice = {
  min_cny: number;
  median_cny: number;
  count: number;
  latest_date?: string;
  malls?: string[];
};

export type ExternalLink = { label: string; url: string };

export type BrandStat = {
  brand: string;
  brand_name: string;
  country: string;
  count: number;
  categories: string[];
};

export type GearSpec = {
  weight: string;
  material: string;
  waterproof_rating: string;
  breathability: string;
  fabric_density: string;
  scenarios: string[];
  key_features: string[];
};

export type PriceGuide = {
  price_cents: number;
  msrp_cny: string;
  deal_cny: string;
  overseas_usd?: string;
  overseas_landed_cny?: string;
  promo_tips?: string;
};

export type GearRankingItem = {
  id: string;
  name: string;
  name_cn: string;
  brand: string;
  brand_name: string;
  category: GearCategory;
  category_name: string;
  price_tier: PriceTier;
  price_tier_name: string;
  image: string;
  rating_score: number | null;
  price_guide: PriceGuide;
  specs: GearSpec;
  authorities: ReviewAuthority[];
  pros: string[];
  cons: string[];
  bottom_line: string;
  gap_analysis: string;
  matched_style_number?: string | null;
  gender?: "men" | "women" | "unisex";
  gender_name?: string;
  brand_country?: string;
  image_remote?: string;
  image_credit?: string;
  score_basis?: string;
  spec_table?: Record<string, string>;
  sub_scores?: Record<string, number>;
  cn_links?: ExternalLink[];
  buy_links?: ExternalLink[];
  pros_zh?: string[];
  cons_zh?: string[];
  sub_scores_zh?: Record<string, string>;
  is_cn_brand?: boolean;
  cn_price?: CnPrice | null;
  cn_query?: string;
  cn_reviews?: CnContent[];
};

export type CategoryMeta = {
  id: GearCategory;
  name: string;
  description: string;
  icon_name: string;
  total_count: number;
  tier_counts: Record<string, number>;
};

export type CompareMatrixResponse = {
  items: GearRankingItem[];
  attributes: string[];
  category?: GearCategory | null;
  category_name: string;
  gap_summary: string;
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
  history: { ts: string; price_cents: number; in_stock: boolean; raw_price_cents?: number }[];
  channel_name?: string;
  source?: string;
  checked_at?: string | null;
  price_status?: "verified" | "stale" | "unmatched";
  paid_now_cents?: number | null;
  effective_cents?: number | null;
  rebate_cents?: number | null;
  steps?: QuoteStep[];
  history_days?: number;
};

export type VariantDeal = {
  id: number;
  title: string;
  summary: string;
  price_cents: number;
  channel: string;
  url: string;
  image: string;
  published_at: string | null;
  currency?: string;
  tags?: string[];
  price_status?: ReportedPriceStatus;
  status_note?: string;
  last_checked_at?: string | null;
  expires_at?: string | null;
  source?: string;
  match_status?: MatchStatus;
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
  brand_name?: string;
  match_status?: MatchStatus;
  match_note?: string;
  reported_min_price_cents?: number | null;
  currency?: string;
  history_days?: number;
  can_subscribe?: boolean;
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

export type PlanStep = {
  promo_name: string;
  kind: string;
  amount_before_cents: number;
  delta_cents: number;
  amount_after_cents: number;
  note: string;
};

export type DealPlan = {
  deal_id: number;
  channel: string;
  url: string;
  title: string;
  published_at: string | null;
  base_price_cents: number;
  paid_now_cents: number;
  rebate_cents: number;
  effective_cents: number;
  claimed_final_cents: number | null;
  promo_count: number;
  steps: PlanStep[];
  notes: string[];
};

export type VariantPlan = {
  variant_id: number;
  basis: "reported";
  note: string;
  platforms: { channel: string; min_price_cents: number; deal_id: number; published_at: string | null; deal_count: number }[];
  best_plan: DealPlan;
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
  summary: string;
  price_cents: number;
  currency: string;
  channel: string;
  image: string;
  tags: string[];
  published_at: string | null;
  variant: DealVariantInfo | null;
  price_status?: ReportedPriceStatus;
  status_note?: string;
  last_checked_at?: string | null;
  expires_at?: string | null;
  match_status?: MatchStatus;
};

export type DealDetail = DealItem & {
  purchase_notes?: string[];
  related_deals?: DealItem[];
  channels?: ChannelQuote[];
  can_subscribe?: boolean;
  history_days?: number;
  min_price_cents?: number | null;
};

export type WatchAlertItem = {
  id: number;
  kind: string;
  price_cents: number;
  reason: string;
  deal_title: string;
  deal_url: string;
  channel: string;
  created_at: string | null;
  sent_at: string | null;
  send_error: string;
};

export type WatchItem = {
  id: number;
  name: string;
  keywords: string[];
  must_words: string[];
  exclude_words: string[];
  target_price_cents: number;
  currency: string;
  qty: number;
  platforms: string[];
  active: boolean;
  last_checked_at: string | null;
  last_result: string;
  created_at: string | null;
};

export type WatchInput = {
  name: string;
  keywords?: string[];
  must_words?: string[];
  exclude_words?: string[];
  target_price?: number; // 元；0 = 不设
  currency?: string;
  qty?: number;
  platforms?: string[];
};

export type DealNoteItem = { id: number; body: string; created_at: string };

export type SiteStatus = {
  scheduler_enabled: boolean;
  last_deal_update: string | null;
  sources: { source: string; name: string; configured: boolean; note: string }[];
  counts: { deals: number; verified_offers: number; confirmed_variants: number };
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
  variants: (params: { brand?: string; q?: string; sort?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.brand) qs.set("brand", params.brand);
    if (params.q) qs.set("q", params.q);
    if (params.sort) qs.set("sort", params.sort);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<VariantListItem[]>(`/api/variants${suffix}`);
  },
  variant: (id: number) => request<VariantDetail>(`/api/variants/${id}`),
  variantPlan: (id: number) => request<VariantPlan>(`/api/variants/${id}/plan`),
  deal: (id: number) => request<DealDetail>(`/api/deals/${id}`),
  status: () => request<SiteStatus>("/api/status"),
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
  deals: (params: { q?: string; brand?: string; channel?: string; sort?: string; limit?: number } = {}) => {
    const qs = new URLSearchParams();
    if (params.q) qs.set("q", params.q);
    if (params.brand) qs.set("brand", params.brand);
    if (params.channel) qs.set("channel", params.channel);
    if (params.sort) qs.set("sort", params.sort);
    if (params.limit) qs.set("limit", String(params.limit));
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<DealItem[]>(`/api/deals${suffix}`);
  },
  dealNotes: (id: number) => request<DealNoteItem[]>(`/api/deals/${id}/notes`),
  addDealNote: (id: number, body: string) =>
    request<DealNoteItem>(`/api/deals/${id}/notes`, { method: "POST", body: JSON.stringify({ body }) }),
  deleteDealNote: (id: number, noteId: number) =>
    request<void>(`/api/deals/${id}/notes/${noteId}`, { method: "DELETE" }),
  watches: () => request<WatchItem[]>("/api/watch"),
  createWatch: (body: WatchInput) => request<WatchItem>("/api/watch", { method: "POST", body: JSON.stringify(body) }),
  updateWatch: (id: number, body: WatchInput) =>
    request<WatchItem>(`/api/watch/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  setWatchActive: (id: number, active: boolean) =>
    request<{ ok: boolean; active: boolean }>(`/api/watch/${id}/active?active=${active}`, { method: "POST" }),
  deleteWatch: (id: number) => request<void>(`/api/watch/${id}`, { method: "DELETE" }),
  checkWatches: () => request<{ checked: number; triggered: number } & Record<string, unknown>>("/api/watch/check", { method: "POST" }),
  watchAlerts: (id: number) => request<WatchAlertItem[]>(`/api/watch/${id}/alerts`),
  ingestDeals: (details = 5) =>
    request<IngestResult>(`/api/deals/ingest?details=${details}`, { method: "POST" }),
  rankings: (params: { category?: string; tier?: string; source?: string; brand?: string; gender?: string; q?: string; sort?: string } = {}) => {
    const qs = new URLSearchParams();
    if (params.category) qs.set("category", params.category);
    if (params.tier) qs.set("tier", params.tier);
    if (params.source) qs.set("source", params.source);
    if (params.brand) qs.set("brand", params.brand);
    if (params.gender) qs.set("gender", params.gender);
    if (params.q) qs.set("q", params.q);
    if (params.sort) qs.set("sort", params.sort);
    const suffix = qs.toString() ? `?${qs.toString()}` : "";
    return request<GearRankingItem[]>(`/api/rankings${suffix}`);
  },
  rankingCategories: () => request<CategoryMeta[]>("/api/rankings/categories"),
  rankingBrands: (category?: string) =>
    request<BrandStat[]>(`/api/rankings/brands${category ? `?category=${encodeURIComponent(category)}` : ""}`),
  rankingDetail: (id: string) => request<GearRankingItem>(`/api/rankings/${id}`),
  rankingCompare: (ids: string[]) =>
    request<CompareMatrixResponse>("/api/rankings/compare", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
};
