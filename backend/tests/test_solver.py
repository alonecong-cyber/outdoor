"""枚举求解器测试。手算过程见各用例注释。"""

from __future__ import annotations

from app.pricing import Promo, PromoKind, all_combinations, best_combination


def promo(kind: PromoKind, pid: str, **kw) -> Promo:
    defaults = dict(id=pid, kind=kind, name=pid)
    defaults.update(kw)
    return Promo(**defaults)


class TestAllCombinations:
    def test_count_is_2_pow_n(self):
        # 2 张互不冲突的券 → 组合数 2^2=4（含空集）
        promos = [
            promo(PromoKind.STORE_COUPON, "s1", amount_cents=30000, threshold_cents=300000),
            promo(PromoKind.PLATFORM_COUPON, "p1", amount_cents=10000, threshold_cents=200000),
        ]
        results = all_combinations(399800, promos)
        assert len(results) == 4

    def test_exclusive_group_prunes(self):
        # 同组店铺券两张互斥 → 组合数 2^2 − 2 = 3（都选的 2 个排列被剪掉）
        promos = [
            promo(PromoKind.STORE_COUPON, "s1", amount_cents=30000, exclusive_group="store"),
            promo(PromoKind.STORE_COUPON, "s2", amount_cents=20000, exclusive_group="store"),
        ]
        results = all_combinations(399800, promos)
        assert len(results) == 3


class TestBestCombination:
    def test_jd_sample(self):
        # 手算：3998 − 300(店铺券) − 100(平台券) = 3598 实付；
        # 返利 1% = 35.98 → 到手 3562.02 元
        promos = [
            promo(PromoKind.STORE_COUPON, "s1", amount_cents=30000, threshold_cents=300000),
            promo(PromoKind.PLATFORM_COUPON, "p1", amount_cents=10000, threshold_cents=200000),
            promo(PromoKind.REBATE, "r1", rate=0.01),
        ]
        r = best_combination(399800, promos)
        assert r.paid_now_cents == 359800
        assert r.rebate_cents == 3598
        assert r.effective_cents == 356202

    def test_exclusive_keeps_bigger_coupon(self):
        # 手算：互斥组内两张满减券只能用一张，取最低到手 → 30000 那张 → 3698
        promos = [
            promo(PromoKind.STORE_COUPON, "s1", amount_cents=30000, exclusive_group="store"),
            promo(PromoKind.STORE_COUPON, "s2", amount_cents=20000, exclusive_group="store"),
        ]
        r = best_combination(399800, promos)
        assert r.paid_now_cents == 369800
        assert [s.promo_id for s in r.steps] == ["s1"]

    def test_empty_set_when_promos_do_not_apply(self):
        # 手算：门槛全部不满足 → 空集最优，原价 4000
        promos = [
            promo(PromoKind.STORE_COUPON, "s1", amount_cents=30000, threshold_cents=500000),
        ]
        r = best_combination(400000, promos)
        assert r.paid_now_cents == 400000
        assert not r.steps
