"""CP-SAT 多商品多渠道测试。"""

from __future__ import annotations

from app.pricing import Promo, PromoKind
from app.pricing.cpsat import ChannelOption, ItemToBuy, solve_multi_item


def promo(kind: PromoKind, pid: str, **kw) -> Promo:
    defaults = dict(id=pid, kind=kind, name=pid)
    defaults.update(kw)
    return Promo(**defaults)


def test_threshold_coupon_pulls_same_channel():
    # 手算：A 在 jd 1000 / tb 900；B 在 jd 800 / tb 950。
    # jd 平台券满 1500 减 300：两件都走 jd → 订单 1800 ≥1500 → 1500。
    # 两件都走 tb → 1850（无券）；混合 jd+tb 不达门槛。最优 = jd+jd 1500。
    items = [
        ItemToBuy("A", "Alpha SV", [ChannelOption("jd", 100000), ChannelOption("tb", 90000)]),
        ItemToBuy("B", "Beta LT", [ChannelOption("jd", 80000), ChannelOption("tb", 95000)]),
    ]
    promos = {
        "jd": [
            promo(PromoKind.PLATFORM_COUPON, "p1", amount_cents=30000, threshold_cents=150000)
        ]
    }
    sol = solve_multi_item(items, promos)
    assert sol.total_paid_cents == 150000
    assert {c.channel for c in sol.choices} == {"jd"}


def test_cashback_channel_wins():
    # 手算：jd 无优惠；tb 无门槛 10% 返利。A: jd 1000 / tb 900；B: jd 800 / tb 950。
    #   A tb + B jd = 1700，返利 900×10% = 90 → 到手 1610 ←最低
    #   A tb + B tb = 1850，返利 185 → 1665
    #   双 jd = 1800；A jd + B tb = 1950−95 = 1855
    # → 返利让渠道混搭最优：A 走 tb、B 走 jd
    items = [
        ItemToBuy("A", "Alpha SV", [ChannelOption("jd", 100000), ChannelOption("tb", 90000)]),
        ItemToBuy("B", "Beta LT", [ChannelOption("jd", 80000), ChannelOption("tb", 95000)]),
    ]
    promos = {"tb": [promo(PromoKind.REBATE, "r1", rate=0.10)]}
    sol = solve_multi_item(items, promos)
    assert {c.item_id: c.channel for c in sol.choices} == {"A": "tb", "B": "jd"}
    assert sol.total_paid_cents == 170000
    assert sol.total_rebate_cents == 9000
    assert sol.effective_cents == 161000


def test_exclusive_group_across_channels():
    # 手算：jd 和 tb 各有一张平台券但同属互斥组 "big"（同一次采购只享其一）。
    # jd 券 300（门槛 1500，订单 1800 达标）→ 1500；
    # tb 券 100 → 1750。互斥约束下最优仍 1500，但两张券不会同时计。
    items = [
        ItemToBuy("A", "Alpha SV", [ChannelOption("jd", 100000), ChannelOption("tb", 90000)]),
        ItemToBuy("B", "Beta LT", [ChannelOption("jd", 80000), ChannelOption("tb", 95000)]),
    ]
    promos = {
        "jd": [promo(PromoKind.PLATFORM_COUPON, "pj", amount_cents=30000,
                     threshold_cents=150000, exclusive_group="big")],
        "tb": [promo(PromoKind.PLATFORM_COUPON, "pt", amount_cents=10000,
                     threshold_cents=100000, exclusive_group="big")],
    }
    sol = solve_multi_item(items, promos)
    assert sol.total_paid_cents == 150000
    used = {p for c in sol.choices for p in c.applied_promos}
    assert used == {"pj"}  # 互斥组跨渠道：只用了 jd 那张大额券


def test_single_item_multiple_channels():
    # 手算：一件商品三渠道 500/450/480 → 直接选最便宜 450
    items = [
        ItemToBuy("A", "Torrentshell", [
            ChannelOption("jd", 50000), ChannelOption("tb", 45000), ChannelOption("us", 48000),
        ])
    ]
    sol = solve_multi_item(items, {})
    assert sol.total_paid_cents == 45000
    assert sol.choices[0].channel == "tb"
