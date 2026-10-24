"""报价 API 回归：关联商品上下文与无listing的手工计算。"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import PromoRule
from app.util import dump_json, utc_now


@pytest.mark.parametrize("scope_key", ["brand_ids", "style_ids", "variant_ids", "listing_ids"])
def test_quote_api_rejects_other_product_coupon(client, seed, scope_key: str) -> None:
    # 手算：其他商品的80000分券无效，符合完整范围的10000分券有效，100000−10000=90000。
    listing = seed.add_listing(seed.jd, external_id="api-scope", price_cents=100000)
    context = {
        "brand_ids": [seed.brand.id],
        "style_ids": [seed.style.id],
        "variant_ids": [seed.variant.id],
        "listing_ids": [listing.id],
    }
    bad_scope = {**context, scope_key: [context[scope_key][0] + 1000]}
    valid = PromoRule(
        name="适用券", kind="store_coupon", amount_cents=10000, scope_json=dump_json(context)
    )
    seed.session.add_all(
        [
            valid,
            PromoRule(
                name="非适用券",
                kind="store_coupon",
                amount_cents=80000,
                scope_json=dump_json(bad_scope),
            ),
        ]
    )
    seed.session.commit()

    response = client.post("/api/pricing/quote", json={"listing_id": listing.id})

    assert response.status_code == 200
    assert response.json()["paid_now_cents"] == 90000
    assert response.json()["applied_promo_ids"] == [f"rule-{valid.id}"]


def test_quote_api_ignores_expired_and_future_database_coupons(client, seed) -> None:
    # 手算：过期券和未来券都不可用，100000分保持100000分。
    listing = seed.add_listing(seed.jd, external_id="api-expired", price_cents=100000)
    now = utc_now()
    seed.session.add_all(
        [
            PromoRule(
                name="过期券",
                kind="store_coupon",
                amount_cents=80000,
                valid_to=now - timedelta(days=1),
            ),
            PromoRule(
                name="未来券",
                kind="store_coupon",
                amount_cents=80000,
                valid_from=now + timedelta(days=1),
            ),
        ]
    )
    seed.session.commit()

    response = client.post("/api/pricing/quote", json={"listing_id": listing.id})

    assert response.status_code == 200
    assert response.json()["paid_now_cents"] == 100000
    assert response.json()["applied_promo_ids"] == []


def test_manual_quote_uses_only_explicit_request_promos(client, seed) -> None:
    # 手算：手工标价100000只减请求里的1000；数据库商品专享券90000不参与，得99000。
    seed.session.add(
        PromoRule(
            name="数据库商品专享",
            kind="store_coupon",
            amount_cents=90000,
            scope_json=dump_json({"variant_ids": [seed.variant.id]}),
        )
    )
    seed.session.commit()

    response = client.post(
        "/api/pricing/quote",
        json={
            "base_price_cents": 100000,
            "promos": [{"id": "manual", "kind": "store_coupon", "amount_cents": 1000}],
        },
    )

    assert response.status_code == 200
    assert response.json()["paid_now_cents"] == 99000
    assert response.json()["applied_promo_ids"] == ["manual"]


def test_manual_quote_honors_timezone_aware_validity(client) -> None:
    # 手算：2099年才开始的1000分券不可用，10000分保持原价；带时区输入不触发500。
    response = client.post(
        "/api/pricing/quote",
        json={
            "base_price_cents": 10000,
            "promos": [
                {
                    "id": "future",
                    "kind": "store_coupon",
                    "amount_cents": 1000,
                    "valid_from": "2099-01-01T00:00:00+08:00",
                }
            ],
        },
    )

    assert response.status_code == 200
    assert response.json()["paid_now_cents"] == 10000
    assert response.json()["applied_promo_ids"] == []
