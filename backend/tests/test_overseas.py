"""海淘到手价测试。验收样例来自 PRD §5，数字必须逐项对上。"""

from __future__ import annotations

from app.pricing import OverseasInput, calc_overseas


class TestAcceptanceSample:
    def test_prd_sample(self):
        # PRD 验收样例：$450 / 25% 折扣 / 10% 码 / 8% 返现 / $0 美国运费
        #               / 汇率 7.1 / 转运 ¥220
        # 手算：商品实付 = 450×0.75×0.90 = $303.75
        #       折人民币 = 303.75×7.1 = ¥2156.625
        #       行邮税 = 2156.625×0.20 = ¥431.325（>50 不免征）
        #       返现 = 303.75×0.08×7.1 = ¥172.53
        #       到手 = 2156.625 + 431.325 + 220 − 172.53 = ¥2635.42
        r = calc_overseas(
            OverseasInput(
                usd_price=450,
                discount=0.25,
                coupon_code=0.10,
                us_shipping=0,
                rate=7.1,
                transfer_fee_cny=220,
                cashback=0.08,
            )
        )
        assert r.goods_paid_usd == 303.75
        assert r.goods_shipping_cny == 2156.63  # 展示层四舍五入
        assert r.tax_cny == 431.33
        assert r.cashback_cny == 172.53
        assert r.landed_cny == 2635.42
        assert not r.tax_exempt
        # 样例本身含运费 2156.63 > 2000 单次限值 → 应有超限提醒（不影响价格）
        assert len(r.warnings) == 1 and "2000" in r.warnings[0]

    def test_no_rounding_drift(self):
        # 手算：中间步骤全部用 Decimal，最终 2635.42 而非分步取整的 2635.43
        r = calc_overseas(
            OverseasInput(
                usd_price=450, discount=0.25, coupon_code=0.10, rate=7.1,
                transfer_fee_cny=220, cashback=0.08,
            )
        )
        assert r.landed_cny == 2635.42


class TestTaxRules:
    def test_tax_exempt_under_50(self):
        # 手算：$30×7.1 = ¥213，税 213×0.2 = ¥42.6 ≤ 50 → 免征
        r = calc_overseas(OverseasInput(usd_price=30, rate=7.1))
        assert r.tax_exempt
        assert r.tax_cny == 0

    def test_parcel_limit_warning(self):
        # 手算：$500×7.1 = ¥3550 > 2000 → 超单次限值提示
        r = calc_overseas(OverseasInput(usd_price=500, rate=7.1))
        assert any("2000" in w for w in r.warnings)

    def test_us_shipping_taxed(self):
        # 手算：(100+10)×7 = ¥770，税 154 > 50 → 不免征
        r = calc_overseas(OverseasInput(usd_price=100, us_shipping=10, rate=7))
        assert r.total_usd == 110
        assert r.goods_shipping_cny == 770
        assert r.tax_cny == 154
        assert not r.tax_exempt
