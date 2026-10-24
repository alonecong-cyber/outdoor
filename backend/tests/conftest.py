"""pytest 公共夹具：临时 SQLite + FastAPI TestClient + 种子数据。"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.api.deps import get_db
from app.config import FIXTURES_DIR
from app.db import get_engine, init_db
from app.main import app
from app.storage import (
    add_price_snapshot,
    get_or_create_brand,
    get_or_create_channel,
    get_or_create_style,
    get_or_create_variant,
    save_raw_listing,
)


@pytest.fixture()
def engine(tmp_path):
    eng = get_engine(tmp_path / "test.db")
    init_db(eng)
    return eng


@pytest.fixture()
def session(engine) -> Generator[Session, None, None]:
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def client(engine) -> Generator[TestClient, None, None]:
    def _override_get_db():
        with Session(engine) as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    app.state.db_engine = engine
    app.state.disable_scheduler = True
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.clear()
        del app.state.db_engine
        del app.state.disable_scheduler


@pytest.fixture()
def fixture_path():
    def _p(name: str):
        return FIXTURES_DIR / name

    return _p


class SeedData:
    """一套最小闭环种子：品牌→款→Variant→渠道→listing→快照。"""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.brand = get_or_create_brand(
            session, "arcteryx", "Arc'teryx", name_cn="始祖鸟", aliases=["始祖鸟"]
        )
        self.style = get_or_create_style(
            session, self.brand.id, "27910", name="Beta LT Jacket", category="shell", gender="men"
        )
        self.variant = get_or_create_variant(session, self.style.id, "Black", "M")
        self.jd = get_or_create_channel(session, "jd", kind="marketplace", currency="CNY")
        self.taobao = get_or_create_channel(session, "taobao", kind="marketplace", currency="CNY")
        self.us = get_or_create_channel(
            session, "official-us", kind="official", currency="USD", country="US"
        )
        session.commit()

    def add_listing(self, channel, *, external_id: str, price_cents: int, title: str = "Beta LT"):
        from app.models import RawListing  # 复用真实模型做桩

        raw = RawListing(
            source="test",
            channel_slug=channel.slug,
            external_id=external_id,
            url=f"https://example.com/{external_id}",
            title=title,
            price_cents=price_cents,
            currency=channel.currency,
        )
        listing, _ = save_raw_listing(
            self.session,
            raw=raw,
            channel_id=channel.id,
            variant_id=self.variant.id,
        )
        add_price_snapshot(
            self.session,
            listing_id=listing.id,
            price_cents=price_cents,
            currency=channel.currency,
        )
        self.session.commit()
        return listing


@pytest.fixture()
def seed(session) -> SeedData:
    return SeedData(session)
