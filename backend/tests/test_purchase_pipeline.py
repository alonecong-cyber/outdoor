"""购买链路回归：真实采集形态进入同规格报价、优惠历史与提醒，全部离线。"""

from datetime import timedelta

from sqlmodel import select

from app.models import (
    AlertSubscription,
    CouponInfo,
    Deal,
    DealDraft,
    Listing,
    MatchCandidate,
    PriceSnapshot,
    PromoRule,
    RawListing,
    Variant,
)
from app.scheduler import collect_and_store
from app.storage import add_price_snapshot, price_history, save_raw_listing
from app.util import dump_json, utc_now


def raw_offer(**overrides):
    values = {
        "source": "jd_union",
        "channel_slug": "jd",
        "external_id": "sku-27910-black-m",
        "url": "https://item.jd.com/123.html",
        "title": "始祖鸟 Beta LT 27910 Black M",
        "brand_hint": "arcteryx",
        "style_number_hint": "27910",
        "color_hint": "Black",
        "size_hint": "M",
        "price_cents": 10000,
    }
    return RawListing(**(values | overrides))


def test_collector_creates_confirmed_spec_scoped_coupon_and_quote(seed, client):
    # 手算：标价100元，专属满90减20券 → 当下实付/到手80元。
    raw = raw_offer(coupons=[CouponInfo(name="满90减20", amount_cents=2000, threshold_cents=9000)])
    result = collect_and_store(seed.session, [raw], channel_id=seed.jd.id)
    assert result.errors == []
    listing = seed.session.exec(select(Listing)).one()
    assert listing.variant_id == seed.variant.id
    rules = seed.session.exec(select(PromoRule).where(PromoRule.active)).all()
    assert len(rules) == 1
    assert str(listing.id) in rules[0].scope_json
    response = client.get(f"/api/variants/{seed.variant.id}")
    assert response.status_code == 200
    channel = response.json()["channels"][0]
    assert channel["price_cents"] == 10000
    assert channel["effective_cents"] == 8000
    assert channel["paid_now_cents"] == 8000
    assert channel["price_status"] == "verified"
    assert channel["steps"][0]["delta_cents"] == -2000


def test_missing_size_stays_in_review_not_attached_to_another_size(seed):
    raw = raw_offer(title="始祖鸟 27910 Black", size_hint="")
    collect_and_store(seed.session, [raw], channel_id=seed.jd.id)
    listing = seed.session.exec(select(Listing)).one()
    assert listing.variant_id is None
    assert seed.session.exec(select(MatchCandidate)).first() is not None


def test_unseen_complete_spec_can_create_variant_without_merging_sizes(seed):
    collect_and_store(seed.session, [raw_offer(size_hint="L")], channel_id=seed.jd.id)
    listing = seed.session.exec(select(Listing)).one()
    assert listing.variant_id != seed.variant.id
    assert seed.session.get(Variant, listing.variant_id).size == "L"


def test_coupon_only_change_records_effective_history_and_alerts(seed):
    # 手算：标价始终100元；首次无券100元，新增20元券后80元，达到85元目标。
    first = raw_offer()
    collect_and_store(seed.session, [first], channel_id=seed.jd.id)
    sub = AlertSubscription(
        variant_id=seed.variant.id,
        target_price_cents=8500,
        kinds_json=dump_json(["price_below"]),
    )
    seed.session.add(sub)
    seed.session.commit()
    second = raw_offer(
        collected_at=utc_now() + timedelta(seconds=1),
        coupons=[CouponInfo(name="20元券", amount_cents=2000)],
    )
    result = collect_and_store(seed.session, [second], channel_id=seed.jd.id)
    assert result.new_snapshots == 1
    assert len(result.alerts) == 1
    assert '"price_cents": 8000' in result.alerts[0].payload_json
    snaps = seed.session.exec(select(PriceSnapshot).order_by(PriceSnapshot.ts)).all()
    assert [s.price_cents for s in snaps] == [10000, 10000]
    assert [s.effective_cents for s in snaps] == [10000, 8000]
    assert len(seed.session.exec(select(PromoRule).where(PromoRule.active)).all()) == 1


def test_unchanged_offer_evaluates_new_subscription_without_duplicate_snapshot(seed):
    raw = raw_offer()
    collect_and_store(seed.session, [raw], channel_id=seed.jd.id)
    seed.session.add(
        AlertSubscription(
            variant_id=seed.variant.id,
            target_price_cents=10000,
            kinds_json=dump_json(["price_below"]),
        )
    )
    seed.session.commit()
    result = collect_and_store(seed.session, [raw], channel_id=seed.jd.id)
    assert result.new_snapshots == 0
    assert len(result.alerts) == 1


