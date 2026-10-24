"""线报流 API：GET /api/deals（Feed）、POST /api/deals/ingest（手动拉取最新线报）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlmodel import Session

from app.api.deps import get_db
from app.api.schemas import DealOut, DealVariantOut, IngestOut
from app.deals import (
    ingest_deals,
    known_source_ids,
    list_deals,
    max_source_id,
    variant_context,
)
from app.models import Deal
from app.util import load_json

router = APIRouter(prefix="/deals", tags=["deals"])


def _to_out(deal: Deal, ctx: dict[int, dict]) -> DealOut:
    v = ctx.get(deal.matched_variant_id or -1)
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
        published_at=deal.published_at.isoformat() + "Z" if deal.published_at else None,
        variant=DealVariantOut(**v) if v else None,
    )


@router.get("", response_model=list[DealOut])
def get_deals(
    q: str = "",
    brand: str = "",
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[DealOut]:
    """线报流（新→旧）。q 过滤标题；brand 只保留已匹配该品牌的线报。"""
    limit_eff = limit if not (q or brand) else 200
    deals = list_deals(db, limit=limit_eff, offset=offset if not (q or brand) else 0)
    if q:
        deals = [d for d in deals if q.lower() in d.title.lower()]
    if brand:
        deals = [d for d in deals if d.matched_variant_id is not None]
    ctx = variant_context(db, {d.matched_variant_id for d in deals if d.matched_variant_id})
    if brand:
        deals = [
            d
            for d in deals
            if ctx.get(d.matched_variant_id or -1, {}).get("brand_slug") == brand
        ]
    return [_to_out(d, ctx) for d in deals[:limit]]


@router.post("/ingest", response_model=IngestOut)
def ingest(
    request: Request,
    details: int = Query(default=10, ge=1, le=30),
    mode: str = Query(default="category"),
    db: Session = Depends(get_db),
) -> IngestOut:
    """从 smzdm 拉取线报（≥10s/请求，最长约 details×10 秒）。

    mode=category（默认）：户外品类页定向发现，跳过已入库 ID；
    mode=sitemap：全站 sitemap 增量（max_seen_id 之后的新线报）。
    """
    factory = getattr(request.app.state, "smzdm_collector_factory", None)
    if factory is not None:
        collector = factory()
    else:
        from app.collectors.smzdm import SmzdmFeedCollector

        collector = SmzdmFeedCollector(max_details_per_run=details)
    try:
        if mode == "sitemap":
            drafts = collector.collect(max_source_id(db), limit=details)
        else:
            drafts = collector.collect_categories(
                exclude_ids=known_source_ids(db), limit=details
            )
    except Exception as e:  # noqa: BLE001 - 采集失败给前端明确报错
        raise HTTPException(status_code=502, detail=f"线报拉取失败: {e}") from e
    finally:
        close = getattr(collector, "close", None)
        if close:
            close()
    result = ingest_deals(db, drafts)
    return IngestOut(ok=not result["errors"], **result)
