"""采集器测试：fixtures 解析、签名向量、退避、robots、商品页解析。"""

from __future__ import annotations

import json

import httpx
import pytest

from app.collectors.avantlink import AvantLinkClient, parse_product_search
from app.collectors.base import CollectorError, fetch_with_backoff, make_http_client
from app.collectors.jd_union import JDUnionClient, parse_goods_query
from app.collectors.tbk import TBKClient, parse_material_optional
from app.collectors.web_product import (
    HostRateLimiter,
    WebProductCollector,
    fetch_product,
    looks_like_block_or_login,
    parse_jsonld_product,
    parse_product_page,
    parse_product_variants,
    robots_allows,
)


class TestJdUnion:
    def test_sign_vectors(self):
        # bash 预计算向量：md5("secret" + "keyword"+"x" + "secret").upper()
        assert JDUnionClient.sign({"keyword": "x"}, "secret") == (
            "A2B70DBB84B822C71DC263EAC9043C4C"
        )
        assert JDUnionClient.sign({"a": "1", "b": "2"}, "secret") == (
            "EF16F26C937CF52AE6F85DF2FD08B24A"
        )

    def test_parse_fixture(self, fixture_path):
        import json

        payload = json.loads(fixture_path("jd_goods_query.json").read_text())
        listings = parse_goods_query(payload)
        assert len(listings) == 2
        first = listings[0]
        assert first.external_id == "100012345"
        assert first.price_cents == 399800
        assert first.list_price_cents == 379810
        assert first.currency == "CNY"
        assert first.in_stock
        assert len(first.coupons) == 2
        # 满 3000 减 300 那张券
        big = max(first.coupons, key=lambda c: c.amount_cents)
        assert big.amount_cents == 30000 and big.threshold_cents == 300000

    def test_missing_credentials(self):
        with pytest.raises(PermissionError):
            JDUnionClient(app_key="", secret="").query_goods("始祖鸟")


class TestTbk:
    def test_parse_fixture(self, fixture_path):
        import json

        payload = json.loads(fixture_path("tbk_material_optional.json").read_text())
        listings = parse_material_optional(payload)
        assert len(listings) == 2
        first = listings[0]
        assert first.price_cents == 239900
        assert first.list_price_cents == 299900
        assert first.coupons and first.coupons[0].amount_cents == 20000
        assert first.coupons[0].threshold_cents == 200000
        assert first.image.startswith("https://")

    def test_missing_credentials(self):
        with pytest.raises(PermissionError):
            TBKClient(app_key="", secret="").material_optional("冲锋衣")


class TestAvantLink:
    def test_parse_fixture(self, fixture_path):
        xml = fixture_path("avantlink_products.xml").read_text()
        listings = parse_product_search(xml)
        assert len(listings) == 2
        first = listings[0]
        assert first.price_cents == 44925  # Sale_Price 优先
        assert first.currency == "USD"
        assert first.in_stock
        assert not listings[1].in_stock  # Out of Stock

    def test_missing_credentials(self):
        with pytest.raises(PermissionError):
            AvantLinkClient(affiliate_id="", website_id="").product_search("jacket")


class TestHttpClientFactory:
    def test_make_http_client_tolerates_ipv6_no_proxy(self, monkeypatch):
        # 本机 Clash 场景：no_proxy 含 "[::1]" 时 httpx 0.28 直接 InvalidURL
        monkeypatch.setenv("no_proxy", "localhost,127.0.0.1,::1,[::1]")
        monkeypatch.setenv("http_proxy", "http://127.0.0.1:7890")
        client = make_http_client(timeout=30)
        assert client is not None
        client.close()


class TestBackoff:
    def test_retries_then_success(self):
        calls, sleeps = [], []

        def flaky():
            calls.append(1)
            if len(calls) < 3:
                raise ConnectionError("boom")
            return "ok"

        assert fetch_with_backoff(flaky, base_delay=1, sleep=sleeps.append, jitter=0) == "ok"
        assert len(calls) == 3
        assert len(sleeps) == 2  # 指数退避 1s、2s

    def test_exhausted_raises_collector_error(self):
        def always_fail():
            raise ConnectionError("down")

        with pytest.raises(CollectorError):
            fetch_with_backoff(always_fail, max_retries=2, base_delay=1, sleep=lambda s: None)


