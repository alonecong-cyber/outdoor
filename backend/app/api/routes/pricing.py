"""定价 API：国内到手价报价、海淘到手价、凑单。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api.deps import get_db
from app.api.schemas import (
    FillerIn,
    FillerOut,
    PromoIn,
    QuoteIn,
    QuoteOut,
    StepOut,
)
from app.models import Listing, PromoRule
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
)
from app.storage import last_snapshot
from app.util import load_json

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


def _rule_to_promo(rule: PromoRule) -> Promo:
    scope = PromoScope(**load_json(rule.scope_json, {}))
    return Promo(
        id=f"rule-{rule.id}",
        kind=PromoKind(rule.kind),
        name=rule.name,
        threshold_cents=rule.threshold_cents or 0,
        amount_cents=rule.amount_cents or 0,
        rate=rule.rate or 0.0,
        cap_cents=rule.cap_cents or 0,
        exclusive_group=rule.exclusive_group or "",
        scope=scope,
        valid_from=rule.valid_from,
        valid_to=rule.valid_to,
        source=rule.source or "db",
    )


@router.post("/quote", response_model=QuoteOut)
def quote(body: QuoteIn, db: Session = Depends(get_db)) -> QuoteOut:
    """单品单渠道最低到手价。listing_id 走库（含该渠道+平台级活动规则），
    否则用请求体里的 base_price_cents + promos。"""
    if body.listing_id is not None:
        listing = db.get(Listing, body.listing_id)
        if listing is None:
            raise HTTPException(404, "listing 不存在")
        snap = last_snapshot(db, listing.id)
        if snap is None:
            raise HTTPException(409, "listing 无价格快照")
        rules = db.exec(
            select(PromoRule).where(
                PromoRule.active,  # type: ignore[arg-type]
                PromoRule.channel_id.is_(None)  # type: ignore[union-attr]
                | (PromoRule.channel_id == listing.channel_id),  # type: ignore[union-attr]
            )
        ).all()  # type: ignore[call-overload]
        # 有效性（valid_from/to）由 Promo.is_valid_at 在引擎里过滤
        promos = [_rule_to_promo(r) for r in rules]
        base = snap.price_cents
    else:
        if body.base_price_cents <= 0:
            raise HTTPException(422, "base_price_cents 必须为正（或提供 listing_id）")
        promos = [_promo_in_to_promo(p) for p in body.promos]
        base = body.base_price_cents

    result = best_combination(base, promos)
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
