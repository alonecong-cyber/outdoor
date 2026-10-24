"""存储层：RawListing → Listing/PriceSnapshot 落库，变化才写快照（PRD §6）。

- Listing 按 (channel_id, external_id) 幂等 upsert；
- 快照写入前对比最近一条，价格或库存无变化就跳过（省库、历史图干净）；
- 价格全程整数分；时间 naive UTC。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import (
    Brand,
    Channel,
    Listing,
    PriceSnapshot,
    Style,
    Variant,
)
from app.util import to_naive_utc, utc_now


def get_or_create(session: Session, model, defaults: dict | None = None, /, **kwargs):
    """通用 get_or_create。返回 (obj, created)。"""
    obj = session.exec(select(model).filter_by(**kwargs)).first()
    if obj is not None:
        return obj, False
    data = {**kwargs, **(defaults or {})}
    obj = model(**data)  # type: ignore[call-arg]
    session.add(obj)
    session.flush()
    return obj, True


def get_or_create_brand(
    session: Session, slug: str, name: str, *, name_cn: str = "", aliases: list[str] | None = None
) -> Brand:
    obj, _ = get_or_create(
        session,
        Brand,
        {
            "name": name,
            "name_cn": name_cn,
            "aliases_json": json.dumps(aliases or [], ensure_ascii=False),
        },
        slug=slug,
    )
    return obj


def get_or_create_channel(
    session: Session,
    slug: str,
    *,
    kind: str,
    name: str = "",
    currency: str = "CNY",
    country: str = "CN",
) -> Channel:
    obj, _ = get_or_create(
        session,
        Channel,
        {"name": name or slug, "kind": kind, "currency": currency, "country": country},
        slug=slug,
    )
    return obj


def get_or_create_style(
    session: Session,
    brand_id: int,
    style_number: str,
    *,
    name: str = "",
    category: str = "",
    gender: str = "",
) -> Style:
    obj, _ = get_or_create(
        session,
        Style,
        {"name": name, "category": category, "gender": gender},
        brand_id=brand_id,
        style_number=style_number,
    )
    return obj


def get_or_create_variant(session: Session, style_id: int, color: str, size: str) -> Variant:
    obj, _ = get_or_create(session, Variant, {}, style_id=style_id, color=color, size=size)
    return obj


def save_raw_listing(
    session: Session,
    *,
    raw,
    channel_id: int,
    variant_id: int | None,
) -> tuple[Listing, bool]:
    """RawListing → Listing upsert。返回 (listing, created)。"""
    listing, created = get_or_create(
        session,
        Listing,
        {
            "url": raw.url,
            "title": raw.title,
            "image": raw.image,
            "variant_id": variant_id,
            "active": True,
            "last_seen_at": to_naive_utc(raw.collected_at) if raw.collected_at else utc_now(),
        },
        channel_id=channel_id,
        external_id=raw.external_id,
    )
    if not created:
        listing.url = raw.url or listing.url
        listing.title = raw.title or listing.title
        listing.image = raw.image or listing.image
        listing.variant_id = variant_id
        listing.active = True
        listing.last_seen_at = to_naive_utc(raw.collected_at) if raw.collected_at else utc_now()
    listing.source = raw.source
    listing.merchant = raw.merchant
    listing.stock_verified = raw.stock_verified
    session.add(listing)
    session.flush()
    return listing, created


def last_snapshot(session: Session, listing_id: int) -> PriceSnapshot | None:
    return session.exec(
        select(PriceSnapshot)
        .where(PriceSnapshot.listing_id == listing_id)
        .order_by(PriceSnapshot.ts.desc())  # type: ignore[union-attr]
        .limit(1)
    ).first()


def add_price_snapshot(
    session: Session,
    *,
    listing_id: int,
    price_cents: int,
    currency: str = "CNY",
    in_stock: bool = True,
    stock_verified: bool = True,
    ts: datetime | None = None,
    paid_now_cents: int | None = None,
    rebate_cents: int = 0,
    effective_cents: int | None = None,
) -> PriceSnapshot | None:
    """标价、实付、返利、到手价、币种或库存变化时才写入。"""
    paid = price_cents if paid_now_cents is None else paid_now_cents
    effective = paid - rebate_cents if effective_cents is None else effective_cents
    last = last_snapshot(session, listing_id)
    if last is not None and (
        last.price_cents == price_cents
        and last.in_stock == in_stock
        and last.stock_verified == stock_verified
        and last.currency == currency
        and last.rebate_cents == rebate_cents
        and (last.paid_now_cents if last.paid_now_cents is not None else last.price_cents) == paid
        and (last.effective_cents if last.effective_cents is not None else last.price_cents)
        == effective
    ):
        return None
    snap = PriceSnapshot(
        listing_id=listing_id,
        ts=ts or utc_now(),
        price_cents=price_cents,
        currency=currency,
        in_stock=in_stock,
        stock_verified=stock_verified,
        paid_now_cents=paid,
        rebate_cents=rebate_cents,
        effective_cents=effective,
    )
    session.add(snap)
    session.flush()
    return snap


def price_history(session: Session, listing_id: int, *, days: int = 90) -> list[PriceSnapshot]:
    """按时间升序的价格历史（含当前）。"""
    return history_window(session, listing_id, days=days)


def history_window(
    session: Session,
    listing_id: int,
    *,
    days: int = 90,
    now: datetime | None = None,
    before: datetime | None = None,
) -> list[PriceSnapshot]:
    """窗口内记录加起点前最后一条；保留原始时间，不伪造观测快照。"""
    end = now or utc_now()
    since = end - timedelta(days=days)
    stmt = select(PriceSnapshot).where(PriceSnapshot.listing_id == listing_id)
    stmt = stmt.where(PriceSnapshot.ts < before) if before else stmt.where(PriceSnapshot.ts <= end)
    previous = session.exec(
        stmt.where(PriceSnapshot.ts < since).order_by(PriceSnapshot.ts.desc()).limit(1)
    ).first()
    rows = session.exec(
        stmt.where(PriceSnapshot.ts >= since).order_by(PriceSnapshot.ts.asc())
    ).all()
    return ([previous] if previous else []) + list(rows)


def lowest_price(
    session: Session, listing_id: int, *, days: int = 90, before: datetime | None = None
) -> int | None:
    """窗口内最低价（分）。before 用于排除"本次"快照后的比较。"""
    rows = history_window(session, listing_id, days=days, now=before, before=before)
    prices = [
        s.effective_cents if s.effective_cents is not None else s.price_cents
        for s in rows
        if s.in_stock and s.stock_verified
    ]
    return min(prices) if prices else None


def sync_listing_coupons(session: Session, listing: Listing, coupons: list) -> None:
    """采集券只限本SKU，同一轮店铺券互斥；消失的券停用，不影响人工规则。"""
    from app.models import PromoRule
    from app.util import dump_json

    source = f"api:listing:{listing.id}"
    existing = session.exec(select(PromoRule).where(PromoRule.source == source)).all()
    for rule in existing:
        rule.active = False
        session.add(rule)
    for index, coupon in enumerate(coupons):
        if coupon.amount_cents <= 0:
            continue
        rule = (
            existing[index]
            if index < len(existing)
            else PromoRule(
                name="", kind="store_coupon", channel_id=listing.channel_id, source=source
            )
        )
        rule.name = coupon.name or f"商品专属券减{coupon.amount_cents / 100:g}元"
        rule.kind = "store_coupon"
        rule.channel_id = listing.channel_id
        rule.threshold_cents = coupon.threshold_cents
        rule.amount_cents = coupon.amount_cents
        rule.scope_json = dump_json({"listing_ids": [listing.id]})
        rule.exclusive_group = f"listing:{listing.id}:store_coupon"
        rule.valid_from = coupon.start_time
        rule.valid_to = coupon.end_time
        rule.active = True
        session.add(rule)
    session.flush()
