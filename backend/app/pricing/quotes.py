"""Listing 报价入口：按关联商品身份、渠道和有效时间筛选同源优惠。"""

from __future__ import annotations

from datetime import datetime

from pydantic import ValidationError
from sqlmodel import Session, select

from app.models import Listing, PromoRule, Style, Variant
from app.pricing.engine import AppliedResult
from app.pricing.rules import Promo, PromoKind, PromoScope
from app.pricing.solver import best_combination
from app.storage import last_snapshot
from app.util import to_naive_utc, utc_now


def _rule_to_promo(rule: PromoRule) -> Promo:
    # 无法解析的定向范围不能降级成全场券；调用方会忽略无效配置。
    scope = PromoScope.model_validate_json(rule.scope_json)
    return Promo(
        id=f"rule-{rule.id}",
        kind=PromoKind(rule.kind),
        name=rule.name,
        threshold_cents=rule.threshold_cents,
        amount_cents=rule.amount_cents,
        rate=rule.rate,
        cap_cents=rule.cap_cents,
        exclusive_group=rule.exclusive_group,
        scope=scope,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        source=rule.source,
    )


def quote_listing(
    session: Session,
    listing: Listing,
    *,
    base_price_cents: int | None = None,
    now: datetime | None = None,
) -> AppliedResult:
    """计算此挂链最低到手价，供 API、调度器和目录共同调用。

    base_price_cents 未传时使用最新快照的标价；传入时可直接报价尚未写入快照的采集价。
    无快照且未传标价会抛 ValueError。未知品牌/款式/规格不能命中对应维度的定向券。
    全部范围为 AND 关系；渠道、active、有效期筛选共用同一个 UTC 时刻。
    """
    if base_price_cents is None:
        snapshot = last_snapshot(session, listing.id) if listing.id is not None else None
        if snapshot is None:
            raise ValueError("listing 无价格快照")
        base_price_cents = snapshot.price_cents
    if base_price_cents < 0:
        raise ValueError("base_price_cents 不能为负")

    at = to_naive_utc(now or utc_now())
    variant = session.get(Variant, listing.variant_id) if listing.variant_id is not None else None
    style = session.get(Style, variant.style_id) if variant is not None else None
    context = {
        "brand_id": style.brand_id if style is not None else None,
        "style_id": style.id if style is not None else None,
        "variant_id": variant.id if variant is not None else None,
        "listing_id": listing.id,
    }
    rules = session.exec(
        select(PromoRule).where(
            PromoRule.active,  # type: ignore[arg-type]
            PromoRule.channel_id.is_(None)  # type: ignore[union-attr]
            | (PromoRule.channel_id == listing.channel_id),
        )
    ).all()
    promos: list[Promo] = []
    for rule in rules:
        try:
            promo = _rule_to_promo(rule)
        except (ValidationError, ValueError):
            continue
        if promo.applies_to(**context) and promo.is_valid_at(at):
            promos.append(promo)

    return best_combination(base_price_cents, promos, now=at)
