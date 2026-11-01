"""规则引擎测试。每条用例附手算过程（AGENTS.md 要求）。"""

from __future__ import annotations

from app.pricing import Promo, PromoKind, allocate_discount, apply_promos


def promo(kind: PromoKind, **kw) -> Promo:
    defaults = dict(
        id=f"{kind.value}-{kw.get('amount_cents', 0)}", kind=kind, name=kw.get("name", kind.value)
    )
    defaults.update(kw)
    return Promo(**defaults)


class TestApplyPromos:
    def test_single_store_coupon(self):
        # 手算：标价 3998 元，店铺券满 3000 减 300 → 3698 元
        r = apply_promos(
            399800,
            [promo(PromoKind.STORE_COUPON, amount_cents=30000, threshold_cents=300000)],
        )
        assert r.paid_now_cents == 369800
        assert r.effective_cents == 369800

    def test_apply_order_full_chain(self):
        # 手算（顺序：直降→店铺满减→平台券→支付立减）：
        # 5000 −500(直降) = 4500 ≥4000 → 满4000减500 → 4000
        # 平台券满3000减100 → 3900；支付立减 2%×3900 = 78 → 3822 元
        promos = [
            promo(PromoKind.STORE_FULL_REDUCE, amount_cents=50000, threshold_cents=400000),
            promo(PromoKind.DIRECT_DISCOUNT, amount_cents=50000),
            promo(PromoKind.PAYMENT_DISCOUNT, rate=0.02),
            promo(PromoKind.PLATFORM_COUPON, amount_cents=10000, threshold_cents=300000),
        ]
        r = apply_promos(500000, promos)
        assert r.paid_now_cents == 382200
        assert [s.kind for s in r.steps] == [
            PromoKind.DIRECT_DISCOUNT,
            PromoKind.STORE_FULL_REDUCE,
            PromoKind.PLATFORM_COUPON,
            PromoKind.PAYMENT_DISCOUNT,
        ]

    def test_threshold_uses_running_subtotal(self):
        # 手算：满减门槛 3000，直降后 4500−500=4000… 先直降到 2000：3000−1000=2000 < 3000 → 券跳过
        promos = [
            promo(PromoKind.DIRECT_DISCOUNT, amount_cents=100000),
            promo(PromoKind.STORE_COUPON, amount_cents=30000, threshold_cents=300000),
        ]
        r = apply_promos(300000, promos)
        assert r.paid_now_cents == 200000
        assert "门槛" in r.steps[1].note

    def test_member_price_only_when_lower(self):
        # 手算：会员价 3500 < 4000 → 3500；另一单会员价 4500 > 4000 → 保持 4000
        r_low = apply_promos(400000, [promo(PromoKind.MEMBER_PRICE, amount_cents=350000)])
        assert r_low.paid_now_cents == 350000
        r_high = apply_promos(400000, [promo(PromoKind.MEMBER_PRICE, amount_cents=450000)])
        assert r_high.paid_now_cents == 400000

    def test_rebate_separate_from_paid(self):
        # 手算：返利 1% 不动实付：付 1000，返 10，到手口径 990
        r = apply_promos(100000, [promo(PromoKind.REBATE, rate=0.01)])
        assert r.paid_now_cents == 100000
        assert r.rebate_cents == 1000
        assert r.effective_cents == 99000

    def test_cap_truncates_discount(self):
        # 手算：立减 50% 但封顶 100：300×50%=150 → 100 → 200 元
        r = apply_promos(30000, [promo(PromoKind.PAYMENT_DISCOUNT, rate=0.5, cap_cents=10000)])
        assert r.paid_now_cents == 20000

    def test_discount_never_negative(self):
        # 手算：券 80 > 余额 50 → 只减 50 → 0 元
        r = apply_promos(5000, [promo(PromoKind.STORE_COUPON, amount_cents=8000)])
        assert r.paid_now_cents == 0

    def test_invalid_promo_skipped(self):
        # 手算：过期券不参与：4000 → 4000
        from datetime import datetime, timedelta

        expired = promo(
            PromoKind.STORE_COUPON,
            amount_cents=30000,
            valid_to=datetime.utcnow() - timedelta(days=1),
        )
        r = apply_promos(400000, [expired])
        assert r.paid_now_cents == 400000
        assert not r.steps


class TestAllocateDiscount:
    def test_proportional_with_remainder(self):
        # 手算：1 元（100 分）减免按 1/3、2/3 摊：33.33→33、66.67→66，
        # 余 1 给小数部分最大的 b → 33+67=100
        alloc = allocate_discount([("a", 3333), ("b", 6667)], 100)
        assert alloc == {"a": 33, "b": 67}

    def test_one_cent_case(self):
        # 手算：1 分减免 → 摊给占比大的 b
        alloc = allocate_discount([("a", 3333), ("b", 6667)], 1)
        assert alloc == {"a": 0, "b": 1}

    def test_zero_discount(self):
        assert allocate_discount([("a", 100)], 0) == {"a": 0}
