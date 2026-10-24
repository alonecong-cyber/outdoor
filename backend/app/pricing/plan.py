"""线报摘要 → 优惠规则解析，单品最优叠加方案（参考口径）。

线报的 price_cents 是文章标注的「到手低至价」，原价与优惠条件写在摘要里。
这里把摘要中的常见优惠句式解析成 Promo，再用定价引擎枚举最优叠加；
解析不出来原价时只给单步参考价，绝不把券叠在到手价上二次折算。
"""

from __future__ import annotations

import re

from app.models import Deal
from app.offers import iso
from app.pricing import Promo, PromoKind, best_combination

# 元金额，允许一位小数
_AMT = r"(\d+(?:\.\d+)?)"

# 满X减Y（每满X减Y 也按单档满减估算，方案备注会说明）
_FULL_REDUCE = re.compile(r"每?满" + _AMT + r"元?减" + _AMT)
# 领券/淘礼金/消费券 + 无门槛面额
_PLAIN_COUPON = re.compile(
    r"(?:领券|优惠券|淘礼金|消费券|购物券|红包)[^\d。；]{0,6}" + _AMT + r"元"
)
# 折扣：92折 = 减 8%
_OFF_RATE = re.compile(_AMT + r"折")
# 返现（积分价值不定，不解析）
_REBATE = re.compile(r"返现?" + _AMT + r"元")
# 支付立减 / 立减
_PAY_DISCOUNT = re.compile(r"(?:支付立减|立减)" + _AMT + r"元")
# 原价句式：活动售价669元 / 售价1234元 / 价格为99元
_BASE_PRICE = re.compile(r"(?:活动)?(?:售价|价格|原价|单价)(?:为|是|仅)?" + _AMT + r"元")
# 线报声称的到手价：实付低至263.2元 / 低至99元
_CLAIMED_FINAL = re.compile(r"(?:实付|到手)?低至" + _AMT + r"元")

_PLATFORM_WORDS = ("88VIP", "平台", "全站")
_MAX_PROMOS = 12


def _cents(text: str) -> int:
    return int(round(float(text) * 100))


def _match_text(text: str, match: re.Match[str], back: int = 14) -> str:
    """匹配位置往前一小段，用于判断句式语境（领取/跨店/平台）。"""
    start = max(0, match.start() - back)
    return text[start : match.end()]


def parse_summary_promos(summary: str) -> list[Promo]:
    """把线报摘要里的优惠句式解析成 Promo 列表；识别不出返回空。"""
    promos: list[Promo] = []
    seen: set[tuple] = set()

    def add(promo: Promo) -> None:
        key = (promo.kind, promo.threshold_cents, promo.amount_cents, promo.rate)
        if key not in seen and len(promos) < _MAX_PROMOS:
            seen.add(key)
            promos.append(promo)

    if not summary:
        return promos
    for match in _FULL_REDUCE.finditer(summary):
        context = _match_text(summary, match)
        if "跨店" in context:
            kind = PromoKind.CROSS_STORE_FULL_REDUCE
        elif any(word in context for word in _PLATFORM_WORDS) or "消费券" in context:
            kind = PromoKind.PLATFORM_COUPON
        elif "红包" in context:
            kind = PromoKind.RED_PACKET
        elif "券" in context or "领取" in context:
            kind = PromoKind.STORE_COUPON
        else:
            kind = PromoKind.STORE_FULL_REDUCE
        add(
            Promo(
                id=f"summary-full-{len(seen)}",
                kind=kind,
                name=match.group(0),
                threshold_cents=_cents(match.group(1)),
                amount_cents=_cents(match.group(2)),
                source="summary",
            )
        )
    for match in _PLAIN_COUPON.finditer(summary):
        context = _match_text(summary, match)
        kind = (
            PromoKind.PLATFORM_COUPON
            if any(word in context for word in _PLATFORM_WORDS) or "消费券" in match.group(0)
            else PromoKind.RED_PACKET
            if "红包" in match.group(0)
            else PromoKind.STORE_COUPON
        )
        add(
            Promo(
                id=f"summary-coupon-{len(seen)}",
                kind=kind,
                name=match.group(0),
                amount_cents=_cents(match.group(1)),
                source="summary",
            )
        )
    for match in _OFF_RATE.finditer(summary):
        value = float(match.group(1))
        ratio = value / 100.0 if value > 10 else value / 10.0  # 92折 与 9.2折 等价
        discount = 1.0 - ratio
        if 0 < discount < 1:
            add(
                Promo(
                    id=f"summary-rate-{len(seen)}",
                    kind=PromoKind.DIRECT_DISCOUNT,
                    name=match.group(0),
                    rate=round(discount, 4),
                    source="summary",
                )
            )
    for match in _REBATE.finditer(summary):
        add(
            Promo(
                id=f"summary-rebate-{len(seen)}",
                kind=PromoKind.REBATE,
                name=match.group(0),
                amount_cents=_cents(match.group(1)),
                source="summary",
            )
        )
    for match in _PAY_DISCOUNT.finditer(summary):
        add(
            Promo(
                id=f"summary-pay-{len(seen)}",
                kind=PromoKind.PAYMENT_DISCOUNT,
                name=match.group(0),
                amount_cents=_cents(match.group(1)),
                source="summary",
            )
        )
    return promos


