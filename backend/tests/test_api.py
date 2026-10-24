"""API 集成测试：/health、pricing 三件套、catalog、订阅 CRUD、事件重发。"""

from __future__ import annotations

from app.storage import add_price_snapshot


class TestHealth:
    def test_health(self, client):
        r = client.get("/api/health")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["version"]


class TestQuote:
    def test_quote_from_body_promos(self, client):
        # 手算：399800 − 店铺券 30000（满 300000 达标）= 369800；平台券 10000 → 359800
        r = client.post(
            "/api/pricing/quote",
            json={
                "base_price_cents": 399800,
                "promos": [
                    {"id": "s1", "kind": "store_coupon", "name": "店铺券",
                     "threshold_cents": 300000, "amount_cents": 30000},
                    {"id": "p1", "kind": "platform_coupon", "name": "平台券",
                     "amount_cents": 10000},
                ],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["base_price_cents"] == 399800
        assert body["paid_now_cents"] == 359800
        assert body["effective_cents"] == 359800
        assert body["applied_promo_ids"] == ["s1", "p1"]

    def test_quote_from_listing_db_promos(self, client, seed):
        # listing 399800 + 库里平台级规则：店铺券满 300000 减 30000
        from app.models import PromoRule

        seed.session.add(
            PromoRule(
                name="满3000减300",
                kind="store_coupon",
                channel_id=None,
                threshold_cents=300000,
                amount_cents=30000,
                active=True,
                source="test",
            )
        )
        seed.session.commit()
        listing = seed.add_listing(seed.jd, external_id="jd-q", price_cents=399800)
        r = client.post("/api/pricing/quote", json={"listing_id": listing.id})
        assert r.status_code == 200
        assert r.json()["paid_now_cents"] == 369800

    def test_quote_listing_not_found(self, client):
        assert client.post("/api/pricing/quote", json={"listing_id": 999}).status_code == 404

    def test_quote_missing_base(self, client):
        assert client.post("/api/pricing/quote", json={}).status_code == 422


class TestOverseas:
    def test_overseas_acceptance(self, client):
        # PRD 验收样例：$450 25% off + 10% 码 + 8% 返现 + 7.1 汇率 + ¥220 转运 → 2635.42
        r = client.post(
            "/api/pricing/overseas",
            json={
                "usd_price": 450.0,
                "discount": 0.25,
                "coupon_code": 0.10,
                "cashback": 0.08,
                "rate": 7.1,
                "transfer_fee_cny": 220.0,
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["landed_cny"] == 2635.42
        assert body["tax_cny"] == 431.33
        assert body["cashback_cny"] == 172.53


class TestFiller:
    def test_filler_exact(self, client):
        # 手算：门槛 300000，{a=100000, d=200000} 恰好 300000
        r = client.post(
            "/api/pricing/filler",
            json={
                "threshold_cents": 300000,
                "items": [
                    {"id": "a", "price_cents": 100000},
                    {"id": "b", "price_cents": 150000},
                    {"id": "c", "price_cents": 80000},
                    {"id": "d", "price_cents": 200000},
                ],
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert body["total_extra_cents"] == 300000
        assert sorted(body["item_ids"]) == ["a", "d"]

    def test_filler_impossible(self, client):
        r = client.post(
            "/api/pricing/filler",
            json={"threshold_cents": 1000000,
                  "items": [{"id": "a", "price_cents": 100}]},
        )
        assert r.status_code == 200
        assert r.json()["ok"] is False


class TestCatalog:
    def test_variants_list_and_filter(self, client, seed):
        r = client.get("/api/variants")
        assert r.status_code == 200
        items = r.json()
        assert len(items) == 1
        assert items[0]["style_number"] == "27910"
        # brand 过滤命中
        assert len(client.get("/api/variants", params={"brand": "arcteryx"}).json()) == 1
        # 不存在的品牌为空
        assert client.get("/api/variants", params={"brand": "nope"}).json() == []

    def test_variant_detail_with_channel_price(self, client, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-d", price_cents=399800)
        r = client.get(f"/api/variants/{seed.variant.id}")
        assert r.status_code == 200
        body = r.json()
        assert body["color"] == "Black" and body["size"] == "M"
        chan = body["channels"][0]
        assert chan["listing_id"] == listing.id
        assert chan["price_cents"] == 399800
        assert chan["history"][0]["price_cents"] == 399800

    def test_variant_404(self, client):
        assert client.get("/api/variants/999").status_code == 404

    def test_listing_history(self, client, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-h", price_cents=300000)
        add_price_snapshot(seed.session, listing_id=listing.id, price_cents=280000)
        seed.session.commit()  # flush 不够：API 走另一个 session，只见已提交数据
        r = client.get(f"/api/listings/{listing.id}/history")
        assert r.status_code == 200
        assert [h["price_cents"] for h in r.json()] == [300000, 280000]


class TestSubscriptions:
    def test_crud(self, client, seed):
        r = client.post(
            "/api/alerts/subscriptions",
            json={"variant_id": seed.variant.id, "target_price_cents": 400000,
                  "kinds": ["price_below"]},
        )
        assert r.status_code == 200
        sub = r.json()
        assert sub["id"] > 0 and sub["kinds"] == ["price_below"]

        subs = client.get("/api/alerts/subscriptions").json()
        assert len(subs) == 1

        assert client.delete(f"/api/alerts/subscriptions/{sub['id']}").status_code == 204
        assert client.get("/api/alerts/subscriptions").json() == []

    def test_create_subscription_variant_404(self, client):
        r = client.post(
            "/api/alerts/subscriptions",
            json={"variant_id": 999},
        )
        assert r.status_code == 404


class TestEvents:
    def test_list_and_resend(self, client, seed, monkeypatch):
        # 清空通知配置，手动重发走"无可用渠道"分支但事件要能查到
        from app.config import get_settings

        get_settings.cache_clear()
        for key in ("TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID", "WECOM_WEBHOOK", "SMTP_HOST"):
            monkeypatch.setenv(key, "")

        from app.alerts.history import evaluate_listing

        listing = seed.add_listing(seed.jd, external_id="jd-e", price_cents=399800)
        from app.models import AlertSubscription
        from app.util import dump_json

        seed.session.add(
            AlertSubscription(
                variant_id=seed.variant.id,
                target_price_cents=400000,
                kinds_json=dump_json(["price_below"]),
            )
        )
        seed.session.commit()
        evaluate_listing(seed.session, listing, 399800)
        seed.session.commit()  # 同上：事件要提交后 API 才可见

        events = client.get("/api/alerts/events").json()
        assert len(events) == 1
        assert events[0]["kind"] == "price_below"
        assert events[0]["payload"]["price_cents"] == 399800

        unsent = client.get("/api/alerts/events", params={"unsent": True}).json()
        assert len(unsent) == 1

        r = client.post(f"/api/alerts/events/{events[0]['id']}/send")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is False  # 无渠道配置
        assert "通知渠道" in body["error"]

    def test_resend_404(self, client):
        assert client.post("/api/alerts/events/999/send").status_code == 404
