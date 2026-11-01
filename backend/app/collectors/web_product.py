"""官网单品页采集：robots.txt 检查 + ≥10s/域名限速 + JSON-LD → CSS 解析。

合规约束（AGENTS.md / PRD §4）：
- 先查 robots.txt，不允许就不抓；
- 同域名两次请求间隔 ≥ MIN_INTERVAL_SECONDS；
- 遇到登录墙/验证码立即放弃该 URL（返回 None，不重试、不对抗）；
- 解析顺序：JSON-LD（schema.org Product）→ CSS/og meta。CSS 选择器可配置。
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from urllib.parse import urlsplit

import httpx

from app.collectors.base import make_http_client
from app.models import RawListing
from app.util import utc_now

MIN_INTERVAL_SECONDS = 10.0
USER_AGENT = "Mozilla/5.0 (compatible; OutdoorDealBot/0.1; +https://outdoordeal.local/bot)"


class ProductParseError(Exception):
    """页面两种解析路径都失败。"""


class TooSoonError(Exception):
    """距上次请求同域名不足最小间隔（测试与限速器内部使用）。"""


class HostRateLimiter:
    """每域名最小间隔限速器。clock/sleep 可注入便于测试。"""

    def __init__(
        self,
        min_interval: float = MIN_INTERVAL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self.clock = clock
        self.sleep = sleep
        self._last: dict[str, float] = {}

    def wait(self, host: str) -> float:
        """等待到可请求。返回实际等待秒数。"""
        last = self._last.get(host)
        now = self.clock()
        waited = 0.0
        if last is not None:
            elapsed = now - last
            if elapsed < self.min_interval:
                waited = self.min_interval - elapsed
                self.sleep(waited)
        self._last[host] = self.clock()
        return waited

    def check(self, host: str) -> bool:
        """不等待，只检查现在是否可请求（测试用）。"""
        last = self._last.get(host)
        if last is None:
            return True
        return (self.clock() - last) >= self.min_interval


def _robots_groups(body: str) -> list[tuple[list[str], list[tuple[str, str]]]]:
    """把 robots.txt 拆成 [(agents, [(kind, pattern), ...])] 组。

    连续的 User-agent 行同属一组；遇到带规则的下一个 User-agent 才切组。
    """
    groups: list[tuple[list[str], list[tuple[str, str]]]] = []
    agents: list[str] = []
    rules: list[tuple[str, str]] = []
    for raw in body.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            if rules:  # 上一组已有规则 → 新组开始
                groups.append((agents, rules))
                agents, rules = [], []
            if value:
                agents.append(value.lower())
        elif key in ("allow", "disallow") and agents:
            rules.append((key, value))
    if agents:
        groups.append((agents, rules))
    return groups


def _rule_matches(path: str, pattern: str) -> bool:
    """RFC 9309 规则匹配：支持 * 通配，结尾 $ 表示完整匹配。"""
    if not pattern:
        return False
    anchored = pattern.endswith("$")
    if anchored:
        pattern = pattern[:-1]
    rx = re.escape(pattern).replace(r"\*", ".*")
    if anchored:
        return re.fullmatch(rx, path) is not None
    return re.match(rx, path) is not None


def robots_allows(url: str, robots_body: str) -> bool:
    """robots.txt 是否允许本 bot 抓该 URL。空 body 视为允许。

    按 RFC 9309 选组：取与 USER_AGENT 匹配（子串、大小写不敏感）的
    最长 agent 组；专属组存在时 "*" 组不再兜底——明确 Disallow 本 bot
    的站点必须被尊重。组内取匹配路径最长的规则，同长 Allow 优先。
    """
    if not robots_body.strip():
        return True
    ua = USER_AGENT.lower()
    chosen: list[tuple[str, str]] | None = None
    best_len = -1
    for agents, rules in _robots_groups(robots_body):
        for a in agents:
            match_len = 0 if a == "*" else (len(a) if a in ua else -1)
            if match_len >= 0 and match_len > best_len:
                best_len = match_len
                chosen = rules
    if chosen is None:
        return True  # 没有任何组适用本 bot
    parts = urlsplit(url)
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    best: tuple[int, bool] | None = None  # (规则长度, 是否允许)
    for kind, pattern in chosen:
        if not _rule_matches(path, pattern):
            continue
        allowed = kind == "allow"
        if (
            best is None
            or len(pattern) > best[0]
            or (len(pattern) == best[0] and allowed and not best[1])
        ):
            best = (len(pattern), allowed)
    return True if best is None else best[1]


def fetch_robots_txt(base_url: str, client: httpx.Client) -> str:
    """抓取域名 robots.txt。404/网络失败视为无限制（返回空串）。"""
    parts = urlsplit(base_url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = client.get(robots_url, headers={"User-Agent": USER_AGENT})
        if resp.status_code == 404:
            return ""
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError:
        return ""


# ---------- JSON-LD ----------


def _jsonld_product(doc) -> dict | None:
    """在 JSON-LD 文档（含 @graph、单对象、列表）里找 Product。"""
    candidates = doc if isinstance(doc, list) else [doc]
    for node in candidates:
        if not isinstance(node, dict):
            continue
        if node.get("@graph"):
            found = _jsonld_product(node["@graph"])
            if found:
                return found
        types = node.get("@type") or []
        types = types if isinstance(types, list) else [types]
        if "Product" in types:
            return node
    return None


def _jsonld_product_group(doc) -> dict | None:
    """找 schema.org ProductGroup（如 arcteryx.com：hasVariant 挂颜色×尺码 Product）。"""
    candidates = doc if isinstance(doc, list) else [doc]
    for node in candidates:
        if not isinstance(node, dict):
            continue
        if node.get("@graph"):
            found = _jsonld_product_group(node["@graph"])
            if found:
                return found
        types = node.get("@type") or []
        types = types if isinstance(types, list) else [types]
        if "ProductGroup" in types and isinstance(node.get("hasVariant"), list):
            return node
    return None


_VARIANT_NAME_RE = re.compile(r"^(?P<name>.+?),\s*(?P<color>[^,]+),\s*Size\s+(?P<size>\S+)\s*$")


def _variant_color_size(variant: dict) -> tuple[str, str]:
    """变体颜色/尺码：显式字段优先，其次从 name 末段解析（"…, Cloud / Void, Size XL"）。"""
    color = str(variant.get("color") or "").strip()
    size = str(variant.get("size") or "").strip()
    if not (color and size):
        m = _VARIANT_NAME_RE.match(str(variant.get("name") or ""))
        if m:
            color = color or m.group("color").strip()
            size = size or (m.group("size") or "").strip()
    return color, size


def _jsonld_offers(product: dict) -> dict:
    offers = product.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    return offers if isinstance(offers, dict) else {}


def _jsonld_image(product: dict) -> str:
    """image 字段形态多样：URL 字符串 / 列表 / ImageObject（含 url）。"""
    image = product.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    if isinstance(image, dict):
        image = image.get("url") or image.get("contentUrl")
    return str(image) if image else ""


def _product_fields(product: dict, *, url: str, brand: str = "") -> dict:
    """schema.org Product 节点 → 统一字段 dict。"""
    offers = _jsonld_offers(product)
    brand_value = product.get("brand")
    if isinstance(brand_value, dict):
        brand_value = brand_value.get("name", "")
    brand = str(brand_value or brand or "")
    style = str(product.get("style") or "")
    price = offers.get("price") or offers.get("lowPrice") or product.get("price")
    currency = offers.get("priceCurrency") or "USD"
    availability = str(offers.get("availability") or "")
    in_stock = "InStock" in availability or "InStoreOnly" in availability
    return {
        "name": product.get("name") or "",
        "brand": brand,
        "style": style,
        "sku": str(product.get("sku") or product.get("productID") or ""),
        "color": product.get("color") or "",
        "size": product.get("size") or "",
        "image": _jsonld_image(product),
        "price": float(price) if price not in (None, "") else None,
        "currency": currency,
        "in_stock": in_stock,
        "url": url,
    }


def parse_jsonld_variants(script_bodies: list[str], *, url: str = "") -> list[dict]:
    """JSON-LD → 变体字段列表。

    - 普通 Product：返回单元素列表；
    - ProductGroup（arcteryx.com 等官网）：hasVariant 每个颜色×尺码一条，
      颜色/尺码从变体 name（"…, Cloud / Void, Size XL"）解析，品牌/图取组级兜底。
    """
    for body in script_bodies:
        try:
            doc = json.loads(body)
        except json.JSONDecodeError:
            continue
        group = _jsonld_product_group(doc)
        if group:
            group_brand = group.get("brand")
            if isinstance(group_brand, dict):
                group_brand = group_brand.get("name", "")
            group_style = str(group.get("productGroupID") or "")
            fields_list = []
            for variant in group["hasVariant"]:
                if not isinstance(variant, dict):
                    continue
                fields = _product_fields(variant, url=url, brand=str(group_brand or ""))
                fields["style"] = fields["style"] or group_style
                color, size = _variant_color_size(variant)
                fields["color"] = fields["color"] or color
                fields["size"] = fields["size"] or size
                fields_list.append(fields)
            if fields_list:
                return fields_list
        product = _jsonld_product(doc)
        if product:
            return [_product_fields(product, url=url)]
    raise ProductParseError("页面无可用 JSON-LD Product")


def parse_jsonld_product(script_bodies: list[str], *, url: str = "") -> dict:
    """从 JSON-LD script 列表提取 Product 字段。失败抛 ProductParseError。"""
    return parse_jsonld_variants(script_bodies, url=url)[0]


# ---------- CSS / meta 兜底 ----------

OG_TITLE_RE = re.compile(
    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', re.I
)
OG_IMAGE_RE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']', re.I
)
META_PRICE_RE = re.compile(
    r'<meta[^>]+(?:property|itemprop)=["\'](?:product:price:amount|price)["\'][^>]+content=["\']([\d.]+)["\']',
    re.I,
)


def parse_meta_fallback(html: str, *, url: str = "") -> dict:
    """og:title + product:price:amount 兜底解析。失败抛 ProductParseError。"""
    title_m = OG_TITLE_RE.search(html)
    price_m = META_PRICE_RE.search(html)
    image_m = OG_IMAGE_RE.search(html)
    if not (title_m and price_m):
        raise ProductParseError("CSS/meta 兜底解析失败")
    return {
        "name": title_m.group(1).strip(),
        "brand": "",
        "sku": "",
        "color": "",
        "size": "",
        "image": image_m.group(1).strip() if image_m else "",
        "price": float(price_m.group(1)),
        "currency": "USD",
        "in_stock": True,
        "url": url,
    }


JSONLD_SCRIPT_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.I | re.S
)


def parse_product_page(html: str, *, url: str = "") -> dict:
    """单品页 → 字段 dict（首个变体）。JSON-LD 优先，meta 兜底。"""
    return parse_product_variants(html, url=url)[0]


def parse_product_variants(html: str, *, url: str = "") -> list[dict]:
    """单品页 → 变体字段列表（ProductGroup 时为全部颜色×尺码）。"""
    bodies = [m.group(1).strip() for m in JSONLD_SCRIPT_RE.finditer(html)]
    try:
        return parse_jsonld_variants(bodies, url=url)
    except ProductParseError:
        return [parse_meta_fallback(html, url=url)]


def _cents(price: float | None) -> int:
    if price is None:
        return 0
    return int(round(price * 100))


def looks_like_block_or_login(html: str) -> bool:
    """识别登录墙/验证码页特征，命中即放弃（不对抗风控）。"""
    markers = ("captcha", "verify you are human", "access denied", "are you a robot")
    lower = html[:5000].lower()
    return any(m in lower for m in markers)


def _raw_listing(fields: dict, url: str) -> RawListing:
    return RawListing(
        source="web_product",
        channel_slug="",
        external_id=fields["sku"] or url,
        url=url,
        title=fields["name"],
        image=fields.get("image", ""),
        brand_hint=fields["brand"],
        style_number_hint=fields.get("style") or fields["sku"],
        color_hint=fields["color"],
        size_hint=fields["size"],
        price_cents=_cents(fields["price"]),
        list_price_cents=0,
        currency=fields["currency"],
        in_stock=fields["in_stock"],
        coupons=[],
        collected_at=utc_now(),
    )


def fetch_products(
    url: str,
    client: httpx.Client,
    rate_limiter: HostRateLimiter,
) -> list[RawListing] | None:
    """抓单个官网商品页 → RawListing 列表（ProductGroup 拆为各颜色×尺码）。

    robots 不允许/风控页 → None。
    """
    host = urlsplit(url).netloc
    if not robots_allows(url, fetch_robots_txt(url, client)):
        return None
    rate_limiter.wait(host)
    resp = client.get(url, headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    resp.raise_for_status()
    html = resp.text
    if looks_like_block_or_login(html):
        return None
    return [_raw_listing(f, url) for f in parse_product_variants(html, url=url)]


def fetch_product(
    url: str,
    client: httpx.Client,
    rate_limiter: HostRateLimiter,
) -> RawListing | None:
    """抓单个官网商品页 → 首个 RawListing。robots 不允许/风控页 → None。"""
    listings = fetch_products(url, client, rate_limiter)
    return listings[0] if listings else None


class WebProductCollector:
    """官网单品页采集器：targets 为 (channel_slug, url) 列表。"""

    channel_slug = ""

    def __init__(self, targets: list[tuple[str, str]]) -> None:
        self.targets = targets
        self.rate_limiter = HostRateLimiter()

    def collect(self, client: httpx.Client | None = None) -> Iterable[RawListing]:
        client = client or make_http_client(timeout=30, follow_redirects=True)
        for channel_slug, url in self.targets:
            try:
                listings = fetch_products(url, client, self.rate_limiter)
            except (httpx.HTTPError, ProductParseError):
                # 单个 URL 失败不拖垮整批；退避重试留给上层调度
                continue
            if listings:
                for raw in listings:
                    raw.channel_slug = channel_slug
                    yield raw
