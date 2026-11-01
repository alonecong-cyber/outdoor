"""线报摘要优惠解析与最优方案接口回归（离线，不联网）。"""

from app.models import DealDraft
from app.pricing.plan import parse_base_price, parse_claimed_final, parse_summary_promos

CAMEL_SUMMARY = (
    "天猫精选此款目前活动售价669元，领取淘礼金87.8元，下单领取满669减129元，"
    "88VIP消费券满480减60元优惠券，天猫APP超神卡运动到92折，参与立减101元优惠活动，"
    "下单1件，凑1件，主商品实付低至263.2元。"
)


def draft(title="骆驼 3514 男女款三合一冲锋衣", summary=CAMEL_SUMMARY, price=26320, channel="天猫"):
    return DealDraft(
        source="smzdm",
        source_id=f"plan-test-{title[:6]}",
        url=f"https://www.smzdm.com/p/{title[:6]}/",
        title=title,
        summary=summary,
        price_cents=price,
        channel=channel,
    )


def test_summary_promos_parse_kinds_and_amounts():
    promos = parse_summary_promos(CAMEL_SUMMARY)
    by_kind = {p.kind for p in promos}
    assert by_kind == {"store_coupon", "platform_coupon", "direct_discount", "payment_discount"}
    kinds = {(p.kind, p.threshold_cents, p.amount_cents, p.rate) for p in promos}
    assert ("store_coupon", 0, 8780, 0.0) in kinds  # 淘礼金 87.8 元
    assert ("store_coupon", 66900, 12900, 0.0) in kinds  # 满669减129（领取句式）
    assert ("platform_coupon", 48000, 6000, 0.0) in kinds  # 88VIP 消费券满480减60
    assert ("direct_discount", 0, 0, 0.08) in kinds  # 92折 → 减 8%
    assert ("payment_discount", 0, 10100, 0.0) in kinds  # 立减101元


def test_summary_base_and_claimed_final():
    assert parse_base_price(CAMEL_SUMMARY) == 66900
    assert parse_claimed_final(CAMEL_SUMMARY) == 26320


def test_summary_without_base_price_yields_no_promos():
    assert parse_base_price("质感在线，到手349元算好价。") is None
    assert parse_summary_promos("质感在线，到手349元算好价。") == []


def test_variant_plan_endpoint(seed, client):
    from sqlmodel import select

    from app.deals import ingest_deals
    from app.models import Deal

    ingest_deals(seed.session, [draft()], grow_catalog=False)
    deal = seed.session.exec(select(Deal).where(Deal.summary == CAMEL_SUMMARY)).one()
    deal.matched_variant_id = seed.variant.id
    seed.session.add(deal)
    seed.session.commit()
    response = client.get(f"/api/variants/{seed.variant.id}/plan")
    assert response.status_code == 200
    data = response.json()
    assert data["basis"] == "reported"
    plan = data["best_plan"]
    assert plan["base_price_cents"] == 66900
    assert plan["effective_cents"] < 66900
    assert plan["promo_count"] >= 4
    assert plan["claimed_final_cents"] == 26320
    assert any(step["delta_cents"] < 0 for step in plan["steps"])
    platforms = data["platforms"]
    assert platforms[0]["channel"] == "天猫"


def test_variants_search_matches_brand_cn(seed, client):
    from app.deals import ingest_deals

    ingest_deals(seed.session, [draft()], grow_catalog=True)
    data = client.get("/api/variants", params={"q": "骆驼"}).json()
    assert len(data) == 1 and data[0]["brand"] == "camel"
    assert client.get("/api/variants", params={"q": "3514"}).json()


def test_variant_plan_404_without_priced_deals(seed, client):
    response = client.get("/api/variants/999999/plan")
    assert response.status_code == 404
