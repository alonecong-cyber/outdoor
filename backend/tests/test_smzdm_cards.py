"""smzdm 品类列表卡片解析：摘要线报（不发详情请求）的解析层测试。"""

from app.collectors.smzdm import parse_category_cards
from app.config import FIXTURES_DIR

FIXTURE = FIXTURES_DIR / "smzdm_fenlei_huwaifushi.html"


def _html() -> str:
    return FIXTURE.read_text(encoding="utf-8")


def test_cards_extracted_with_price_channel_tags():
    cards = parse_category_cards(_html())
    assert len(cards) >= 3
    first = cards[0]
    assert first.source_id == "184733680"
    assert first.url == "https://www.smzdm.com/p/184733680/"
    assert first.title.startswith("哥伦比亚")
    # 999.15元 → 99915 分（手算：999.15 × 100）
    assert first.price_cents == 99915
    assert first.currency == "CNY"
    # directlink=item.jd.com → 渠道识别为京东
    assert first.channel == "京东"
    assert first.image.startswith("https://")
    assert "360天新低" in first.tags


def test_cards_without_price_subtitle_are_skipped():
    cards = parse_category_cards(_html())
    # 指南/资讯卡（如「户外服饰指南」）没有价格副标，不得混进线报流
    assert all(card.price_cents > 0 for card in cards)


def test_card_ids_are_deduplicated():
    cards = parse_category_cards(_html())
    ids = [card.source_id for card in cards]
    assert len(ids) == len(set(ids))
