"""AvantLink 采集器：ProductSearch 接口（美国官网渠道，海淘价数据源）。

- 文档：https://www.avantlink.com/ProductSearch.php?affiliate_id=..&website_id=..
- 参数 output=xml；关键词搜索，限速 3600 次/小时、15000 次/天（PRD §4）；
- 解析用 xml.etree，纯函数 parse_product_search(xml_text) 供 fixtures 测试；
- 货币 USD，渠道 kind=official、country=US。
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from collections.abc import Iterable

from app.collectors.base import make_http_client
from app.config import get_settings
from app.models import RawListing

API_URL = "https://www.avantlink.com/ProductSearch.php"


class AvantLinkClient:
    def __init__(self, affiliate_id: str | None = None, website_id: str | None = None) -> None:
        s = get_settings()
        self.affiliate_id = affiliate_id or s.avantlink_affiliate_id
        self.website_id = website_id or s.avantlink_website_id
        self.http = make_http_client(timeout=30)

    def product_search(
        self,
        search_keywords: str,
        *,
        merchant_ids: str = "",
        limit: int = 100,
    ) -> str:
        if not self.affiliate_id or not self.website_id:
            raise PermissionError(
                "AVANTLINK_AFFILIATE_ID / AVANTLINK_WEBSITE_ID 未配置（backend/.env）"
            )
        params = {
            "affiliate_id": self.affiliate_id,
            "website_id": self.website_id,
            "search_keywords": search_keywords,
            "output": "xml",
            "limit": str(limit),
        }
        if merchant_ids:
            params["merchant_ids"] = merchant_ids
        resp = self.http.get(API_URL, params=params)
        resp.raise_for_status()
        return resp.text


def _price_cents(text: str | None) -> int:
    if not text:
        return 0
    return int(round(float(text) * 100))


def parse_product_search(
    xml_text: str, *, channel_slug: str = "avantlink"
) -> list[RawListing]:
    """解析 ProductSearch XML → RawListing（纯函数）。"""
    root = ET.fromstring(xml_text)
    listings: list[RawListing] = []
    for row in root.iter("row"):

        def field(name: str, _row=row) -> str:
            node = _row.find(name)
            return (node.text or "").strip() if node is not None and node.text else ""

        sale = _price_cents(field("Sale_Price"))
        retail = _price_cents(field("Retail_Price"))
        stock_text = field("Stock_Status").lower()
        listings.append(
            RawListing(
                source="avantlink",
                channel_slug=channel_slug,
                external_id=field("SKU_Code") or field("Product_ID"),
                url=field("Deep_URL"),
                title=f"{field('Brand_Name')} {field('Product_Name')}".strip(),
                image=field("Image_URL"),
                price_cents=sale or retail,
                list_price_cents=retail,
                currency="USD",
                in_stock="out of stock" not in stock_text and stock_text != "",
                coupons=[],
            )
        )
    return listings


class AvantLinkCollector:
    """采集 AvantLink 关键词商品（美国官网渠道）。channel_slug 默认 avantlink。"""

    channel_slug = "avantlink"

    def __init__(self, client: AvantLinkClient | None = None) -> None:
        self.client = client or AvantLinkClient()

    def collect(self, search_keywords: str) -> Iterable[RawListing]:
        xml_text = self.client.product_search(search_keywords)
        return parse_product_search(xml_text, channel_slug=self.channel_slug)
