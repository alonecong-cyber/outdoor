"""优惠规则的统一表达：类型、门槛、面额/比例、上限、作用范围、互斥组、计算顺序。"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.util import to_naive_utc, utc_now


class PromoKind(StrEnum):
    """优惠类型。APPLY_ORDER 定义了计算顺序（先券前减、后立减、返利最后）。"""

    DIRECT_DISCOUNT = "direct_discount"  # 直降
    MEMBER_PRICE = "member_price"  # 会员价（一口价）
    STORE_COUPON = "store_coupon"  # 店铺券
    STORE_FULL_REDUCE = "store_full_reduce"  # 店铺满减
    CROSS_STORE_FULL_REDUCE = "cross_store_full_reduce"  # 跨店满减
    PLATFORM_COUPON = "platform_coupon"  # 平台券
    RED_PACKET = "red_packet"  # 红包
    PAYMENT_DISCOUNT = "payment_discount"  # 支付立减
    REBATE = "rebate"  # 返利（国内，事后到账）
    CASHBACK = "cashback"  # 返现（海淘，事后到账）


# 计算顺序：直降/会员价 → 店铺券 → 店铺满减 → 跨店满减 → 平台券/红包 → 支付立减 → 返利
APPLY_ORDER: list[PromoKind] = [
    PromoKind.DIRECT_DISCOUNT,
    PromoKind.MEMBER_PRICE,
    PromoKind.STORE_COUPON,
    PromoKind.STORE_FULL_REDUCE,
    PromoKind.CROSS_STORE_FULL_REDUCE,
    PromoKind.PLATFORM_COUPON,
    PromoKind.RED_PACKET,
    PromoKind.PAYMENT_DISCOUNT,
    PromoKind.REBATE,
    PromoKind.CASHBACK,
]

_KIND_INDEX = {kind: i for i, kind in enumerate(APPLY_ORDER)}


class PromoScope(BaseModel):
    """优惠作用范围：空 = 全部适用。字段间是 AND 关系。"""

    brand_ids: list[int] = Field(default_factory=list)
    style_ids: list[int] = Field(default_factory=list)
    variant_ids: list[int] = Field(default_factory=list)
    listing_ids: list[int] = Field(default_factory=list)


class Promo(BaseModel):
    """一条可计算的优惠（采集的券 / 人工录入的满减都会转成它）。"""

    id: str
    kind: PromoKind
    name: str = ""
    threshold_cents: int = 0  # 订单金额（分）≥ 门槛才生效；0 = 无门槛
    amount_cents: int = 0  # 固定减免/一口价（分）
    rate: float = 0.0  # 比例减免（0-1），与 amount 二选一，amount 优先
    cap_cents: int = 0  # 单条规则最多减（分）；0 = 不限
    exclusive_group: str = ""  # 同组互斥；空 = 不互斥
    scope: PromoScope = Field(default_factory=PromoScope)
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    source: str = ""

    def is_valid_at(self, at: datetime | None = None) -> bool:
        """有效起止时刻均包含边界；无时区值按存储约定视为 UTC。"""
        at = to_naive_utc(at or utc_now())
        if self.valid_from and at < to_naive_utc(self.valid_from):
            return False
        if self.valid_to and at > to_naive_utc(self.valid_to):
            return False
        return True

    def applies_to(
        self,
        *,
        brand_id: int | None = None,
        style_id: int | None = None,
        variant_id: int | None = None,
        listing_id: int | None = None,
    ) -> bool:
        """作用范围命中判断：给出的维度必须全部命中（未约束的维度视为命中）。"""
        s = self.scope
        if s.brand_ids and brand_id not in s.brand_ids:
            return False
        if s.style_ids and style_id not in s.style_ids:
            return False
        if s.variant_ids and variant_id not in s.variant_ids:
            return False
        if s.listing_ids and listing_id not in s.listing_ids:
            return False
        return True

    def sort_key(self) -> int:
        return _KIND_INDEX.get(self.kind, len(APPLY_ORDER))


def sort_promos(promos: list[Promo]) -> list[Promo]:
    """按计算顺序排列；同类型内按面额从大到小（先用大券）。"""
    return sorted(promos, key=lambda p: (p.sort_key(), -p.amount_cents))
