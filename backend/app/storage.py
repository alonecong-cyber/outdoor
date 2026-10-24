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
from app.util import utc_now


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
            "last_seen_at": raw.collected_at or utc_now(),
        },
        channel_id=channel_id,
        external_id=raw.external_id,
    )
    if not created:
        listing.url = raw.url or listing.url
        listing.title = raw.title or listing.title
        listing.image = raw.image or listing.image
        if variant_id is not None:
            listing.variant_id = variant_id
        listing.active = True
        listing.last_seen_at = raw.collected_at or utc_now()
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
    ts: datetime | None = None,
) -> PriceSnapshot | None:
    """变化才写快照：价格或库存与最近一条相同则返回 None。"""
    last = last_snapshot(session, listing_id)
    if last is not None and last.price_cents == price_cents and last.in_stock == in_stock:
        return None
    snap = PriceSnapshot(
        listing_id=listing_id,
        ts=ts or utc_now(),
        price_cents=price_cents,
        currency=currency,
        in_stock=in_stock,
    )
    session.add(snap)
    session.flush()
    return snap


def price_history(
    session: Session, listing_id: int, *, days: int = 90
) -> list[PriceSnapshot]:
    """按时间升序的价格历史（含当前）。"""
    since = utc_now() - timedelta(days=days)
    rows = session.exec(
        select(PriceSnapshot)
        .where(PriceSnapshot.listing_id == listing_id, PriceSnapshot.ts >= since)
        .order_by(PriceSnapshot.ts.asc())  # type: ignore[union-attr]
    ).all()
    return list(rows)


def lowest_price(
    session: Session, listing_id: int, *, days: int = 90, before: datetime | None = None
) -> int | None:
    """窗口内最低价（分）。before 用于排除"本次"快照后的比较。"""
    since = (before or utc_now()) - timedelta(days=days)
    q = select(PriceSnapshot.price_cents).where(
        PriceSnapshot.listing_id == listing_id,
        PriceSnapshot.ts >= since,
    )
    if before is not None:
        q = q.where(PriceSnapshot.ts < before)
    prices = session.exec(q).all()  # type: ignore[call-overload]
    return min(prices) if prices else None
