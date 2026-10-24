"""定价 API：国内到手价报价、海淘到手价、凑单。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import get_db
from app.api.schemas import (
    FillerIn,
    FillerOut,
    PromoIn,
    QuoteIn,
    QuoteOut,
    StepOut,
)
from app.models import Listing
from app.pricing import (
    FillerItem,
    OverseasInput,
    OverseasResult,
    Promo,
    PromoKind,
    PromoScope,
    best_combination,
    best_filler,
    calc_overseas,
    quote_listing,
)

router = APIRouter(prefix="/pricing", tags=["pricing"])


def _promo_in_to_promo(p: PromoIn) -> Promo:
    return Promo(
        id=p.id or p.name or p.kind,
        kind=PromoKind(p.kind),
        name=p.name,
        threshold_cents=p.threshold_cents,
        amount_cents=p.amount_cents,
        rate=p.rate,
        cap_cents=p.cap_cents,
        exclusive_group=p.exclusive_group,
        scope=PromoScope(
            brand_ids=p.scope_brand_ids,
            style_ids=p.scope_style_ids,
            variant_ids=p.scope_variant_ids,
            listing_ids=p.scope_listing_ids,
        ),
        valid_from=p.valid_from,  # type: ignore[arg-type]
        valid_to=p.valid_to,  # type: ignore[arg-type]
    )


@router.post("/quote", response_model=QuoteOut)
def quote(body: QuoteIn, db: Session = Depends(get_db)) -> QuoteOut:
    """listing_id 使用共享挂链报价；手工模式仅计算请求显式提供的优惠。"""
    if body.listing_id is not None:
        listing = db.get(Listing, body.listing_id)
        if listing is None:
            raise HTTPException(404, "listing 不存在")
        try:
            result = quote_listing(db, listing)
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from exc
    else:
        if body.base_price_cents <= 0:
            raise HTTPException(422, "base_price_cents 必须为正（或提供 listing_id）")
        promos = [_promo_in_to_promo(p) for p in body.promos]
        result = best_combination(body.base_price_cents, promos)
    return QuoteOut(
        base_price_cents=result.base_cents,
        paid_now_cents=result.paid_now_cents,
        rebate_cents=result.rebate_cents,
        effective_cents=result.effective_cents,
        steps=[
            StepOut(
                promo_id=s.promo_id,
                promo_name=s.promo_name,
                kind=s.kind.value,
                amount_before_cents=s.amount_before_cents,
                delta_cents=s.delta_cents,
                amount_after_cents=s.amount_after_cents,
                note=s.note,
            )
            for s in result.steps
        ],
        applied_promo_ids=[s.promo_id for s in result.steps if s.promo_id],
    )


@router.post("/overseas", response_model=OverseasResult)
def overseas(body: OverseasInput) -> OverseasResult:
    """海淘到手价（美元价 → 人民币最终价），公式见 PRD §5.3。"""
    return calc_overseas(body)


@router.post("/filler", response_model=FillerOut)
def filler(body: FillerIn) -> FillerOut:
    """凑单推荐：刚好跨过 threshold 的最小加购组合。"""
    chosen = best_filler(
        body.threshold_cents,
        [FillerItem(id=i.id, name=i.name, price_cents=i.price_cents) for i in body.items],
    )
    if chosen is None:
        return FillerOut(ok=False, total_extra_cents=0, item_ids=[])
    return FillerOut(
        ok=True,
        total_extra_cents=sum(item.price_cents for item in chosen),
        item_ids=[item.id for item in chosen],
    )