def test_disabled_subscription_and_out_of_stock_offer_do_not_alert(seed):
    seed.session.add(
        AlertSubscription(
            variant_id=seed.variant.id,
            target_price_cents=20000,
            active=False,
            kinds_json=dump_json(["price_below"]),
        )
    )
    seed.session.commit()
    result = collect_and_store(seed.session, [raw_offer()], channel_id=seed.jd.id)
    assert result.alerts == []
    sub = seed.session.exec(select(AlertSubscription)).one()
    sub.active = True
    seed.session.add(sub)
    seed.session.commit()
    result = collect_and_store(seed.session, [raw_offer(in_stock=False)], channel_id=seed.jd.id)
    assert result.alerts == []


def test_long_unchanged_price_is_carried_into_window_and_new_low(seed):
    from app.alerts.history import is_new_low

    # 手算：100天前500元，直到今天才降499元；90天窗口仍承接500元，故为新低。
    raw = raw_offer(collected_at=utc_now() - timedelta(days=100), price_cents=50000)
    listing, _ = save_raw_listing(
        seed.session, raw=raw, channel_id=seed.jd.id, variant_id=seed.variant.id
    )
    add_price_snapshot(seed.session, listing_id=listing.id, price_cents=50000, ts=raw.collected_at)
    assert len(price_history(seed.session, listing.id, days=90)) == 1
    assert is_new_low(seed.session, listing.id, 49900)


def test_persistent_scheduler_uses_serializable_module_functions(tmp_path, monkeypatch):
    from app.config import get_settings
    from app.scheduler import build_scheduler

    get_settings.cache_clear()
    monkeypatch.setenv("DB_PATH", str(tmp_path / "scheduler.db"))
    try:
        scheduler = build_scheduler(start_now=False)
        for job in scheduler.get_jobs():
            assert "<locals>" not in job.func_ref
            job.misfire_grace_time = 60
            job.coalesce = True
            job.max_instances = 1
            job.next_run_time = None
            assert job.__getstate__()["func"]
        scheduler.start(paused=True)
        assert scheduler.running
        scheduler.shutdown(wait=False)
    finally:
        get_settings.cache_clear()


def test_reported_price_is_not_a_verified_catalog_minimum(client, session):
    from app.deals import ingest_deals

    ingest_deals(
        session,
        [
            DealDraft(
                source_id="report-only",
                title="始祖鸟 抓绒衣 保暖款",
                price_cents=10000,
                summary="会员领券后100元，活动条件以原文为准。",
            )
        ],
    )
    item = client.get("/api/variants").json()[0]
    assert item["min_price_cents"] is None
    assert item["reported_min_price_cents"] == 10000
    assert item["match_status"] == "needs_review"
    deal = client.get("/api/deals").json()[0]
    detail = client.get(f"/api/deals/{deal['id']}").json()
    assert detail["summary"] == "会员领券后100元，活动条件以原文为准。"
    assert detail["price_status"] == "reported"
    assert detail["channels"] == []
    assert detail["purchase_notes"]


def test_summary_only_change_updates_existing_report(session):
    from app.deals import save_deal

    draft = DealDraft(
        source_id="change", title="始祖鸟 抓绒衣", price_cents=10000, summary="原条件"
    )
    deal, _ = save_deal(session, draft)
    draft.summary = "改为会员专享，须另付运费"
    updated, created = save_deal(session, draft)
    assert not created and updated.id == deal.id
    assert updated.summary == "改为会员专享，须另付运费"
    assert updated.last_checked_at is not None
    assert len(session.exec(select(Deal)).all()) == 1


def test_stale_offer_is_not_current_minimum_or_subscribable(seed, client):
    raw = raw_offer(collected_at=utc_now() - timedelta(days=3))
    collect_and_store(seed.session, [raw], channel_id=seed.jd.id)
    item = client.get(f"/api/variants/{seed.variant.id}").json()
    assert item["channels"][0]["price_status"] == "stale"
    assert not item["can_subscribe"]
    row = client.get("/api/variants").json()[0]
    assert row["min_price_cents"] is None