class TestHostRateLimiter:
    def test_min_interval(self):
        clock = {"t": 100.0}
        slept = []

        def fake_sleep(s):
            slept.append(s)

        rl = HostRateLimiter(min_interval=10, clock=lambda: clock["t"], sleep=fake_sleep)
        assert rl.wait("a.com") == 0  # 首次不等待
        waited = rl.wait("a.com")  # 同一时刻再来 → 等满 10 秒
        assert waited == pytest.approx(10)
        assert slept == [pytest.approx(10)]

    def test_check_after_interval(self):
        clock = {"t": 100.0}
        rl = HostRateLimiter(min_interval=10, clock=lambda: clock["t"], sleep=lambda s: None)
        rl.wait("a.com")
        assert not rl.check("a.com")
        clock["t"] += 10
        assert rl.check("a.com")

    def test_different_hosts_independent(self):
        rl = HostRateLimiter(min_interval=10, clock=lambda: 0.0, sleep=lambda s: None)
        rl.wait("a.com")
        assert rl.check("b.com")  # 不同域名互不影响


class TestRobots:
    def test_mixed_robots_blocks_our_bot(self, fixture_path):
        # robots_mixed.txt："*" 组只禁 /cart 等，但 OutdoorDealBot 组 Disallow /
        # → 按 RFC 9309 选最长匹配组：本 bot 在整站被禁，即使其他 UA 可抓商品页
        body = fixture_path("robots_mixed.txt").read_text()
        assert not robots_allows("https://brand.com/products/beta-lt", body)
        assert not robots_allows("https://brand.com/cart", body)

    def test_generic_group_applies_when_no_specific(self):
        body = "User-agent: *\nDisallow: /cart\nDisallow: /checkout\n"
        assert robots_allows("https://x.com/products/1", body)
        assert not robots_allows("https://x.com/cart", body)

    def test_specific_group_overrides_generic(self):
        # "*" 禁一切，但给我们的 bot 单独放行 /products/
        body = (
            "User-agent: *\nDisallow: /\n\n"
            "User-agent: OutdoorDealBot\nAllow: /products/\nDisallow: /\n"
        )
        assert robots_allows("https://x.com/products/beta-lt", body)
        assert not robots_allows("https://x.com/cart", body)

    def test_wildcard_rule(self):
        body = "User-agent: *\nDisallow: /*?*size=\n"
        assert not robots_allows("https://x.com/p/1?color=black&size=M", body)
        assert robots_allows("https://x.com/p/1?color=black", body)

    def test_empty_body_means_allowed(self):
        assert robots_allows("https://x.com/anything", "")


