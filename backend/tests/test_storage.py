"""存储层测试：upsert、变化才写快照、历史查询。"""

from __future__ import annotations

from datetime import timedelta

from app.storage import (
    add_price_snapshot,
    get_or_create_brand,
    last_snapshot,
    lowest_price,
    price_history,
    save_raw_listing,
)
from app.util import utc_now


class TestGetOrCreate:
    def test_brand_idempotent(self, session):
        b1 = get_or_create_brand(session, "arcteryx", "Arc'teryx", name_cn="始祖鸟")
        b2 = get_or_create_brand(session, "arcteryx", "Arc'teryx")
        assert b1.id == b2.id


class TestSaveRawListing:
    def test_create_then_update(self, seed):
        listing, created = save_raw_listing(
            seed.session,
            raw=_raw("jd-1", "Beta LT"),
            channel_id=seed.jd.id,
            variant_id=seed.variant.id,
        )
        assert created
        listing2, created2 = save_raw_listing(
            seed.session,
            raw=_raw("jd-1", "Beta LT 降价版"),
            channel_id=seed.jd.id,
            variant_id=seed.variant.id,
        )
        assert not created2
        assert listing2.id == listing.id
        assert listing2.title == "Beta LT 降价版"

    def test_same_channel_different_external_ids(self, seed):
        l1, c1 = save_raw_listing(
            seed.session, raw=_raw("jd-1", "a"), channel_id=seed.jd.id, variant_id=None
        )
        l2, c2 = save_raw_listing(
            seed.session, raw=_raw("jd-2", "b"), channel_id=seed.jd.id, variant_id=None
        )
        assert c1 and c2 and l1.id != l2.id


class TestSnapshots:
    def test_change_only_writes(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=399800)
        # 价格库存都没变 → 不写新快照
        assert (
            add_price_snapshot(
                seed.session, listing_id=listing.id, price_cents=399800, in_stock=True
            )
            is None
        )
        # 价格变了 → 写
        snap = add_price_snapshot(
            seed.session, listing_id=listing.id, price_cents=369800, in_stock=True
        )
        assert snap is not None and snap.price_cents == 369800
        # 库存变了 → 也写
        snap2 = add_price_snapshot(
            seed.session, listing_id=listing.id, price_cents=369800, in_stock=False
        )
        assert snap2 is not None and not snap2.in_stock
        history = price_history(seed.session, listing.id)
        assert [s.price_cents for s in history] == [399800, 369800, 369800]

    def test_last_and_lowest(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=500000)
        add_price_snapshot(seed.session, listing_id=listing.id, price_cents=300000)
        add_price_snapshot(seed.session, listing_id=listing.id, price_cents=400000)
        last = last_snapshot(seed.session, listing.id)
        assert last.price_cents == 400000
        assert lowest_price(seed.session, listing.id) == 300000

    def test_history_excludes_future_window_before(self, seed):
        listing = seed.add_listing(seed.jd, external_id="jd-1", price_cents=500000)
        base = utc_now()
        add_price_snapshot(
            seed.session,
            listing_id=listing.id,
            price_cents=200000,
            ts=base - timedelta(days=1),
        )
        # before=base 时，刚写入的这条（ts=base-1d）在窗口内
        assert lowest_price(seed.session, listing.id, before=base) == 200000


def _raw(external_id: str, title: str):
    from app.models import RawListing

    return RawListing(
        source="test",
        channel_slug="jd",
        external_id=external_id,
        url=f"https://item.jd.com/{external_id}.html",
        title=title,
        price_cents=0,
    )
