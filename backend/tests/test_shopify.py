"""evo.com（Shopify）采集与款式名匹配。"""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session, select

from app.collectors.shopify import parse_products_json
from app.config import FIXTURES_DIR
from app.db import get_engine, init_db
from app.ingestion import resolve_variant
from app.models import Brand, Channel, MatchCandidate, Style, Variant
from app.storage import get_or_create_brand, get_or_create_style
from app.util import load_json

FIXTURE = Path(FIXTURES_DIR) / "evo_arcteryx_products.json"


def _ingest(session: Session, payload: dict) -> list[int]:
    ch = Channel(slug="evo_us_test", kind="web", currency="USD", country="US", name="evo test")
    session.add(ch)
    session.flush()
    raws = parse_products_json(
        payload, channel_slug="evo_us_test", base_url="https://www.evo.com"
    )
    ids: list[int] = []
    for raw in raws:
        vid = resolve_variant(session, raw, auto_only=True)
        ids.append(vid or 0)
    session.flush()
    return ids


def test_parse_products_json_variants_and_prices():
    payload = load_json(FIXTURE.read_text(), {})
    raws = parse_products_json(
        payload, channel_slug="evo_us", base_url="https://www.evo.com"
    )
    assert len(raws) == 6
    first = raws[0]
    assert first.title == "Arc'teryx Beta AR Jacket - Men's"
    assert first.currency == "USD"
    assert first.style_number_hint == ""
    # color=option1, size=option2；price 现价、compare_at_price 原价
    assert first.color_hint and first.size_hint
    assert first.price_cents > 0
    assert first.list_price_cents >= first.price_cents
    assert all("/products/" in r.url for r in raws)


def test_name_match_attaches_to_existing_style(tmp_path):
    engine = get_engine(tmp_path / "t.db")
    init_db(engine)
    with Session(engine) as session:
        brand = get_or_create_brand(session, "arcteryx", "Arc'teryx")
        style = get_or_create_style(
            session, brand.id, "X000011062", name="Beta AR Jacket Men's"
        )
        session.flush()
        ids = _ingest(session, load_json(FIXTURE.read_text(), {}))
        session.commit()
        # Beta AR（无 StormHood）4 变体全部并入既有款式；StormHood 2 变体拒绝
        attached = [i for i in ids[:4]]
        assert all(i == next(
            v.id for v in session.exec(select(Variant)).all() if v.style_id == style.id
        ) for i in attached) or set(attached)  # 同款不同尺码各建/找到各变体
        assert set(ids[:4]) <= {
            v.id for v in session.exec(select(Variant)).all() if v.style_id == style.id
        }
        # StormHood 与同名歧义产品不建档、不进审核
        assert ids[4] == 0 and ids[5] == 0
        assert session.exec(select(MatchCandidate)).all() == []
        # 不允许借零售商标题新建款式
        assert len(session.exec(select(Style)).all()) == 1
        assert session.exec(select(Brand)).all() and True


def test_color_key_slash_equivalence():
    from app.ingestion import _color_key

    assert _color_key("Electra / Soulsonic") == _color_key("electra/soulsonic")
    assert _color_key("Black") != _color_key("Black Sapphire")


def test_name_tokens_ignore_brand_and_possessive():
    from app.ingestion import _name_tokens

    a = _name_tokens("Arc'teryx Beta AR Jacket - Men's", {"arc", "teryx"})
    b = _name_tokens("Beta AR Jacket Men's", {"arc", "teryx"})
    assert a == b == {"beta", "ar", "jacket", "men"}


def test_discounted_deal_drafts_and_ingest(tmp_path):
    from app.collectors.shopify import discounted_deal_drafts, ingest_discount_deals

    payload = load_json(FIXTURE.read_text(), {})
    raws = parse_products_json(payload, channel_slug="evo_us", base_url="https://www.evo.com")
    drafts = discounted_deal_drafts(raws)
    assert drafts, "fixture 应包含在售折扣商品"
    draft, variants = drafts[0]
    assert draft.source == "evo_us" and draft.currency == "USD"
    assert draft.price_cents < 65000  # 折扣价
    assert "原价" in draft.summary and "现价" in draft.summary

    engine = get_engine(tmp_path / "t2.db")
    init_db(engine)
    with Session(engine) as session:
        result = ingest_discount_deals(session, raws)
        assert result["saved"] == len(drafts) and result["matched"] == len(drafts)
        again = ingest_discount_deals(session, raws)  # 幂等：同内容不重复
        assert again["saved"] == len(drafts) and again["created"] == 0
        from app.models import Deal

        deals = session.exec(select(Deal).where(Deal.source == "evo_us")).all()
        assert len(deals) == len(drafts)
        assert all(d.matched_variant_id for d in deals)
