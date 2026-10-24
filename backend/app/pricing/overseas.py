"""海淘落地价计算器。

公式（PRD §5）：
    海淘到手价 = (美元价 × (1−折扣) × (1−折扣码) + 美国运费) × 汇率 + 转运费 + 行邮税 − 返现×汇率

- 行邮税 = (商品+运费折人民币) × 税率；税额 ≤50 元免征；
- 单次限值 2000 元（商品+运费折人民币口径），超限提示可能退运或按货物报关；
- 用 Decimal 精确计算，展示字段四舍五入到分（ROUND_HALF_UP）；
- 验收样例（PRD §5）：$450 / 25% / 10% / 8% / $0 运费 / 7.1 / ¥220 → ¥2635.42。
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from pydantic import BaseModel, Field

TWO_PLACES = Decimal("0.01")


class OverseasInput(BaseModel):
    usd_price: float  # 美国标价（USD）
    discount: float = 0.0  # 站点折扣，0.25 = 七五折
    coupon_code: float = 0.0  # 折扣码，0.10 = 再九折
    us_shipping: float = 0.0  # 美国运费（USD）
    rate: float  # 汇率 CNY/USD
    transfer_fee_cny: float = 0.0  # 转运费（CNY）
    cashback: float = 0.0  # 返现比例（Rakuten / TopCashback），0.08 = 8%
    tax_rate: float = 0.20  # 行邮税
    tax_free_threshold_cny: float = 50.0  # 税额 ≤50 元免征
    parcel_limit_cny: float = 2000.0  # 单次限值


class OverseasResult(BaseModel):
    goods_paid_usd: float  # 商品实付（USD）
    total_usd: float  # 商品 + 美国运费（USD）
    goods_shipping_cny: float  # 商品 + 运费折人民币
    tax_cny: float  # 行邮税（免征后）
    tax_exempt: bool
    transfer_fee_cny: float
    cashback_cny: float  # 返现折回（正数展示，计算时为减项）
    landed_cny: float  # 最终到手价
    warnings: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _d(x: float) -> Decimal:
    return Decimal(str(x))


def _round(x: Decimal) -> float:
    return float(x.quantize(TWO_PLACES, rounding=ROUND_HALF_UP))


def calc_overseas(inp: OverseasInput) -> OverseasResult:
    usd_price = _d(inp.usd_price)
    goods_paid_usd = (
        usd_price * (Decimal(1) - _d(inp.discount)) * (Decimal(1) - _d(inp.coupon_code))
    )
    total_usd = goods_paid_usd + _d(inp.us_shipping)
    goods_shipping_cny = total_usd * _d(inp.rate)

    tax_raw = goods_shipping_cny * _d(inp.tax_rate)
    tax_exempt = tax_raw <= _d(inp.tax_free_threshold_cny)
    tax_cny = Decimal(0) if tax_exempt else tax_raw

    cashback_cny = goods_paid_usd * _d(inp.cashback) * _d(inp.rate)
    transfer = _d(inp.transfer_fee_cny)
    landed = goods_shipping_cny + tax_cny + transfer - cashback_cny

    warnings: list[str] = []
    notes: list[str] = []
    if goods_shipping_cny > _d(inp.parcel_limit_cny):
        warnings.append(
            f"商品价值（含运费）{_round(goods_shipping_cny)} 元超过 "
            f"{_round(_d(inp.parcel_limit_cny))} 元单次限值，可能被要求退运或按货物报关。"
        )
    if tax_exempt:
        notes.append(f"行邮税税额 {_round(tax_raw)} 元 ≤ {inp.tax_free_threshold_cny} 元，免征。")
    notes.append("行邮税按 20% 计，海关也可能按计税价格表而非实付计税；未计入美国销售税。")

    return OverseasResult(
        goods_paid_usd=_round(goods_paid_usd),
        total_usd=_round(total_usd),
        goods_shipping_cny=_round(goods_shipping_cny),
        tax_cny=_round(tax_cny),
        tax_exempt=tax_exempt,
        transfer_fee_cny=_round(transfer),
        cashback_cny=_round(cashback_cny),
        landed_cny=_round(landed),
        warnings=warnings,
        notes=notes,
    )