def parse_base_price(summary: str) -> int | None:
    """摘要中声称的活动原价（分）；识别不出返回 None。"""
    for match in _BASE_PRICE.finditer(summary):
        cents = _cents(match.group(1))
        if cents > 0:
            return cents
    return None


def parse_claimed_final(summary: str) -> int | None:
    """摘要中声称的到手低至价（分）；识别不出返回 None。"""
    for match in _CLAIMED_FINAL.finditer(summary):
        cents = _cents(match.group(1))
        if cents > 0:
            return cents
    return None


def _deal_plan(deal: Deal) -> dict:
    """单条线报的参考方案：优先用摘要原价叠券，拆不出原价就只报到手价。"""
    base = parse_base_price(deal.summary)
    promos = parse_summary_promos(deal.summary) if base else []
    claimed = parse_claimed_final(deal.summary)
    if base:
        result = best_combination(base, promos)
        computed = result.effective_cents
        notes = []
        if claimed is not None and abs(computed - claimed) > 100:
            notes.append("与线报标注到手价有出入（可能含凑单或会员条件），以渠道结算为准")
    else:
        computed = deal.price_cents
        result = None
        notes = ["线报未给出原价，无法拆分优惠叠加，仅按标注到手价展示"]
    return {
        "deal_id": deal.id,
        "channel": deal.channel,
        "url": deal.url,
        "title": deal.title,
        "published_at": iso(deal.published_at or deal.created_at),
        "base_price_cents": base if base else deal.price_cents,
        "paid_now_cents": result.paid_now_cents if result else computed,
        "rebate_cents": result.rebate_cents if result else 0,
        "effective_cents": computed,
        "claimed_final_cents": claimed,
        "promo_count": len(promos),
        "steps": [
            {
                "promo_name": step.promo_name,
                "kind": step.kind.value,
                "amount_before_cents": step.amount_before_cents,
                "delta_cents": step.delta_cents,
                "amount_after_cents": step.amount_after_cents,
                "note": step.note,
            }
            for step in (result.steps if result else [])
        ],
        "notes": notes,
    }


def build_variant_plan(session, variant_id: int) -> dict | None:
    """各平台参考现价 + 最优叠加方案。没有带价线报返回 None。"""
    from sqlmodel import select

    deals = list(
        session.exec(
            select(Deal)
            .where(
                Deal.matched_variant_id == variant_id,
                Deal.price_cents > 0,
                Deal.currency == "CNY",
            )
            .order_by(Deal.created_at.desc())
        ).all()
    )
    if not deals:
        return None
    plans = [_deal_plan(deal) for deal in deals]
    best = min(plans, key=lambda plan: (plan["effective_cents"], plan["paid_now_cents"]))

    platforms: dict[str, dict] = {}
    for deal, plan in zip(deals, plans, strict=True):
        key = deal.channel or "未知渠道"
        entry = platforms.get(key)
        if entry is None or plan["effective_cents"] < entry["min_price_cents"]:
            platforms[key] = {
                "channel": key,
                "min_price_cents": plan["effective_cents"],
                "deal_id": deal.id,
                "published_at": plan["published_at"],
                "deal_count": 0,
            }
        platforms[key]["deal_count"] += 1
    ordered = sorted(platforms.values(), key=lambda item: item["min_price_cents"])
    return {
        "variant_id": variant_id,
        "basis": "reported",
        "note": "方案由线报摘要估算（参考口径）：以摘要标注原价叠解析出的优惠；"
        "结算以渠道下单页为准，凑单、会员与库存可能影响最终价格。",
        "platforms": ordered,
        "best_plan": best,
    }
