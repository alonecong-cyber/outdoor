"""smzdm 线报采集：sitemap 解析、og:title 解析、详情页解析、增量发现、目录自动生长。"""

from __future__ import annotations

import httpx
import pytest
from sqlmodel import select

from app.collectors.smzdm import (
    SmzdmFeedCollector,
    parse_category_page,
    parse_deal_page,
    parse_og_title,
    parse_sitemap,
)
from app.deals import (
    grow_variant,
    ingest_deals,
    max_source_id,
    save_deal,
)
from app.models import Brand, Deal, DealDraft, Style, Variant

# ---------- parse_og_title ----------


def test_og_title_real_format():
    """实测格式：标题 价格元_渠道优惠促销_报价_多少钱-什么值得买。"""
    title, cents, channel = parse_og_title(
        "蒂佳婷 蓝色药丸补水面膜 5片 100元_京东优惠促销_报价_多少钱-什么值得买"
    )
    assert title == "蒂佳婷 蓝色药丸补水面膜 5片"
    assert cents == 10000
    assert channel == "京东"


def test_og_title_decimal_price():
    title, cents, channel = parse_og_title(
        "凯乐石 户外冲锋衣 511 9.9元_天猫优惠促销_报价-什么值得买"
    )
    assert title == "凯乐石 户外冲锋衣 511"
    assert cents == 990
    assert channel == "天猫"


def test_og_title_no_price_keeps_whole_title():
    """信息型线报（无价格）：价格 0，标题保留，渠道从词典兜底。"""
    title, cents, channel = parse_og_title(
        "某品牌 免费抽奖 试用装_天猫超市优惠促销_报价-什么值得买"
    )
    assert title == "某品牌 免费抽奖 试用装"
    assert cents == 0
    assert channel == "天猫超市"


def test_og_title_channel_fallback_by_dictionary():
    """第二段不是"XX优惠促销"时用渠道词典扫全文。"""
    title, cents, channel = parse_og_title("某物 纸巾 20元_亚马逊海外购好价-什么值得买")
    assert cents == 2000
    assert channel == "亚马逊"


# ---------- parse_sitemap ----------


def test_parse_sitemap_filters_deal_urls_only(fixture_path):
    xml = fixture_path("smzdm_sitemap.xml").read_text(encoding="utf-8")
    entries = parse_sitemap(xml)
    ids = {i for _, i in entries}
    # /youhui/ 索引页与 /baoliao/ 不算线报
    assert ids == {184615805, 184615813, 184615802, 184615804, 184615789}
    assert all(u.startswith("https://www.smzdm.com/p/") for u, _ in entries)


# ---------- parse_deal_page ----------


def test_parse_deal_page_real_shape(fixture_path):
    html = fixture_path("smzdm_deal.html").read_text(encoding="utf-8")
    d = parse_deal_page(html, "https://www.smzdm.com/p/184615805/")
    assert d.source == "smzdm"
    assert d.source_id == "184615805"
    assert d.title == "蒂佳婷 蓝色药丸补水面膜 5片"
    assert d.price_cents == 10000
    assert d.channel == "京东"
    assert d.image.startswith("https://y.zdmimg.com/")
    # 发布时间 2026-10-24 02:59 北京时间 → UTC 18:59 前一天
    assert d.published_at is not None
    assert (d.published_at.year, d.published_at.month, d.published_at.day) == (2026, 10, 23)
    assert (d.published_at.hour, d.published_at.minute) == (18, 59)


def test_parse_deal_page_h1_fallback():
    """没有 og:title 时退到 h1；渠道词扫全文；价格未知。"""
    html = (
        "<html><body><h1 class='title'>始祖鸟 Beta LT 夹克 27910</h1>"
        "<p>京东自营</p></body></html>"
    )
    d = parse_deal_page(html, "https://www.smzdm.com/p/184615999/")
    assert d.title == "始祖鸟 Beta LT 夹克 27910"
    assert d.price_cents == 0
    assert d.channel == "京东自营"


# ---------- collector（MockTransport + 免睡眠限速） ----------


class _NoWaitLimiter:
    def wait(self, host: str) -> float:
        return 0.0

    def check(self, host: str) -> bool:
        return True


def _mock_collector(sitemap_xml: str, pages: dict[str, str], **kwargs) -> SmzdmFeedCollector:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if "sitemap" in url:
            return httpx.Response(200, text=sitemap_xml)
        if url in pages:
            return httpx.Response(200, text=pages[url])
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SmzdmFeedCollector(
        client=client, rate_limiter=_NoWaitLimiter(), sleep=lambda _s: 0, **kwargs
    )


def test_collector_incremental_fetch(fixture_path):
    xml = fixture_path("smzdm_sitemap.xml").read_text(encoding="utf-8")
    page = fixture_path("smzdm_deal.html").read_text(encoding="utf-8")
    url = "https://www.smzdm.com/p/184615813/"
    c = _mock_collector(xml, {url: page})
    try:
        # since_id = 184615805 → 只抓 813（最新优先，limit=1）
        drafts = c.collect(since_id=184615805, limit=1)
        assert [d.source_id for d in drafts] == ["184615813"]
        assert drafts[0].price_cents == 10000
    finally:
        c.close()


def test_collector_skips_failing_page(fixture_path):
    """单条详情页 404：跳过不炸整批。"""
    xml = fixture_path("smzdm_sitemap.xml").read_text(encoding="utf-8")
    page = fixture_path("smzdm_deal.html").read_text(encoding="utf-8")
    c = _mock_collector(
        xml,
        {
            "https://www.smzdm.com/p/184615813/": page,
            "https://www.smzdm.com/p/184615789/": page,
        },
    )
    try:
        # since_id=788 → 新的有 813/805/804/802/789；其中 805/804/802 404 跳过
        drafts = c.collect(since_id=184615788, limit=5)
        assert {d.source_id for d in drafts} == {"184615813", "184615789"}
    finally:
        c.close()