def test_coupon_expiry_recomputes_history_without_price_collection(seed, monkeypatch):
    from app.scheduler import refresh_quotes

    # 手算：100元−20元券=80元；券到期后恢复100元，不需伪造新的标价。
    end = utc_now() + timedelta(minutes=1)
    collect_and_store(
        seed.session,
        [raw_offer(coupons=[CouponInfo(name="限时20元券", amount_cents=2000, end_time=end)])],
        channel_id=seed.jd.id,
    )
    monkeypatch.setattr("app.scheduler.utc_now", lambda: end + timedelta(minutes=1))
    result = refresh_quotes(seed.session)
    assert result["snapshots"] == 1
    snaps = seed.session.exec(select(PriceSnapshot).order_by(PriceSnapshot.ts)).all()
    assert [s.price_cents for s in snaps] == [10000, 10000]
    assert [s.effective_cents for s in snaps] == [8000, 10000]


def test_coupons_disappearing_from_source_are_deactivated(seed):
    collect_and_store(
        seed.session, [raw_offer(coupons=[CouponInfo(amount_cents=2000)])], channel_id=seed.jd.id
    )
    collect_and_store(
        seed.session,
        [raw_offer(collected_at=utc_now() + timedelta(seconds=1))],
        channel_id=seed.jd.id,
    )
    assert not seed.session.exec(select(PromoRule).where(PromoRule.active)).all()
    snaps = seed.session.exec(select(PriceSnapshot).order_by(PriceSnapshot.ts)).all()
    assert [s.effective_cents for s in snaps] == [8000, 10000]


def test_foreign_currency_never_becomes_a_cny_minimum(seed, client):
    collect_and_store(seed.session, [raw_offer(price_cents=30000)], channel_id=seed.jd.id)
    collect_and_store(
        seed.session,
        [
            raw_offer(
                source="web",
                channel_slug=seed.us.slug,
                price_cents=1000,
                currency="USD",
            )
        ],
        channel_id=seed.us.id,
    )
    item = client.get("/api/variants").json()[0]
    assert item["min_price_cents"] == 30000 and item["currency"] == "CNY"
    detail = client.get(f"/api/variants/{seed.variant.id}").json()
    assert {c["currency"] for c in detail["channels"]} == {"CNY", "USD"}


def test_failed_record_rolls_back_without_removing_batch_success(seed):
    bad = raw_offer(external_id="invalid-negative", price_cents=-1)
    result = collect_and_store(seed.session, [bad, raw_offer()], channel_id=seed.jd.id)
    assert result.saved == 1 and len(result.errors) == 1
    ids = [item.external_id for item in seed.session.exec(select(Listing)).all()]
    assert ids == [raw_offer().external_id]
    assert len(seed.session.exec(select(PriceSnapshot)).all()) == 1


def test_aware_collection_time_is_normalized_before_freshness_check(seed, client):
    from datetime import UTC, datetime

    result = collect_and_store(
        seed.session, [raw_offer(collected_at=datetime.now(UTC))], channel_id=seed.jd.id
    )
    assert result.errors == []
    assert client.get(f"/api/variants/{seed.variant.id}").json()["can_subscribe"]


def test_api_refuses_subscriptions_without_verified_offers(seed, client):
    response = client.post(
        "/api/alerts/subscriptions",
        json={
            "variant_id": seed.variant.id,
            "target_price_cents": 10000,
        },
    )
    assert response.status_code == 409
    collect_and_store(seed.session, [raw_offer()], channel_id=seed.jd.id)
    assert (
        client.post(
            "/api/alerts/subscriptions",
            json={
                "variant_id": seed.variant.id,
                "target_price_cents": -1,
            },
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/alerts/subscriptions",
            json={
                "variant_id": seed.variant.id,
                "target_price_cents": 10000,
                "kinds": ["not-supported"],
            },
        ).status_code
        == 422
    )


def test_report_recheck_updates_expiration_without_duplicate_record(session):
    from app.deals import known_source_ids, save_deal

    draft = DealDraft(
        source_id="recheck", title="始祖鸟 抓绒衣", checked_at=utc_now() - timedelta(hours=7)
    )
    deal, _ = save_deal(session, draft)
    assert "recheck" in known_source_ids(session)
    assert "recheck" not in known_source_ids(session, fresh_only=True)
    draft.expired = True
    draft.checked_at = utc_now()
    updated, created = save_deal(session, draft)
    assert not created and updated.id == deal.id and updated.expired
    assert "recheck" in known_source_ids(session, fresh_only=True)


def test_status_api_exposes_real_counts_without_credentials(client, seed, monkeypatch):
    from app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("JD_UNION_APP_KEY", "")
    monkeypatch.setenv("JD_UNION_SECRET_KEY", "")
    try:
        data = client.get("/api/status").json()
        assert not data["scheduler_enabled"]
        assert data["counts"]["verified_offers"] == 0
        jd = next(s for s in data["sources"] if s["source"] == "jd_union")
        assert not jd["configured"]
    finally:
        get_settings.cache_clear()
