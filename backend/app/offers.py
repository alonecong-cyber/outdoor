"""渠道报价的可信度、到手价与历史投影，线报不伪装成已核验报价。"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.config import get_settings
from app.models import Channel, Listing, PriceSnapshot, Style, Variant
from app.pricing.quotes import quote_listing
from app.storage import last_snapshot, price_history
from app.util import utc_now

HASH_STYLE = re.compile(r"^T[0-9A-F]{7}$")


def identity_confirmed(style: Style | None, variant: Variant | None) -> bool:
    return bool(
        style
        and variant
        and style.style_number
        and not HASH_STYLE.fullmatch(style.style_number)
        and variant.color not in {"", "-"}
        and variant.size not in {"", "-"}
    )


def effective_price(snapshot: PriceSnapshot) -> int:
    return (
        snapshot.effective_cents if snapshot.effective_cents is not None else snapshot.price_cents
    )


def iso(ts: datetime | None) -> str | None:
    return ts.isoformat() + "Z" if ts else None


def listing_fresh(listing: Listing, *, now: datetime | None = None) -> bool:
    now = now or utc_now()
    return bool(
        listing.active
        and listing.last_seen_at
        and listing.last_seen_at >= now - timedelta(hours=get_settings().offer_freshness_hours)
        and listing.last_seen_at <= now + timedelta(minutes=5)
    )


def channel_quotes(session: Session, variant_id: int) -> list[dict]:
    now = utc_now()
    variant = session.get(Variant, variant_id)
    style = session.get(Style, variant.style_id) if variant else None
    confirmed = identity_confirmed(style, variant)
    rows = session.exec(
        select(Listing, Channel)
        .join(Channel, Listing.channel_id == Channel.id)
        .where(Listing.variant_id == variant_id, Listing.active, Channel.active)
    ).all()
    channels = []
    for listing, channel in rows:
        snap = last_snapshot(session, listing.id)
        history = price_history(session, listing.id, days=90)
        first = session.exec(
            select(PriceSnapshot)
            .where(PriceSnapshot.listing_id == listing.id)
            .order_by(PriceSnapshot.ts)
            .limit(1)
        ).first()
        days = max(0, (now - first.ts).days) if first else 0
        quote = quote_listing(session, listing, now=now) if snap else None
        state = (
            "unmatched"
            if not confirmed
            else ("verified" if snap and listing_fresh(listing, now=now) else "stale")
        )
        channels.append(
            {
                "listing_id": listing.id,
                "channel": channel.slug,
                "channel_name": listing.merchant or channel.name,
                "channel_kind": channel.kind,
                "currency": snap.currency if snap else channel.currency,
                "title": listing.title,
                "url": listing.url,
                "image": listing.image,
                "source": listing.source,
                "checked_at": iso(listing.last_seen_at),
                "price_status": state,
                "in_stock": snap.in_stock if snap and snap.stock_verified else None,
                "price_cents": snap.price_cents if snap else None,
                "paid_now_cents": quote.paid_now_cents if quote else None,
                "rebate_cents": quote.rebate_cents if quote else None,
                "effective_cents": quote.effective_cents if quote else None,
                "steps": [
                    step.model_dump()
                    if hasattr(step, "model_dump")
                    else {
                        "promo_id": step.promo_id,
                        "promo_name": step.promo_name,
                        "kind": step.kind,
                        "amount_before_cents": step.amount_before_cents,
                        "delta_cents": step.delta_cents,
                        "amount_after_cents": step.amount_after_cents,
                        "note": step.note,
                    }
                    for step in quote.steps
                ]
                if quote
                else [],
                "history_days": days,
                "history": [
                    {
                        "ts": iso(s.ts),
                        "price_cents": effective_price(s),
                        "raw_price_cents": s.price_cents,
                        "in_stock": s.in_stock,
                    }
                    for s in history
                ],
            }
        )
    channels.sort(
        key=lambda c: (
            c["price_status"] != "verified",
            c["in_stock"] is False,
            c["currency"],
            c["effective_cents"] if c["effective_cents"] is not None else 10**15,
        )
    )
    return channels


def current_cny_quotes(channels: list[dict]) -> list[dict]:
    """人民币同口径报价才可直接求最低价；外币价保留原币展示。"""
    return [
        c
        for c in channels
        if c["price_status"] == "verified"
        and c["in_stock"] is True
        and c["currency"] == "CNY"
        and c["effective_cents"] is not None
        and c["effective_cents"] > 0
    ]
