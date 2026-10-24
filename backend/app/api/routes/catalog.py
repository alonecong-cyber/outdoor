"""商品目录：Variant 查询、listing 与价格历史。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db
from app.models import Brand, Channel, Listing, Style, Variant
from app.storage import last_snapshot, price_history

router = APIRouter(tags=["catalog"])


@router.get("/variants")
def list_variants(
    brand: str = "",
    q: str = "",
    db: Session = Depends(get_db),
) -> list[dict]:
    """列 Variant（可按 brand slug / 关键词过滤），带品牌与款式信息。"""
    stmt = select(Variant, Style, Brand).join(Style, Variant.style_id == Style.id).join(
        Brand, Style.brand_id == Brand.id
    )
    if brand:
        stmt = stmt.where(Brand.slug == brand)
    rows = db.exec(stmt).all()  # type: ignore[call-overload]
    out = []
    for variant, style, brand_obj in rows:
        if q and q.lower() not in f"{style.name} {style.style_number} {variant.color}".lower():
            continue
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
            }
        )
    return out


@router.get("/variants/{variant_id}")
def variant_detail(variant_id: int, db: Session = Depends(get_db)) -> dict:
    """Variant 详情 + 各渠道当前价 + 90 天历史（按 listing）。"""
    variant = db.get(Variant, variant_id)
    if variant is None:
        raise HTTPException(404, "variant 不存在")
    style = db.get(Style, variant.style_id)
    brand = db.get(Brand, style.brand_id) if style else None

    listings = db.exec(
        select(Listing, Channel).join(Channel, Listing.channel_id == Channel.id).where(
            Listing.variant_id == variant_id, Listing.active
        )
    ).all()  # type: ignore[call-overload]

    channels = []
    for listing, channel in listings:
        snap = last_snapshot(db, listing.id)
        history = price_history(db, listing.id, days=90)
        channels.append(
            {
                "listing_id": listing.id,
                "channel": channel.slug,
                "channel_kind": channel.kind,
                "currency": channel.currency,
                "title": listing.title,
                "url": listing.url,
                "image": listing.image,
                "in_stock": snap.in_stock if snap else None,
                "price_cents": snap.price_cents if snap else None,
                "history": [
                    {"ts": s.ts.isoformat(), "price_cents": s.price_cents, "in_stock": s.in_stock}
                    for s in history
                ],
            }
        )
    return {
        "id": variant.id,
        "brand": brand.slug if brand else "",
        "style_number": style.style_number if style else "",
        "style_name": style.name if style else "",
        "color": variant.color,
        "size": variant.size,
        "channels": channels,
    }


@router.get("/listings/{listing_id}/history")
def listing_history(
    listing_id: int, days: int = 90, db: Session = Depends(get_db)
) -> list[dict]:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(404, "listing 不存在")
    return [
        {"ts": s.ts.isoformat(), "price_cents": s.price_cents, "in_stock": s.in_stock}
        for s in price_history(db, listing_id, days=days)
    ]
