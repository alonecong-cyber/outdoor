"""Listing 报价回归：范围、渠道、有效期与可复用 helper 的同源计算。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import pytest

from app.models import Listing, PromoRule
from app.pricing import Promo, PromoKind, apply_promos, best_combination, quote_listing
from app.util import dump_json

SCOPE_KEYS = ("brand_ids", "style_ids", "variant_ids", "listing_ids")
AT = datetime(2030, 1, 2, 12)


def _scope(seed, listing: Listing) -> dict[str, list[int]]:
    return {
        "brand_ids": [seed.brand.id],
        "style_ids": [seed.style.id],
        "variant_ids": [seed.variant.id],
        "listing_ids": [listing.id],
    }


def test_quote_listing_matching_scope_and_rebate(seed) -> None:
    # 手算：100000−同品牌/款式/规格/挂链券10000=实付90000；返利1%=900，到手89100。
    listing = seed.add_listing(seed.jd, external_id="quote-match", price_cents=100000)
    coupon = PromoRule(
        name="完整范围券",
        kind="store_coupon",
        channel_id=seed.jd.id,
        amount_cents=10000,
        scope_json=dump_json(_scope(seed, listing)),
    )
    rebate = PromoRule(name="全渠道返利", kind="rebate", rate=0.01)
    seed.session.add_all([coupon, rebate])
    seed.session.flush()

    result = quote_listing(seed.session, listing, now=AT)

    assert result.base_cents == 100000
    assert result.paid_now_cents == 90000
    assert result.rebate_cents == 900
    assert result.effective_cents == 89100
    assert [step.promo_id for step in result.steps] == [f"rule-{coupon.id}", f"rule-{rebate.id}"]


@pytest.mark.parametrize("mismatched_key", SCOPE_KEYS)
def test_quote_listing_rejects_any_mismatched_scope_dimension(seed, mismatched_key: str) -> None:
    # 手算：四维范围为 AND，任意一维不匹配，80000 分券无效，仍付100000。
    listing = seed.add_listing(seed.jd, external_id="quote-mismatch", price_cents=100000)
    scope = _scope(seed, listing)
    scope[mismatched_key] = [scope[mismatched_key][0] + 1000]
    seed.session.add(
        PromoRule(
            name="其他商品券", kind="store_coupon", amount_cents=80000, scope_json=dump_json(scope)
        )
    )
    seed.session.flush()

    result = quote_listing(seed.session, listing, now=AT)

    assert result.paid_now_cents == 100000
    assert not result.steps


def test_quote_listing_ignores_other_channel_and_inactive_rules(seed) -> None:
    # 手算：淘宝券和停用京东券均不可用；仅全渠道券1000生效，100000−1000=99000。
    listing = seed.add_listing(seed.jd, external_id="quote-channel", price_cents=100000)
    seed.session.add_all(
        [
            PromoRule(
                name="其他渠道", kind="store_coupon", channel_id=seed.taobao.id, amount_cents=90000
            ),
            PromoRule(
                name="停用",
                kind="store_coupon",
                channel_id=seed.jd.id,
                amount_cents=90000,
                active=False,
            ),
            PromoRule(name="通用", kind="store_coupon", amount_cents=1000),
        ]
    )
    seed.session.flush()

    assert quote_listing(seed.session, listing, now=AT).paid_now_cents == 99000


def test_unmatched_listing_cannot_use_unknown_product_scopes(seed) -> None:
    # 手算：未归一化时品牌/规格未知，定向券不可用；此listing专享券1000仍可用，付99000。
    listing = Listing(channel_id=seed.jd.id, external_id="unmatched")
    seed.session.add(listing)
    seed.session.flush()
    seed.session.add_all(
        [
            PromoRule(
                name="品牌券",
                kind="store_coupon",
                amount_cents=90000,
                scope_json=dump_json({"brand_ids": [seed.brand.id]}),
            ),
            PromoRule(
                name="规格券",
                kind="store_coupon",
                amount_cents=90000,
                scope_json=dump_json({"variant_ids": [seed.variant.id]}),
            ),
            PromoRule(
                name="此挂链券",
                kind="store_coupon",
                amount_cents=1000,
                scope_json=dump_json({"listing_ids": [listing.id]}),
            ),
        ]
    )
    seed.session.flush()

    result = quote_listing(seed.session, listing, base_price_cents=100000, now=AT)

    assert result.paid_now_cents == 99000
    assert len(result.steps) == 1


def test_quote_listing_uses_override_without_snapshot(seed) -> None:
    # 手算：尚未写入快照的新采集标价120000，减10000，得110000。
    listing = Listing(channel_id=seed.jd.id, variant_id=seed.variant.id, external_id="fresh")
    seed.session.add(listing)
    seed.session.add(PromoRule(name="通用券", kind="store_coupon", amount_cents=10000))
    seed.session.flush()

    assert (
        quote_listing(seed.session, listing, base_price_cents=120000, now=AT).paid_now_cents
        == 110000
    )
    with pytest.raises(ValueError, match="无价格快照"):
        quote_listing(seed.session, listing, now=AT)


def test_quote_listing_uses_one_explicit_time_for_all_validity_checks(seed) -> None:
    # 手算：2030年指定时点可用券10000，已过期/未开始券无效，100000−10000=90000。
    listing = seed.add_listing(seed.jd, external_id="quote-time", price_cents=100000)
    seed.session.add_all(
        [
            PromoRule(
                name="有效",
                kind="store_coupon",
                amount_cents=10000,
                valid_from=AT - timedelta(hours=1),
                valid_to=AT + timedelta(hours=1),
            ),
            PromoRule(
                name="过期",
                kind="store_coupon",
                amount_cents=80000,
                valid_to=AT - timedelta(microseconds=1),
            ),
            PromoRule(
                name="未开始",
                kind="store_coupon",
                amount_cents=80000,
                valid_from=AT + timedelta(microseconds=1),
            ),
        ]
    )
    seed.session.flush()

    assert quote_listing(seed.session, listing, now=AT.replace(tzinfo=UTC)).paid_now_cents == 90000


@pytest.mark.parametrize("quote", [apply_promos, best_combination])
def test_aware_validity_is_utc_and_honors_inclusive_boundaries(quote) -> None:
    # 手算：北京时间20:00=UTC12:00；起止边界当刻可用减1000，晚1微秒过期原价10000。
    local = AT.replace(hour=20, tzinfo=timezone(timedelta(hours=8)))
    promo = Promo(
        id="boundary",
        kind=PromoKind.STORE_COUPON,
        amount_cents=1000,
        valid_from=local,
        valid_to=local,
    )

    assert quote(10000, [promo], now=AT).paid_now_cents == 9000
    assert quote(10000, [promo], now=AT + timedelta(microseconds=1)).paid_now_cents == 10000
