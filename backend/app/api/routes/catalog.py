"""商品目录：严格同规格的渠道现价、参考线报与到手价历史。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session, select

from app.api.deps import get_db
from app.api.routes.deals import _to_out
from app.config import get_settings
from app.deals import variant_context
from app.models import Brand, Channel, Deal, Listing, Style, Variant
from app.offers import (
    channel_quotes,
    current_cny_quotes,
    effective_price,
    identity_confirmed,
    iso,
    listing_fresh,
)
from app.storage import last_snapshot, price_history

router = APIRouter(tags=["catalog"])


def _reported(deals: list[Deal]) -> tuple[int | None, str]:
    priced = [d for d in deals if d.price_cents > 0]
    currency = (
        "CNY"
        if any(d.currency == "CNY" for d in priced)
        else (priced[0].currency if priced else "CNY")
    )
    # 不同币种不进行数值最低价比较。
    return min((d.price_cents for d in priced if d.currency == currency), default=None), currency


@router.get("/variants")
def list_variants(brand: str = "", q: str = "", db: Session = Depends(get_db)) -> list[dict]:
    from sqlalchemy import or_

    stmt = (
        select(Variant, Style, Brand)
        .join(Style, Variant.style_id == Style.id)
        .join(Brand, Style.brand_id == Brand.id)
    )
    if brand:
        stmt = stmt.where(Brand.slug == brand)
    if q.strip():
        like = f"%{q.strip()}%"
        stmt = stmt.where(
            or_(
                Style.name.ilike(like),
                Style.style_number.ilike(like),
                Style.category.ilike(like),
                Variant.color.ilike(like),
                Variant.size.ilike(like),
                Brand.name.ilike(like),
                Brand.name_cn.ilike(like),
            )
        )
    out = []
    for variant, style, brand_obj in db.exec(stmt).all():
        deals = list(
            db.exec(
                select(Deal)
                .where(Deal.matched_variant_id == variant.id)
                .order_by(Deal.created_at.desc())
            ).all()
        )
        channels = channel_quotes(db, variant.id)
        current = current_cny_quotes(channels)
        reported_min, report_currency = _reported(deals)
        current_min = min((c["effective_cents"] for c in current), default=None)
        confirmed = identity_confirmed(style, variant)
        out.append(
            {
                "id": variant.id,
                "brand": brand_obj.slug,
                "brand_name": brand_obj.name_cn or brand_obj.name,
                "style_number": style.style_number,
                "style_name": style.name,
                "category": style.category,
                "color": variant.color,
                "size": variant.size,
                "min_price_cents": current_min,
                "reported_min_price_cents": reported_min,
                "currency": "CNY" if current else report_currency,
                "reported_currency": report_currency,
                "price_basis": "verified" if current else "reported" if deals else "unknown",
                "match_status": "confirmed" if confirmed else "needs_review",
                "deal_count": len(deals),
                "verified_offer_count": len(current),
                "latest_reported_at": iso(deals[0].published_at or deals[0].created_at)
                if deals
                else None,
                "image": next((c["image"] for c in channels if c["image"]), "")
                or next((d.image for d in deals if d.image), ""),
            }
        )
    return out


@router.get("/variants/{variant_id}")
def variant_detail(variant_id: int, db: Session = Depends(get_db)) -> dict:
    variant = db.get(Variant, variant_id)
    if variant is None:
        raise HTTPException(404, "商品规格不存在")
    style = db.get(Style, variant.style_id)
    brand = db.get(Brand, style.brand_id) if style else None
    confirmed = identity_confirmed(style, variant)
    channels = channel_quotes(db, variant_id)
    current = current_cny_quotes(channels)
    deal_rows = list(
        db.exec(
            select(Deal)
            .where(Deal.matched_variant_id == variant_id)
            .order_by(Deal.created_at.desc())
            .limit(40)
        ).all()
    )
    ctx = variant_context(db, {variant_id})
    deals = [_to_out(deal, ctx).model_dump() for deal in deal_rows]
    reported_min, report_currency = _reported(deal_rows)
    return {
        "id": variant.id,
        "brand": brand.slug if brand else "",
        "brand_name": (brand.name_cn or brand.name) if brand else "",
        "style_number": style.style_number if style else "",
        "style_name": style.name if style else "",
        "color": variant.color,
        "size": variant.size,
        "image": next((c["image"] for c in channels if c["image"]), "")
        or next((d["image"] for d in deals if d["image"]), ""),
        "match_status": "confirmed" if confirmed else "needs_review",
        "match_note": "已确认款号、颜色与尺码"
        if confirmed
        else "完整规格尚未确认，不与其他颜色或尺码合并比价",
        "channels": channels,
        "deals": deals,
        "reported_min_price_cents": reported_min,
        "currency": "CNY" if current else report_currency,
        "history_days": max((c["history_days"] for c in channels), default=0),
        "can_subscribe": bool(confirmed and current),
        "min_price_cents": min((c["effective_cents"] for c in current), default=None),
    }


@router.get("/variants/{variant_id}/plan")
def variant_plan(variant_id: int, db: Session = Depends(get_db)) -> dict:
    """各平台参考现价 + 最优优惠叠加方案（由线报摘要估算）。"""
    if db.get(Variant, variant_id) is None:
        raise HTTPException(404, "商品规格不存在")
    from app.pricing.plan import build_variant_plan

    plan = build_variant_plan(db, variant_id)
    if plan is None:
        raise HTTPException(404, "该规格暂无带价格的线报")
    return plan


@router.get("/listings/{listing_id}/history")
def listing_history(
    listing_id: int,
    days: int = Query(default=90, ge=1, le=3650),
    db: Session = Depends(get_db),
) -> list[dict]:
    if db.get(Listing, listing_id) is None:
        raise HTTPException(404, "渠道商品不存在")
    return [
        {
            "ts": iso(s.ts),
            "price_cents": effective_price(s),
            "raw_price_cents": s.price_cents,
            "currency": s.currency,
            "in_stock": s.in_stock,
        }
        for s in price_history(db, listing_id, days=days)
    ]


@router.get("/status")
def site_status(request: Request, db: Session = Depends(get_db)) -> dict:
    settings = get_settings()
    scheduler = getattr(request.app.state, "scheduler", None)
    running = bool(scheduler and scheduler.running)
    deals = db.exec(select(Deal)).all()
    listings = db.exec(select(Listing).where(Listing.active)).all()
    confirmed = 0
    variants = db.exec(select(Variant, Style).join(Style, Variant.style_id == Style.id)).all()
    confirmed_ids = {v.id for v, s in variants if identity_confirmed(s, v)}
    confirmed = len(confirmed_ids)
    verified = 0
    for listing in listings:
        snap = last_snapshot(db, listing.id)
        channel = db.get(Channel, listing.channel_id)
        if (
            listing.variant_id in confirmed_ids
            and listing_fresh(listing)
            and snap
            and snap.in_stock
            and snap.currency == "CNY"
            and channel
            and channel.active
        ):
            verified += 1
    last_deal = max((d.last_checked_at for d in deals if d.last_checked_at), default=None)
    last_offer = max((item.last_seen_at for item in listings if item.last_seen_at), default=None)
    sources = [
        {
            "source": "smzdm",
            "name": "什么值得买",
            "configured": True,
            "note": "定期更新户外优惠线报，发布价格作为参考"
            if running
            else "户外优惠线报，支持手动更新",
        }
    ]
    for source, name, configured in [
        ("jd_union", "京东联盟", bool(settings.jd_union_app_key and settings.jd_union_secret_key)),
        (
            "tbk",
            "淘宝联盟",
            bool(settings.taobao_app_key and settings.taobao_app_secret and settings.taobao_pid),
        ),
        (
            "avantlink",
            "AvantLink 海外渠道",
            bool(settings.avantlink_affiliate_id and settings.avantlink_website_id),
        ),
    ]:
        sources.append(
            {
                "source": source,
                "name": name,
                "configured": configured,
                "note": "已配置采集凭据" if configured else "尚未配置，暂无直接报价",
            }
        )
    return {
        "scheduler_enabled": running,
        "last_deal_update": iso(last_deal),
        "last_offer_update": iso(last_offer),
        "sources": sources,
        "notifications_enabled": settings.notifications_enabled,
        "notification_configured": bool(
            (settings.telegram_bot_token and settings.telegram_chat_id)
            or settings.wecom_webhook
            or (settings.smtp_host and settings.smtp_to)
        ),
        "counts": {
            "deals": len(deals),
            "verified_offers": verified,
            "confirmed_variants": confirmed,
        },
    }
