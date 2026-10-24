"""报价与外部通知边界回归：全部使用临时数据库及 stub 发送器。"""

import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import select

from app.models import AlertEvent, AlertSubscription, Listing, PriceSnapshot, RawListing
from app.scheduler import collect_and_store, send_pending_alerts
from app.util import utc_now


def offer(**changes):
    values = dict(
        source="jd_union",
        channel_slug="jd",
        external_id="stock-27910",
        url="https://item.jd.com/123.html",
        title="始祖鸟 Beta LT 27910 Black M",
        brand_hint="arcteryx",
        style_number_hint="27910",
        color_hint="Black",
        size_hint="M",
        price_cents=10000,
    )
    return RawListing(**(values | changes))


def subscribe(seed, kinds='["price_below"]'):
    sub = AlertSubscription(variant_id=seed.variant.id, target_price_cents=10000, kinds_json=kinds)
    seed.session.add(sub)
    seed.session.commit()
    return sub


def test_unknown_stock_never_becomes_available_offer_or_alert(seed, client):
    subscribe(seed, '["price_below", "restock"]')
    result = collect_and_store(seed.session, [offer(stock_verified=False)], channel_id=seed.jd.id)
    assert not result.alerts
    data = client.get(f"/api/variants/{seed.variant.id}").json()
    assert data["channels"][0]["in_stock"] is None
    assert data["min_price_cents"] is None and not data["can_subscribe"]
    again = collect_and_store(seed.session, [offer()], channel_id=seed.jd.id)
    assert all(event.kind != "restock" for event in again.alerts)


def test_disabled_channel_does_not_collect_or_create_alert(seed):
    seed.jd.active = False
    seed.session.add(seed.jd)
    seed.session.commit()
    result = collect_and_store(seed.session, [offer()], channel_id=seed.jd.id)
    assert result.saved == 0 and result.errors
    assert not seed.session.exec(select(PriceSnapshot)).all()
    assert not seed.session.exec(select(AlertEvent)).all()


@pytest.mark.parametrize(
    "change", ["out_of_stock", "channel_disabled", "price_increased", "stale", "cancelled"]
)
def test_queued_and_manual_alerts_recheck_conditions(seed, client, monkeypatch, change):
    sub = subscribe(seed)
    event = collect_and_store(seed.session, [offer()], channel_id=seed.jd.id).alerts[0]
    if change == "out_of_stock":
        collect_and_store(seed.session, [offer(in_stock=False)], channel_id=seed.jd.id)
    elif change == "price_increased":
        collect_and_store(seed.session, [offer(price_cents=15000)], channel_id=seed.jd.id)
    elif change == "channel_disabled":
        seed.jd.active = False
        seed.session.add(seed.jd)
    elif change == "cancelled":
        sub.active = False
        seed.session.add(sub)
    else:
        listing = seed.session.exec(select(Listing)).one()
        listing.last_seen_at = utc_now() - timedelta(days=2)
        seed.session.add(listing)
    seed.session.commit()
    calls = []

    def stub(*args, **kwargs):
        calls.append(args)
        return True, None

    monkeypatch.setattr("app.scheduler.send_alert", stub)
    monkeypatch.setattr("app.api.routes.alerts.send_alert", stub)
    assert send_pending_alerts(seed.session)["sent"] == 0
    assert client.post(f"/api/alerts/events/{event.id}/send").status_code == 409
    assert calls == []


def test_successful_manual_send_commits_non_null_error(seed, client, monkeypatch):
    subscribe(seed)
    event = collect_and_store(seed.session, [offer()], channel_id=seed.jd.id).alerts[0]
    monkeypatch.setattr("app.api.routes.alerts.send_alert", lambda *args, **kwargs: (True, None))
    response = client.post(f"/api/alerts/events/{event.id}/send")
    assert response.status_code == 200 and response.json()["ok"]
    seed.session.refresh(event)
    assert event.sent_at is not None and event.send_error == ""


