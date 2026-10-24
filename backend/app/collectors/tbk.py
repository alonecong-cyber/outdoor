"""淘宝客采集器：taobao.tbk.dg.material.optional（淘宝联盟）。

- 签名：HMAC-MD5，消息 = 按 key 升序的 k+v 拼接，密钥 = app_secret，大写；
- 密钥只读环境变量（TAOBAO_APP_KEY / TAOBAO_APP_SECRET / TAOBAO_PID）；
- parse_material_optional 纯函数，fixtures 测试不联网；
- 优惠以 coupon_* 字段为准（满 X 减 Y），无券时与会员价并存留空。
"""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Iterable

from app.collectors.base import make_http_client
from app.collectors.jd_union import _coupon_end
from app.config import get_settings
from app.models import CouponInfo, RawListing
from app.util import utc_now

API_URL = "https://eco.taobao.com/router/rest"
METHOD = "taobao.tbk.dg.material.optional"


class TBKClient:
    def __init__(self, app_key: str | None = None, secret: str | None = None) -> None:
        s = get_settings()
        self.app_key = app_key or s.taobao_app_key
        self.secret = secret or s.taobao_app_secret
        self.http = make_http_client(timeout=30)

    @staticmethod
    def sign(params: dict[str, str], secret: str) -> str:
        """淘宝 HMAC-MD5 签名：message=sorted(k+v) 拼接，key=secret，大写。"""
        message = "".join(f"{k}{params[k]}" for k in sorted(params))
        return hmac.new(secret.encode(), message.encode(), hashlib.md5).hexdigest().upper()

    def material_optional(
        self,
        keywords: str,
        *,
        adzone_id: str = "",
        page_size: int = 20,
    ) -> dict:
        if not self.app_key or not self.secret:
            raise PermissionError("TAOBAO_APP_KEY / TAOBAO_APP_SECRET 未配置（backend/.env）")
        s = get_settings()
        pid = s.taobao_pid or ""
        adzone = adzone_id or (pid.split("_")[-1] if pid else "")
        params = {
            "method": METHOD,
            "app_key": self.app_key,
            "timestamp": utc_now().strftime("%Y-%m-%d %H:%M:%S"),
            "format": "json",
            "v": "2.0",
            "sign_method": "hmac",
            "keyword": keywords,
            "adzone_id": adzone,
            "page_size": str(page_size),
        }
        params["sign"] = self.sign(params, self.secret)
        resp = self.http.get(API_URL, params=params)
        resp.raise_for_status()
        return resp.json()


def _cents(value) -> int:
    if value in (None, "", 0):
        return 0
    return int(round(float(value) * 100))


def parse_material_optional(payload: dict, *, channel_slug: str = "taobao") -> list[RawListing]:
    """解析 tbk.dg.material.optional 响应 → RawListing（纯函数，测试走 fixtures）。"""
    body = payload.get(f"{METHOD.replace('.', '_')}_response") or {}
    if "error_response" in payload:
        raise ValueError(f"淘宝联盟返回错误: {payload['error_response']}")
    items = ((body.get("result_list") or {}).get("map_data")) or []
    if isinstance(items, dict):
        items = [items]

    listings: list[RawListing] = []
    for m in items:
        coupons: list[CouponInfo] = []
        amount = _cents(m.get("coupon_amount"))
        if amount > 0:
            threshold = _cents(m.get("coupon_start_fee"))
            coupons.append(
                CouponInfo(
                    name=f"淘宝券 满{threshold / 100:.0f}减{amount / 100:.0f}",
                    amount_cents=amount,
                    threshold_cents=threshold,
                    start_time=_coupon_end(m.get("coupon_start_time")),
                    end_time=_coupon_end(
                        str(m["coupon_end_time"]) + " 23:59:59"
                        if len(str(m.get("coupon_end_time", ""))) == 10
                        else m.get("coupon_end_time")
                    ),
                )
            )
        listings.append(
            RawListing(
                source="tbk",
                channel_slug=channel_slug,
                external_id=str(m.get("item_id") or m.get("num_iid") or ""),
                url=m.get("url") or "",
                title=m.get("title") or "",
                image=(m.get("pict_url") or "").replace("http://", "https://"),
                price_cents=_cents(m.get("zk_final_price")),
                list_price_cents=_cents(m.get("reserve_price")),
                currency="CNY",
                merchant=m.get("nick") or m.get("shop_title") or "",
                in_stock=m.get("in_stock") is True,
                stock_verified=isinstance(m.get("in_stock"), bool),
                coupons=coupons,
            )
        )
    return listings


class TaobaoKeCollector:
    """采集淘宝客物料（关键词）。channel_slug 默认 taobao。"""

    channel_slug = "taobao"

    def __init__(self, client: TBKClient | None = None) -> None:
        self.client = client or TBKClient()

    def collect(self, keywords: str) -> Iterable[RawListing]:
        payload = self.client.material_optional(keywords)
        return parse_material_optional(payload, channel_slug=self.channel_slug)
