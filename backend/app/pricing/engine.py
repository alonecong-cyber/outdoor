"""规则引擎：给定一组优惠，按顺序应用到标价上，产出逐步明细。

口径：
- 返利/返现不减少"当下实付"，单独累计到 rebate_cents（事后到账）；
- 比较口径 effective_cents = paid_now_cents - rebate_cents；
- 满减分摊（多件摊到每件）由 allocate_discount 提供。
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from app.pricing.rules import Promo, PromoKind, sort_promos


class StepResult(BaseModel):
    """一步优惠的明细：页面要展示"为什么是这个价"。"""

    promo_id: str
    promo_name: str
    kind: PromoKind
    amount_before_cents: int
    delta_cents: int  # 本步对订单金额的减免（负数）；返利步为 0
    amount_after_cents: int
    rebate_delta_cents: int = 0  # 本步新增的返利（分）
    note: str = ""


class AppliedResult(BaseModel):
    base_cents: int
    paid_now_cents: int  # 当下实付
    rebate_cents: int  # 事后到账（返利/返现）
    effective_cents: int  # paid_now - rebate，比较口径
    steps: list[StepResult] = Field(default_factory=list)


def _discount_of(promo: Promo, subtotal: int) -> int:
    """单条规则的减免额（未做上限与余额截断）。"""
    if promo.kind == PromoKind.MEMBER_PRICE:
        raise ValueError("member_price 是一口价，不是减免额")
    if promo.amount_cents > 0:
        return promo.amount_cents
    if promo.rate > 0:
        return int(round(subtotal * promo.rate))
    return 0


def apply_promos(
    base_cents: int, promos: list[Promo], *, skip_invalid: bool = True
) -> AppliedResult:
    """把一组优惠按固定顺序应用到 base_cents 上。

    skip_invalid=True 时过滤掉不在有效期内的规则。
    门槛判断基于"当前订单金额"（前面优惠已扣减），符合真实结算顺序。
    """
    active = [p for p in promos if p.is_valid_at()] if skip_invalid else list(promos)
    subtotal = base_cents
    rebate = 0
    steps: list[StepResult] = []

    for promo in sort_promos(active):
        before = subtotal

        if promo.kind == PromoKind.MEMBER_PRICE:
            # 会员价是一口价：只有比当前金额低才生效
            if 0 < promo.amount_cents < subtotal:
                subtotal = promo.amount_cents
                steps.append(
                    StepResult(
                        promo_id=promo.id,
                        promo_name=promo.name,
                        kind=promo.kind,
                        amount_before_cents=before,
                        delta_cents=subtotal - before,
                        amount_after_cents=subtotal,
                        note=f"会员价 {promo.amount_cents} 分生效",
                    )
                )
            else:
                steps.append(
                    StepResult(
                        promo_id=promo.id,
                        promo_name=promo.name,
                        kind=promo.kind,
                        amount_before_cents=before,
                        delta_cents=0,
                        amount_after_cents=subtotal,
                        note="会员价不低于当前金额，跳过",
                    )
                )
            continue

        # 门槛：订单金额 ≥ threshold 才可用
        if promo.threshold_cents > 0 and subtotal < promo.threshold_cents:
            steps.append(
                StepResult(
                    promo_id=promo.id,
                    promo_name=promo.name,
                    kind=promo.kind,
                    amount_before_cents=before,
                    delta_cents=0,
                    amount_after_cents=subtotal,
                    note=f"门槛 {promo.threshold_cents} 分未满足，跳过",
                )
            )
            continue

        if promo.kind in (PromoKind.REBATE, PromoKind.CASHBACK):
            # 返利按实付计算、事后到账，不动当下实付
            gain = (
                promo.amount_cents
                if promo.amount_cents > 0
                else int(round(subtotal * promo.rate))
            )
            if promo.cap_cents > 0:
                gain = min(gain, promo.cap_cents)
            rebate += gain
            steps.append(
                StepResult(
                    promo_id=promo.id,
                    promo_name=promo.name,
                    kind=promo.kind,
                    amount_before_cents=before,
                    delta_cents=0,
                    amount_after_cents=subtotal,
                    rebate_delta_cents=gain,
                    note="事后到账，与当下实付分开展示",
                )
            )
            continue

        discount = _discount_of(promo, subtotal)
        if promo.cap_cents > 0:
            discount = min(discount, promo.cap_cents)
        discount = min(discount, subtotal)  # 不能减成负数
        subtotal -= discount
        steps.append(
            StepResult(
                promo_id=promo.id,
                promo_name=promo.name,
                kind=promo.kind,
                amount_before_cents=before,
                delta_cents=-discount,
                amount_after_cents=subtotal,
            )
        )

    return AppliedResult(
        base_cents=base_cents,
        paid_now_cents=subtotal,
        rebate_cents=rebate,
        effective_cents=subtotal - rebate,
        steps=steps,
    )


def allocate_discount(
    line_cents: list[tuple[str, int]], total_discount_cents: int
) -> dict[str, int]:
    """把一笔订单级减免按商品金额比例摊到每件（最大余数法，保证合计恰好相等）。

    退货时才算得准：退掉一件只回冲它分摊到的部分。
    """
    total = sum(c for _, c in line_cents)
    if total <= 0 or total_discount_cents <= 0:
        return {k: 0 for k, _ in line_cents}
    discount = min(total_discount_cents, total)
    raw = {k: c * discount / total for k, c in line_cents}
    alloc = {k: int(v) for k, v in raw.items()}
    remainder = discount - sum(alloc.values())
    # 余数从大到小逐个 +1，凑齐总减免
    for k in sorted(raw, key=lambda k: raw[k] - alloc[k], reverse=True):
        if remainder <= 0:
            break
        alloc[k] += 1
        remainder -= 1
    return alloc