def test_restock_subscription_can_be_created_while_out_of_stock(seed, client):
    collect_and_store(seed.session, [offer(in_stock=False)], channel_id=seed.jd.id)
    response = client.post(
        "/api/alerts/subscriptions", json={"variant_id": seed.variant.id, "kinds": ["restock"]}
    )
    assert response.status_code == 200
    assert (
        client.post(
            "/api/alerts/subscriptions",
            json={"variant_id": seed.variant.id, "target_price_cents": 10000},
        ).status_code
        == 409
    )


def test_real_avantlink_parser_preserves_same_sku_from_two_merchants(seed):
    from app.collectors.avantlink import parse_product_search

    rows = "".join(
        f"""<row><Product_ID>shared-id</Product_ID><SKU_Code>27910</SKU_Code>
        <Merchant_ID>{idx}</Merchant_ID><Merchant_Name>Shop {idx}</Merchant_Name>
        <Brand_Name>Arc'teryx</Brand_Name><Product_Name>Beta LT 27910 Black M</Product_Name>
        <Sale_Price>100</Sale_Price><Stock_Status>In Stock</Stock_Status>
        <Deep_URL>https://shop{idx}.example/item</Deep_URL></row>"""
        for idx in (1, 2)
    )
    result = collect_and_store(
        seed.session, parse_product_search(f"<table>{rows}</table>"), channel_id=seed.us.id
    )
    assert result.saved == 2 and not result.errors
    listings = seed.session.exec(select(Listing)).all()
    assert len(listings) == 2 and len({item.channel_id for item in listings}) == 2
    assert {item.variant_id for item in listings} == {seed.variant.id}


def test_jd_string_response_and_millisecond_dates_are_supported(fixture_path):
    from app.collectors.jd_union import parse_goods_query

    body = json.loads(fixture_path("jd_goods_query.json").read_text())[
        "jd_union_open_goods_query_responce"
    ]["queryResult"]
    goods = body["data"]["list"]
    goods[0]["couponInfo"]["couponList"][0]["couponEndTime"] = 1793462399000
    payload = {
        "jd_union_open_goods_query_responce": {
            "queryResult": json.dumps({"code": 200, "data": goods})
        }
    }
    raw = parse_goods_query(payload)[0]
    assert raw.coupons[0].end_time == datetime.fromtimestamp(1793462399, UTC).replace(tzinfo=None)
    assert not raw.stock_verified


def test_tbk_dates_are_parsed_and_sales_volume_is_not_stock(fixture_path):
    from app.collectors.tbk import parse_material_optional

    payload = json.loads(fixture_path("tbk_material_optional.json").read_text())
    item = payload["taobao_tbk_dg_material_optional_response"]["result_list"]["map_data"][0]
    item["coupon_start_time"], item["coupon_end_time"] = "2026-10-24", "2026-10-25"
    raw = parse_material_optional(payload)[0]
    assert raw.coupons[0].start_time == datetime(2026, 10, 23, 16)
    assert raw.coupons[0].end_time == datetime(2026, 10, 25, 15, 59, 59)
    assert not raw.stock_verified


def test_configured_smtp_uses_ssl_without_attribute_error(monkeypatch):
    from app.alerts.notify import send_smtp
    from app.config import Settings

    settings = Settings(
        _env_file=None,
        smtp_host="mail.example",
        smtp_user="u",
        smtp_password="secret",
        smtp_to="user@example.com",
    )
    monkeypatch.setattr("app.alerts.notify.get_settings", lambda: settings)
    sent = []

    class FakeSMTP:
        def login(self, *args):
            pass

        def sendmail(self, *args):
            sent.append(args)

        def quit(self):
            pass

    monkeypatch.setattr("app.alerts.notify.smtplib.SMTP_SSL", lambda *args, **kwargs: FakeSMTP())
    assert send_smtp("价格提醒") == (True, None)
    assert len(sent) == 1
