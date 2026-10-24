"""提醒测试：历史新低判定、24h 去重、订阅评估、通知发送。"""

from __future__ import annotations

from datetime import timedelta

from app.alerts.history import evaluate_listing, is_new_low, recent_alert
from app.alerts.notify import format_alert, send_alert
from app.models import AlertSubscription, RawListing
from app.storage import add_price_snapshot, save_raw_listing
from app.util import dump_json, utc_now


def _listing_with_history(seed, rows):
    """建 listing 并按时间序写入 (days_ago, price_cents) 快照。

    走 save_raw_listing 而非 seed.add_listing：后者自动写一条"当前"快照，
    会和历史快照互相触发"变化才写"去重。
    """
    raw = RawListing(
        source="test",
        channel_slug=seed.jd.slug,
        external_id=f"hist-{id(rows)}",
        url="https://example.com/hist",
        title="Beta LT",
        price_cents=rows[0][1],
        currency=seed.jd.currency,
    )
    listing, _ = save_raw_listing(
            seed.session, raw=raw, channel_id=seed.jd.id, variant_id=seed.variant.id
        )
    base = utc_now()
    for days_ago, price in rows:
        add_price_snapshot(
            seed.session, listing_id=listing.id, price_cents=price,
            ts=base - timedelta(days=days_ago),
        )
    return listing, base


class TestIsNewLow:
    def test_new_low_with_long_history(self, seed):
        # 手算：20 天前 5000、10 天前 4800，历史 ≥14 天；现价 4700 < 4800 → 新低
        listing, base = _listing_with_history(seed, [(20, 500000), (10, 480000)])
        assert is_new_low(seed.session, listing.id, 470000, now=base)

    def test_not_low_when_price_higher(self, seed):
        listing, base = _listing_with_history(seed, [(20, 500000), (10, 480000)])
        assert not is_new_low(seed.session, listing.id, 485000, now=base)

    def test_short_history_not_new_low(self, seed):
        # 手算：第一条快照距今 5 天 < 14 天 → 历史太短，不报新低（防促销假低）
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=500000)
        base = utc_now()
        add_price_snapshot(
            seed.session, listing_id=listing.id, price_cents=500000,
            ts=base - timedelta(days=5),
        )
        assert not is_new_low(seed.session, listing.id, 100000, now=base)

    def test_new_low_excludes_snapshot_just_written(self, seed):
        # 回归：调度器先写快照再评估。不传 before 时，刚写入的当前价落进
        # ts<now 窗口，min 含自己 → 新低永远 False。传 before=当前快照 ts 才对。
        listing, base = _listing_with_history(seed, [(20, 500000), (10, 480000)])
        now = base + timedelta(seconds=1)
        snap = add_price_snapshot(
            seed.session, listing_id=listing.id, price_cents=470000, ts=now
        )
        assert snap is not None
        assert not is_new_low(seed.session, listing.id, 470000, now=now + timedelta(seconds=1))
        assert is_new_low(
            seed.session, listing.id, 470000, now=now + timedelta(seconds=1), before=snap.ts
        )


class TestEvaluateListing:
    def _subscribe(self, seed, target=460000, kinds=None):
        sub = AlertSubscription(
            variant_id=seed.variant.id,
            target_price_cents=target,
            kinds_json=dump_json(kinds or ["price_below"]),
            channel="jd",
            destination="",
        )
        seed.session.add(sub)
        seed.session.commit()
        return sub

    def test_price_below_creates_event(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=450000)
        self._subscribe(seed)
        events = evaluate_listing(seed.session, listing, 450000)
        assert len(events) == 1
        assert events[0].kind == "price_below"

    def test_dedupe_within_24h(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=450000)
        self._subscribe(seed)
        first = evaluate_listing(seed.session, listing, 450000)
        second = evaluate_listing(seed.session, listing, 450000)
        assert len(first) == 1 and len(second) == 0  # 24h 内不重复

    def test_new_low_kind(self, seed):
        listing, base = _listing_with_history(seed, [(20, 500000), (10, 480000)])
        self._subscribe(seed, kinds=["new_low"])
        events = evaluate_listing(seed.session, listing, 470000, now=base)
        assert len(events) == 1
        assert events[0].kind == "new_low"

    def test_recent_alert_flag(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=450000)
        sub = self._subscribe(seed)
        now = utc_now()
        evaluate_listing(seed.session, listing, 450000, now=now)
        assert recent_alert(seed.session, sub.id, "price_below", now=now)
        assert not recent_alert(
            seed.session, sub.id, "price_below", now=now + timedelta(hours=25)
        )


class TestNotify:
    def test_format_alert_readable(self):
        text = format_alert(
            {"title": "Beta LT", "price_cents": 369800, "kind": "price_below",
             "target_price_cents": 400000}
        )
        assert "Beta LT" in text and "3698" in text

    def test_send_alert_no_channel_configured(self, monkeypatch):
        # 无任何渠道配置 → 明确报错而不是静默
        from app.config import get_settings

        get_settings.cache_clear()
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "")
        monkeypatch.setenv("TELEGRAM_CHAT_ID", "")
        monkeypatch.setenv("WECOM_WEBHOOK", "")
        monkeypatch.setenv("SMTP_HOST", "")
        ok, err = send_alert({"title": "x", "price_cents": 1, "kind": "price_below"})
        assert not ok
        assert err and "通知渠道" in err
