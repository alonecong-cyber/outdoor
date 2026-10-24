"""API 请求/响应模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: str
    version: str


# ---------- 定价 ----------

class PromoIn(BaseModel):
    id: str = ""
    kind: str
    name: str = ""
    threshold_cents: int = 0
    amount_cents: int = 0
    rate: float = 0.0
    cap_cents: int = 0
    exclusive_group: str = ""
    scope_brand_ids: list[int] = Field(default_factory=list)
    scope_style_ids: list[int] = Field(default_factory=list)
    scope_variant_ids: list[int] = Field(default_factory=list)
    scope_listing_ids: list[int] = Field(default_factory=list)
    valid_from: str | None = None
    valid_to: str | None = None


class QuoteIn(BaseModel):
    """报价请求：给 listing_id 走库，否则用 base_price_cents + promos。"""

    listing_id: int | None = None
    base_price_cents: int = 0
    promos: list[PromoIn] = Field(default_factory=list)


class StepOut(BaseModel):
    promo_id: str
    promo_name: str
    kind: str
    amount_before_cents: int
    delta_cents: int
    amount_after_cents: int
    note: str = ""


class QuoteOut(BaseModel):
    base_price_cents: int
    paid_now_cents: int
    rebate_cents: int
    effective_cents: int
    steps: list[StepOut]
    applied_promo_ids: list[str]


class OverseasIn(BaseModel):
    usd_price: float
    discount_rate: float = 0.0
    coupon_code_rate: float = 0.0
    us_shipping_usd: float = 0.0
    exchange_rate: float
    transfer_fee_cny: float = 0.0
    cashback_rate: float = 0.0


class FillerItemIn(BaseModel):
    id: str
    name: str = ""
    price_cents: int


class FillerIn(BaseModel):
    threshold_cents: int
    items: list[FillerItemIn]


class FillerOut(BaseModel):
    ok: bool
    total_extra_cents: int
    item_ids: list[str]
