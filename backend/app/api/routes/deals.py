"""线报列表与站内详情；发布价格只作参考，单独展示已核验渠道报价。"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import get_db
from app.api.schemas import DealOut, DealVariantOut, IngestOut
from app.deals import ingest_deals, known_source_ids, max_source_id, variant_context
from app.models import Brand, Deal, Style, Variant
from app.offers import HASH_STYLE, channel_quotes, current_cny_quotes, iso
from app.util import load_json, utc_now

router = APIRouter(prefix="/deals", tags=["deals"])


def _to_out(deal: Deal, ctx: dict[int, dict]) -> DealOut:
    v = ctx.get(deal.matched_variant_id or -1)
    now = utc_now()
    expired = deal.expired or bool(deal.expires_at and deal.expires_at <= now)
    old = (deal.published_at or deal.created_at) < now - timedelta(days=14)
    state = "expired" if expired else "stale" if old else "reported"
    confirmed = bool(
        v
        and not HASH_STYLE.fullmatch(v["style_number"])
        and v["color"] not in {"", "-"}
        and v["size"] not in {"", "-"}
    )
    note = {
        "reported": "线报发布价格，尚未核验当前库存与优惠条件",
        "expired": "这条优惠已失效，价格仅供历史参考",
        "stale": "较早发布的优惠，当前价格与购买条件待复核",
    }[state]
    return DealOut(
        id=deal.id,
        source=deal.source,
        source_id=deal.source_id,
        url=deal.url,
        title=deal.title,
        summary=deal.summary,
        price_cents=deal.price_cents,
        currency=deal.currency,
        channel=deal.channel,
        image=deal.image,
        tags=load_json(deal.tags_json, []),
        published_at=iso(deal.published_at),
        variant=DealVariantOut(**v) if v else None,
        price_status=state,
        status_note=note,
        last_checked_at=iso(deal.last_checked_at),
        expires_at=iso(deal.expires_at),
        match_status="confirmed" if confirmed else "needs_review",
    )


@router.get("", response_model=list[DealOut])
def get_deals(
    q: str = "",
    brand: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DealOut]:
    stmt = select(Deal)
    if q:
        stmt = stmt.where(Deal.title.icontains(q, autoescape=True))
    if brand:
        stmt = (
            stmt.join(Variant, Deal.matched_variant_id == Variant.id)
            .join(Style, Variant.style_id == Style.id)
            .join(Brand, Style.brand_id == Brand.id)
            .where(Brand.slug == brand)
        )
    key = func.coalesce(Deal.published_at, Deal.created_at)
    deals = db.exec(stmt.order_by(key.desc(), Deal.id.desc()).offset(offset).limit(limit)).all()
    ctx = variant_context(db, {d.matched_variant_id for d in deals if d.matched_variant_id})
    return [_to_out(d, ctx) for d in deals]


@router.post("/ingest", response_model=IngestOut)
def ingest(
    request: Request,
    details: int = Query(default=10, ge=1, le=30),
    mode: str = Query(default="category", pattern="^(category|sitemap)$"),
    db: Session = Depends(get_db),
) -> IngestOut:
    """手动更新；≥10秒/请求。旧详情超过复核周期后可重新采集。"""
    factory = getattr(request.app.state, "smzdm_collector_factory", None)
    if factory is not None:
        collector = factory()
    else:
        from app.collectors.smzdm import SmzdmFeedCollector

        collector = SmzdmFeedCollector(max_details_per_run=details)
    try:
        if mode == "sitemap":
            drafts = list(collector.collect(max_source_id(db), limit=details))
        else:
            drafts = list(
                collector.collect_categories(
                    exclude_ids=known_source_ids(db, fresh_only=True), limit=details
                )
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"线报拉取失败: {exc}") from exc
    finally:
        close = getattr(collector, "close", None)
        if close:
            close()
    result = ingest_deals(db, drafts)
    return IngestOut(ok=not result["errors"], **result)


@router.get("/{deal_id}")
def deal_detail(deal_id: int, db: Session = Depends(get_db)) -> dict:
    deal = db.get(Deal, deal_id)
    if deal is None:
        raise HTTPException(404, "优惠线报不存在")
    ctx = variant_context(db, {deal.matched_variant_id} if deal.matched_variant_id else set())
    result = _to_out(deal, ctx)
    channels = channel_quotes(db, deal.matched_variant_id) if deal.matched_variant_id else []
    current = current_cny_quotes(channels)
    related = []
    if deal.matched_variant_id:
        related_rows = db.exec(
            select(Deal)
            .where(Deal.matched_variant_id == deal.matched_variant_id, Deal.id != deal.id)
            .order_by(Deal.created_at.desc())
            .limit(8)
        ).all()
        related = [_to_out(row, ctx).model_dump() for row in related_rows]
    notes = ["线报发布价不等于当前可成交价；请核对优惠条件、库存及适用规格。"]
    if result.match_status != "confirmed":
        notes.append("这条线报的完整规格尚未确认，暂不与其他尺码或颜色合并比价。")
    if not current:
        notes.append("目前没有可核验的人民币渠道报价，暂不能判断当前最低到手价。")
    if any(c["currency"] != "CNY" for c in channels):
        notes.append("海外渠道显示原币商品价；税费、运费与转运费需在海淘计算器补齐。")
    return {
        **result.model_dump(),
        "channels": channels,
        "related_deals": related,
        "purchase_notes": notes,
        "can_subscribe": bool(current),
        "history_days": max((c["history_days"] for c in channels), default=0),
        "min_price_cents": min((c["effective_cents"] for c in current), default=None),
    }
