"""京东联盟采集器：jd.union.open.goods.query（宙斯开放平台 jos.jd.com）。

- 签名算法（JOS MD5）：secret + 按 key 升序拼接的 k=v 串 + secret，取 MD5 大写；
- 密钥只读环境变量（JD_UNION_APP_KEY / JD_UNION_SECRET_KEY）；
- parse_goods_query 是纯函数，fixtures 测试不联网；
- 按关键词查询（按 SKU 批量查询需额外权限，风险应对见 PRD §8）。
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from app.collectors.base import make_http_client
from app.config import get_settings
from app.models import CouponInfo, RawListing
from app.util import utc_now

API_URL = "https://api.jd.com/routerjson"
METHOD = "jd.union.open.goods.query"


class JDUnionClient:
    def __init__(self, app_key: str | None = None, secret: str | None = None) -> None:
        s = get_settings()
        self.app_key = app_key or s.jd_union_app_key
        self.secret = secret or s.jd_union_secret_key
        self.http = make_http_client(timeout=30)

    @staticmethod
    def sign(params: dict[str, str], secret: str) -> str:
        """JOS MD5 签名：secret + sorted(k+v) + secret → MD5 大写。"""
        plain = secret + "".join(f"{k}{params[k]}" for k in sorted(params)) + secret
        return hashlib.md5(plain.encode("utf-8")).hexdigest().upper()

    def query_goods(self, keywords: str, page_size: int = 30) -> dict:
        if not self.app_key or not self.secret:
            raise PermissionError("JD_UNION_APP_KEY / JD_UNION_SECRET_KEY 未配置（backend/.env）")
        param_json = (
            f'{{"goodsReqDTO":{{"keyword":"{keywords}","pageSize":{page_size},"pageIndex":1}}}}'
        )
        system_params = {
            "method": METHOD,
            "app_key": self.app_key,
            "timestamp": utc_now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "1.0",
            "sign_method": "md5",
            "param_json": param_json,
        }
        system_params["sign"] = self.sign(system_params, self.secret)
        resp = self.http.post(API_URL, data=system_params)
        resp.raise_for_status()
        return resp.json()


def _cents(value) -> int:
    """联盟接口价格字段（元，字符串或数字）→ 分。"""
    if value in (None, "", 0):
        return 0
    return int(round(float(value) * 100))


def _coupon_end(raw: str | int | float | None) -> datetime | None:
    if raw in (None, ""):
        return None
    try:
        text = str(raw).strip()
        if text.replace(".", "", 1).isdigit():
            stamp = float(text)
            return datetime.fromtimestamp(stamp / 1000 if stamp > 10**11 else stamp, UTC).replace(
                tzinfo=None
            )
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if value.tzinfo is None:
            value = value.replace(tzinfo=ZoneInfo("Asia/Shanghai"))
        return value.astimezone(UTC).replace(tzinfo=None)
    except (ValueError, OverflowError, OSError):
        return None


def parse_goods_query(payload: dict, *, channel_slug: str = "jd") -> list[RawListing]:
    """解析 jd.union.open.goods.query 响应 → RawListing（纯函数，测试走 fixtures）。"""
    # 注意 JOS 返回键名固定拼写为 "responce"（平台历史 typo，勿改）
    body = payload.get(f"{METHOD.replace('.', '_')}_responce", {})
    query_result = body.get("queryResult") or {}
    if isinstance(query_result, str):
        query_result = json.loads(query_result)
    if query_result.get("code") not in (0, "0", 200, "200"):
        raise ValueError(f"京东联盟返回错误: {query_result.get('message')}")
    data = query_result.get("data") or []
    goods_list = data if isinstance(data, list) else data.get("list", [])

    listings: list[RawListing] = []
    for g in goods_list:
        price_info = g.get("priceInfo") or {}
        coupons: list[CouponInfo] = []
        for c in (g.get("couponInfo") or {}).get("couponList") or []:
            amount = _cents(c.get("discount"))
            if amount <= 0:
                continue
            coupons.append(
                CouponInfo(
                    name=c.get("couponTitle") or "京东店铺券",
                    amount_cents=amount,
                    threshold_cents=_cents(c.get("quota")),
                    start_time=_coupon_end(c.get("couponStartTime")),
                    end_time=_coupon_end(c.get("couponEndTime")),
                )
            )
        images = (g.get("imageInfo") or {}).get("imageList") or []
        listings.append(
            RawListing(
                source="jd_union",
                channel_slug=channel_slug,
                external_id=str(g.get("skuId") or g.get("goodsId") or ""),
                url=g.get("materialUrl") or g.get("detailUrl") or "",
                title=g.get("goodsName") or "",
                image=images[0].get("url", "") if images else "",
                merchant=(g.get("shopInfo") or {}).get("shopName", ""),
                stock_verified="stockState" in g or isinstance(g.get("in_stock"), bool),
                price_cents=_cents(price_info.get("price")),
                list_price_cents=_cents(price_info.get("lowestPrice")),
                currency="CNY",
                in_stock=(
                    str(g["stockState"]) in {"33", "40"}
                    if "stockState" in g
                    else g.get("in_stock", g.get("goodsStatus", 1) in (1, "1", None))
                ),
                coupons=coupons,
            )
        )
    return listings


class JDUnionCollector:
    """采集京东联盟关键词下的商品。channel_slug 默认 jd。"""

    channel_slug = "jd"

    def __init__(self, client: JDUnionClient | None = None) -> None:
        self.client = client or JDUnionClient()

    def collect(self, keywords: str) -> Iterable[RawListing]:
        payload = self.client.query_goods(keywords)
        return parse_goods_query(payload, channel_slug=self.channel_slug)
