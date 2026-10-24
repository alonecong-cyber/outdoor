"""collectors 包：联盟 API + 官网页采集，统一产 RawListing。"""

from app.collectors.avantlink import AvantLinkClient, AvantLinkCollector, parse_product_search
from app.collectors.base import (
    BaseCollector,
    CollectorError,
    CredentialsMissing,
    fetch_with_backoff,
)
from app.collectors.jd_union import JDUnionClient, JDUnionCollector, parse_goods_query
from app.collectors.tbk import TaobaoKeCollector, TBKClient, parse_material_optional
from app.collectors.web_product import (
    HostRateLimiter,
    ProductParseError,
    WebProductCollector,
    fetch_product,
    parse_product_page,
    robots_allows,
)

__all__ = [
    "AvantLinkClient",
    "AvantLinkCollector",
    "BaseCollector",
    "CollectorError",
    "CredentialsMissing",
    "HostRateLimiter",
    "JDUnionClient",
    "JDUnionCollector",
    "ProductParseError",
    "TBKClient",
    "TaobaoKeCollector",
    "WebProductCollector",
    "fetch_product",
    "fetch_with_backoff",
    "parse_goods_query",
    "parse_material_optional",
    "parse_product_page",
    "parse_product_search",
    "robots_allows",
]
