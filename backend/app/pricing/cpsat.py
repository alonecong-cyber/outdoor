"""多商品多渠道最低价：CP-SAT 整数规划（M6，第二阶段交付，接口先立好）。

模型（PRD §5.4）：
- x[商品,渠道] ∈ {0,1}：每件商品只在一个渠道下一次单（Σ_c x[i,c] = 1）；
- y[渠道,优惠] ∈ {0,1}：优惠只作用于所在渠道的订单；
- 门槛：y=1 时该渠道订单金额（标价合计，分）≥ 门槛；
- 互斥组：同组优惠 Σy ≤ 1；
- 目标：最小化总到手价。

简化口径（在 docstring 明示，避免误解为精确结算）：
- 订单金额按"该渠道所选商品标价合计"计（顺序叠加的券-券相互作用不建模，
  单渠道内的精确叠加仍走 app.pricing.solver 枚举）；
- 比例类优惠通过把目标放大 1000 倍（毫分级）保持整数线性化。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.pricing.rules import Promo, PromoKind

RATE_SCALE = 1000  # 比例 × 金额 的整数化放大倍数


@dataclass(frozen=True)
class ChannelOption:
    """商品 i 在渠道 c 的一个购买选项。"""

    channel: str
    base_price_cents: int


@dataclass
class ItemToBuy:
    item_id: str
    name: str = ""
    options: list[ChannelOption] = field(default_factory=list)


@dataclass
class ChosenOption:
    item_id: str
    channel: str
    base_price_cents: int
    applied_promos: list[str] = field(default_factory=list)


@dataclass
class MultiItemSolution:
    total_paid_cents: int
    total_rebate_cents: int
    choices: list[ChosenOption] = field(default_factory=list)

    @property
    def effective_cents(self) -> int:
        return self.total_paid_cents - self.total_rebate_cents


def solve_multi_item(
    items: list[ItemToBuy],
    channel_promos: dict[str, list[Promo]],
) -> MultiItemSolution:
    """求多商品多渠道最低总到手价。需要 ortools；无解/无依赖时抛异常。"""
    try:
        from ortools.sat.python import cp_model
    except ImportError as e:  # pragma: no cover - 环境缺依赖时的友好报错
        raise RuntimeError("CP-SAT 需要 ortools：uv sync 后重试") from e

    for it in items:
        if not it.options:
            raise ValueError(f"商品 {it.item_id} 没有可用渠道选项")

    model = cp_model.CpModel()
    x: dict[tuple[str, str], object] = {}
    base: dict[tuple[str, str], int] = {}

    for it in items:
        for opt in it.options:
            x[(it.item_id, opt.channel)] = model.new_bool_var(f"x_{it.item_id}_{opt.channel}")
            base[(it.item_id, opt.channel)] = opt.base_price_cents
        model.add_exactly_one([x[(it.item_id, opt.channel)] for opt in it.options])

    # 每个渠道的订单金额（标价合计）
    channels = sorted({opt.channel for it in items for opt in it.options})
    order_amount: dict[str, object] = {}
    for c in channels:
        terms = [
            base[(it.item_id, o.channel)] * x[(it.item_id, o.channel)]
            for it in items
            for o in it.options
            if o.channel == c
        ]
        if terms:
            v = model.new_int_var(0, 10**12, f"order_{c}")
            model.add(v == sum(terms))
            order_amount[c] = v

    # 优惠变量与折扣（毫 = 分×1000，保证比例优惠整数化）
    y: dict[tuple[str, str], object] = {}
    discount_milli: dict[tuple[str, str], object] = {}
    rebate_milli: dict[tuple[str, str], object] = {}
    big_m = 10**12

    for c, promos in channel_promos.items():
        for p in promos:
            key = (c, p.id)
            y[key] = model.new_bool_var(f"y_{c}_{p.id}")
            if p.threshold_cents > 0:
                # y=1 ⇒ order_amount[c] ≥ threshold
                model.add(order_amount[c] >= p.threshold_cents * y[key] - big_m * (1 - y[key]))

            is_rebate = p.kind in (PromoKind.REBATE, PromoKind.CASHBACK)
            d = model.new_int_var(0, big_m, f"d_{c}_{p.id}")
            if is_rebate:
                # 返利/返现不动实付，只进 r；否则目标函数里会被减两次
                model.add(d == 0)
            elif p.amount_cents > 0:
                model.add(d == p.amount_cents * RATE_SCALE * y[key])
            elif p.rate > 0:
                # z = y * order_amount（二元×整数线性化）
                z = model.new_int_var(0, big_m, f"z_{c}_{p.id}")
                model.add(z <= big_m * y[key])
                model.add(z <= order_amount[c])
                model.add(z >= order_amount[c] - big_m * (1 - y[key]))
                rate_milli = int(round(p.rate * RATE_SCALE))
                model.add(d == rate_milli * z)
            else:
                model.add(d == 0)
            if p.cap_cents > 0:
                model.add(d <= p.cap_cents * RATE_SCALE)
            discount_milli[key] = d

            if p.kind in (PromoKind.REBATE, PromoKind.CASHBACK):
                r = model.new_int_var(0, big_m, f"r_{c}_{p.id}")
                if p.amount_cents > 0:
                    model.add(r == p.amount_cents * RATE_SCALE * y[key])
                elif p.rate > 0:
                    z = model.new_int_var(0, big_m, f"rz_{c}_{p.id}")
                    model.add(z <= big_m * y[key])
                    model.add(z <= order_amount[c])
                    model.add(z >= order_amount[c] - big_m * (1 - y[key]))
                    rate_milli = int(round(p.rate * RATE_SCALE))
                    model.add(r == rate_milli * z)
                else:
                    model.add(r == 0)
                if p.cap_cents > 0:
                    model.add(r <= p.cap_cents * RATE_SCALE)
                rebate_milli[key] = r
            else:
                rebate_milli[key] = None

    # 互斥组：同组优惠最多选一个（跨渠道也算互斥）
    groups: dict[str, list] = {}
    for (c, pid), var in y.items():
        promo = next(p for p in channel_promos[c] if p.id == pid)
        if promo.exclusive_group:
            groups.setdefault(promo.exclusive_group, []).append(var)
    for vars_ in groups.values():
        model.add_at_most_one(vars_)

    # 每渠道折扣总额不能超过订单金额
    for c in channels:
        ds = [d for (cc, _), d in discount_milli.items() if cc == c and d is not None]
        if ds:
            model.add(sum(ds) <= order_amount[c] * RATE_SCALE)

    # 目标：总到手（毫）= Σ订单金额×1000 − Σ折扣 − Σ返利
    objective = []
    for c in channels:
        objective.append(order_amount[c] * RATE_SCALE)
    objective.extend(-d for d in discount_milli.values() if d is not None)
    objective.extend(-r for r in rebate_milli.values() if r is not None)
    model.minimize(sum(objective))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10.0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise RuntimeError("CP-SAT 无解：请检查门槛/互斥约束")

    total_milli = int(solver.value(sum(objective)))
    # 毫 → 分；目标里折扣已含放大，直接换算
    total_effective = total_milli // RATE_SCALE

    choices = []
    for it in items:
        chosen = None
        for opt in it.options:
            if solver.value(x[(it.item_id, opt.channel)]):
                chosen = opt
                break
        assert chosen is not None
        applied = [
            p.id
            for p in channel_promos.get(chosen.channel, [])
            if solver.value(y[(chosen.channel, p.id)])
        ]
        choices.append(
            ChosenOption(
                item_id=it.item_id,
                channel=chosen.channel,
                base_price_cents=chosen.base_price_cents,
                applied_promos=applied,
            )
        )

    # 返利/返现是渠道级（整单一次），按 (渠道,优惠) 统计而非按商品重复累加
    total_rebate = 0
    for (c, pid), rv in rebate_milli.items():
        if rv is not None and solver.value(y[(c, pid)]):
            total_rebate += int(solver.value(rv)) // RATE_SCALE

    # total_effective 是 paid−rebate；paid = effective + rebate
    return MultiItemSolution(
        total_paid_cents=total_effective + total_rebate,
        total_rebate_cents=total_rebate,
        choices=choices,
    )