def test_collector_sitemap_failure_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="boom")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    c = SmzdmFeedCollector(client=client, rate_limiter=_NoWaitLimiter(), sleep=lambda _s: 0)
    with pytest.raises(httpx.HTTPStatusError):
        c.fetch_sitemap()
    c.close()


# ---------- 落库与目录自动生长 ----------


def test_save_deal_dedupe_and_update(session):

    d1 = DealDraft(
        source_id="100",
        url="https://www.smzdm.com/p/100/",
        title="始祖鸟 Beta LT 夹克 男款 27910 黑色 M 3998元",
        price_cents=399800,
        channel="淘宝",
    )
    deal, created = save_deal(session, d1)
    assert created
    # 同内容重复 → 不新建
    deal2, created2 = save_deal(session, d1)
    assert not created2 and deal2.id == deal.id
    # 价格变了 → 原地更新，不新建
    d1.price_cents = 389800
    deal3, created3 = save_deal(session, d1)
    assert not created3 and deal3.id == deal.id and deal3.price_cents == 389800
    assert len(session.exec(select(Deal)).all()) == 1


def test_grow_variant_from_deal_title(session):
    """始祖鸟线报 → 自动长出 Brand/Style/Variant 并挂上。"""
    variant_id = grow_variant(session, "始祖鸟 Beta LT 硬壳夹克 男款 27910 黑色 M 3998元")
    assert variant_id is not None
    variant = session.get(Variant, variant_id)
    style = session.get(Style, variant.style_id)
    brand = session.get(Brand, style.brand_id)
    assert brand.slug == "arcteryx" and brand.name_cn == "始祖鸟"
    assert style.style_number == "27910"
    assert variant.color == "黑色" and variant.size == "M"
    # 同款再来一条 → 关联到同一个 variant，不重复建
    assert grow_variant(session, "始祖鸟 Beta LT 27910 黑色 M 特价") == variant_id


def test_grow_variant_unknown_brand_or_style(session):
    """识别不出品牌/款号 → None，绝不猜。"""
    assert grow_variant(session, "蒂佳婷 蓝色药丸补水面膜 5片") is None  # 非户外品牌词典
    assert grow_variant(session, "始祖鸟 抓绒衣 保暖款") is None  # 品牌命中但无款号


def test_ingest_deals_grows_catalog(session):

    drafts = [
        DealDraft(
            source_id="200",
            url="https://www.smzdm.com/p/200/",
            title="始祖鸟 Beta LT 硬壳夹克 男款 27910 黑色 M 3998元",
            price_cents=399800,
            channel="淘宝",
        ),
        DealDraft(
            source_id="201",
            url="https://www.smzdm.com/p/201/",
            title="蒂佳婷 面膜 5片 100元",
            price_cents=10000,
            channel="京东",
        ),
    ]
    result = ingest_deals(session, drafts)
    assert result["saved"] == 2 and result["created"] == 2 and result["matched"] == 1
    assert max_source_id(session) == 201
    matched = session.exec(
        select(Deal).where(Deal.matched_variant_id.is_not(None))  # type: ignore[union-attr]
    ).all()
    assert len(matched) == 1 and matched[0].source_id == "200"
    assert len(session.exec(select(Variant)).all()) == 1


def test_parse_category_page(fixture_path):
    html = fixture_path("smzdm_category.html").read_text(encoding="utf-8")
    entries = parse_category_page(html)
    # 去重 + 只收 /p/<id>/；baoliao 链接不算线报
    assert [i for _u, i in entries] == [184600101, 184600099, 184599950]


def _mock_category_collector(pages: dict[str, str], **kwargs) -> SmzdmFeedCollector:
    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        if url in pages:
            return httpx.Response(200, text=pages[url])
        return httpx.Response(404, text="not found")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    return SmzdmFeedCollector(
        client=client, rate_limiter=_NoWaitLimiter(), sleep=lambda _s: 0, **kwargs
    )


def test_collect_categories_discovers_and_skips_known(fixture_path):
    cat = fixture_path("smzdm_category.html").read_text(encoding="utf-8")
    page = fixture_path("smzdm_deal.html").read_text(encoding="utf-8")
    c = _mock_category_collector(
        {
            "https://www.smzdm.com/fenlei/chongfengyi/": cat,
            "https://www.smzdm.com/p/184600101/": page,
            "https://www.smzdm.com/p/184600099/": page,
        }
    )
    try:
        # 101 已入库应跳过；099 新的抓详情
        drafts = c.collect_categories(
            ["chongfengyi"], exclude_ids={"184600101", "184599950"}, limit=5
        )
        assert [d.source_id for d in drafts] == ["184600099"]
    finally:
        c.close()


def test_collect_categories_limit_and_dead_category(fixture_path):
    """品类页 404 跳过；limit 封顶。"""
    page = fixture_path("smzdm_deal.html").read_text(encoding="utf-8")
    c = _mock_category_collector(
        {
            # 品类页正则只认双引号 href（真实页面即如此）
            "https://www.smzdm.com/fenlei/chongfengyi/": (
                '<a href="https://www.smzdm.com/p/184600101/">x</a>'
            ),
            "https://www.smzdm.com/p/184600101/": page,
        }
    )
    try:
        drafts = c.collect_categories(
            ["dead-slug", "chongfengyi"], exclude_ids=set(), limit=1
        )
        assert [d.source_id for d in drafts] == ["184600101"]
    finally:
        c.close()