class TestProductPage:
    def test_jsonld_fixture(self, fixture_path):
        html = fixture_path("product_jsonld.html").read_text()
        f = parse_product_page(html, url="https://brand.com/p/beta-lt")
        assert f["name"].startswith("Arc'teryx Beta LT")
        assert f["sku"] == "27910"
        assert f["color"] == "Black"
        assert f["image"] == "https://example-retailer.com/img/beta-lt-black.jpg"
        assert f["price"] == 449.25
        assert f["currency"] == "USD"
        assert f["in_stock"]

    def test_jsonld_image_variants(self):
        # image 字段的常见形态：URL 字符串 / 列表 / ImageObject
        base = {"@type": "Product", "name": "X", "offers": {"price": "10", "priceCurrency": "USD"}}
        p1 = parse_jsonld_product([json.dumps({**base, "image": "https://c/1.jpg"})])
        assert p1["image"] == "https://c/1.jpg"
        p2 = parse_jsonld_product(
            [json.dumps({**base, "image": [{"@type": "ImageObject", "url": "https://c/2.jpg"}]})]
        )
        assert p2["image"] == "https://c/2.jpg"
        p3 = parse_jsonld_product([json.dumps(base)])
        assert p3["image"] == ""

    def test_meta_fallback_fixture(self, fixture_path):
        html = fixture_path("product_meta_fallback.html").read_text()
        f = parse_product_page(html, url="https://brand.com/p/torrentshell")
        assert f["price"] == 239.0
        assert "Torrentshell" in f["name"]

    def test_block_page_detected(self):
        assert looks_like_block_or_login("<html>please verify you are human</html>")
        assert looks_like_block_or_login("<html>Access Denied</html>")
        assert not looks_like_block_or_login("<html>Arc'teryx Beta LT $449</html>")

    def test_fetch_product_happy_path(self, fixture_path):
        html = fixture_path("product_jsonld.html").read_text()
        robots = "User-agent: *\nAllow: /\n"

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text=robots)
            return httpx.Response(200, text=html)

        client = httpx.Client(transport=httpx.MockTransport(handler))
        rl = HostRateLimiter(min_interval=0, clock=lambda: 0.0, sleep=lambda s: None)
        raw = fetch_product("https://brand.com/products/beta-lt", client, rl)
        assert raw is not None
        assert raw.price_cents == 44925
        assert raw.external_id == "27910"
        assert raw.source == "web_product"
        assert raw.image == "https://example-retailer.com/img/beta-lt-black.jpg"

    def test_fetch_product_blocked_by_robots(self):
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nDisallow: /\n")
            return httpx.Response(200, text="<html>x</html>")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        rl = HostRateLimiter(min_interval=0, clock=lambda: 0.0, sleep=lambda s: None)
        assert fetch_product("https://brand.com/p/1", client, rl) is None

    def test_collector_loops_targets(self, fixture_path):
        html = fixture_path("product_meta_fallback.html").read_text()

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path == "/robots.txt":
                return httpx.Response(200, text="User-agent: *\nAllow: /\n")
            if "good" in request.url.path:
                return httpx.Response(200, text=html)
            return httpx.Response(500, text="err")

        client = httpx.Client(transport=httpx.MockTransport(handler))
        c = WebProductCollector(
            targets=[("official-us", "https://brand.com/good"), ("official-us", "https://brand.com/bad")]
        )
        c.rate_limiter = HostRateLimiter(min_interval=0, clock=lambda: 0.0, sleep=lambda s: None)
        raws = list(c.collect(client=client))
        assert len(raws) == 1  # 单 URL 失败不中断整个批次
        assert raws[0].channel_slug == "official-us"


class TestProductGroup:
    """真实官网（arcteryx.com）形态：ProductGroup + hasVariant（颜色×尺码）。

    fixture 来自 2026-10-24 抓取的 Beta AR Jacket 页面，截取 3 个变体。
    """

    def _variants(self):
        import json as _json
        from pathlib import Path

        from app.config import FIXTURES_DIR

        doc = _json.loads((Path(FIXTURES_DIR) / "arcteryx_beta_ar_productgroup.json").read_text())
        html = f'<script type="application/ld+json">{_json.dumps(doc)}</script>'
        return parse_product_variants(html, url=doc["url"])

    def test_group_expands_to_variants(self):
        vs = self._variants()
        assert len(vs) == 3
        first = vs[0]
        assert first["brand"] == "Arc'teryx"
        assert first["color"] == "Cloud / Void"
        assert first["size"] == "XL"
        assert first["sku"] == "X000011062012"
        assert first["price"] == 650.0
        assert first["currency"] == "USD"
        assert first["in_stock"] is True

    def test_group_variants_differ_by_color_size(self):
        vs = self._variants()
        assert {(v["color"], v["size"]) for v in vs} == {
            ("Cloud / Void", "XL"),
            ("Rune / Sea Salt", "XL"),
            ("Nucleus / Larch", "S"),
        }

    def test_page_keeps_single_item_contract(self):
        vs = self._variants()
        assert parse_product_page.__doc__  # 单条入口仍在
        import json as _json
        from pathlib import Path

        from app.collectors.web_product import parse_product_page as ppp
        from app.config import FIXTURES_DIR

        doc = _json.loads((Path(FIXTURES_DIR) / "arcteryx_beta_ar_productgroup.json").read_text())
        html = f'<script type="application/ld+json">{_json.dumps(doc)}</script>'
        assert ppp(html, url=doc["url"]) == vs[0]
