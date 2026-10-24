"""数据模型（M0）：品牌 / 款式 / 变体（颜色×尺码）/ 渠道 / 挂链 / 快照 / 优惠 / 匹配审核 / 提醒。

口径约定：
- 价格一律存整数"分"（price_cents），杜绝浮点误差。
- 快照只在价格或库存变化时写入（由 app.history.snapshots 保证）。
- 优惠作用范围 scope、提醒类型 kinds 等 JSON 字段以字符串落库，读写走 util.load_json/dump_json。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, NaiveDatetime
from sqlmodel import Field as SQLField
from sqlmodel import SQLModel, UniqueConstraint

from app.util import utc_now

# ---------------------------------------------------------------------------
# SKU 主数据
# ---------------------------------------------------------------------------


class Brand(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    slug: str = SQLField(unique=True, index=True)  # arcteryx / thenorthface / patagonia
    name: str  # Arc'teryx
    name_cn: str = ""  # 始祖鸟
    aliases_json: str = "[]"  # 标题里可能出现的写法，normalize 词典为源头


class Style(SQLModel, table=True):
    """款式：品牌下的一个型号（如 Beta LT Jacket）。"""

    id: int | None = SQLField(default=None, primary_key=True)
    brand_id: int = SQLField(foreign_key="brand.id", index=True)
    style_number: str = SQLField(index=True)  # 官方款号，如 24104 / NF0A3V5L / 85240
    name: str  # Beta LT Jacket
    category: str = ""  # hardshell / fleece / down ...
    gender: str = ""  # men / women / unisex


class Variant(SQLModel, table=True):
    """变体 = 款式 × 颜色 × 尺码。比价的最小单位。"""

    id: int | None = SQLField(default=None, primary_key=True)
    style_id: int = SQLField(foreign_key="style.id", index=True)
    color: str  # 词典归一后的颜色，如 black
    size: str  # 词典归一后的尺码，如 m / xl / 42

    __table_args__ = (UniqueConstraint("style_id", "color", "size"),)


# ---------------------------------------------------------------------------
# 渠道与挂链
# ---------------------------------------------------------------------------


class Channel(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    slug: str = SQLField(unique=True)  # jd / taobao / rei / backcountry / arcteryx_cn
    name: str
    kind: str  # jd_union / tbk / avantlink / official_cn / official_us / affiliate
    currency: str = "CNY"
    country: str = "CN"
    active: bool = True


class Listing(SQLModel, table=True):
    """渠道里的一个商品页（同 external_id 幂等）。匹配成功后挂到 variant。"""

    id: int | None = SQLField(default=None, primary_key=True)
    channel_id: int = SQLField(foreign_key="channel.id", index=True)
    variant_id: int | None = SQLField(
        default=None, foreign_key="variant.id", index=True
    )  # 归一化通过后才填充
    external_id: str = SQLField(index=True)  # 渠道内商品/SKU 标识
    url: str = ""
    title: str = ""
    image: str = ""
    source: str = "manual"
    merchant: str = ""
    stock_verified: bool = False
    active: bool = True
    last_seen_at: NaiveDatetime | None = None

    __table_args__ = (UniqueConstraint("channel_id", "external_id"),)


# ---------------------------------------------------------------------------
# 价格历史
# ---------------------------------------------------------------------------


class PriceSnapshot(SQLModel, table=True):
    """价格快照：只在价格或库存变化时写入。"""

    id: int | None = SQLField(default=None, primary_key=True)
    listing_id: int = SQLField(foreign_key="listing.id", index=True)
    ts: NaiveDatetime = SQLField(default_factory=utc_now, index=True)
    price_cents: int
    currency: str = "CNY"
    in_stock: bool = True
    stock_verified: bool = True
    paid_now_cents: int | None = None
    rebate_cents: int = 0
    effective_cents: int | None = None


# ---------------------------------------------------------------------------
# 优惠规则
# ---------------------------------------------------------------------------


class PromoRule(SQLModel, table=True):
    """优惠规则：可配置、可人工录入（大促期间最可靠的来源是人）。"""

    id: int | None = SQLField(default=None, primary_key=True)
    name: str
    kind: str = SQLField(index=True)  # app.pricing.rules.PromoKind 的值
    channel_id: int | None = SQLField(
        default=None, foreign_key="channel.id", index=True
    )  # None = 平台级（全渠道可用）
    threshold_cents: int = 0  # 订单金额 ≥ 门槛才生效
    amount_cents: int = 0  # 固定减免（分）
    rate: float = 0.0  # 比例减免（0-1）
    cap_cents: int = 0  # 单条规则最多减（0 = 不限）
    scope_json: str = "{}"  # {"brand_ids":..,"style_ids":..,"variant_ids":..,"listing_ids":..}
    exclusive_group: str = ""  # 同组互斥；空 = 不互斥
    valid_from: NaiveDatetime | None = None
    valid_to: NaiveDatetime | None = None
    source: str = "manual"  # manual / smzdm / api
    active: bool = True
    created_at: NaiveDatetime = SQLField(default_factory=utc_now)


# ---------------------------------------------------------------------------
# SKU 归一化的人工审核队列
# ---------------------------------------------------------------------------


class MatchCandidate(SQLModel, table=True):
    """置信度 < 0.85 的匹配进入人工审核，绝不猜。"""

    id: int | None = SQLField(default=None, primary_key=True)
    payload_json: str  # RawListing 序列化
    suggested_style_id: int | None = SQLField(default=None, foreign_key="style.id")
    suggested_variant_id: int | None = SQLField(default=None, foreign_key="variant.id")
    confidence: float
    reasons_json: str = "[]"  # 匹配依据，页面要展示
    status: str = SQLField(default="pending", index=True)  # pending / approved / rejected
    created_at: NaiveDatetime = SQLField(default_factory=utc_now)


# ---------------------------------------------------------------------------
# 提醒
# ---------------------------------------------------------------------------


class AlertSubscription(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    variant_id: int = SQLField(foreign_key="variant.id", index=True)
    target_price_cents: int | None = None  # 到手价 ≤ 目标价触发
    kinds_json: str = '["price_drop", "new_low"]'  # price_drop/new_low/restock/coupon_expiring
    channel: str = "telegram"  # telegram / email / wecom
    destination: str = ""  # chat_id / 邮箱；空则用全局配置
    active: bool = True
    created_at: NaiveDatetime = SQLField(default_factory=utc_now)


class AlertEvent(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    subscription_id: int | None = SQLField(default=None, foreign_key="alertsubscription.id")
    variant_id: int = SQLField(index=True)
    kind: str
    payload_json: str = "{}"
    created_at: NaiveDatetime = SQLField(default_factory=utc_now, index=True)
    sent_at: NaiveDatetime | None = None
    send_error: str = ""


# ---------------------------------------------------------------------------
# 汇率
# ---------------------------------------------------------------------------


class ExchangeRate(SQLModel, table=True):
    id: int | None = SQLField(default=None, primary_key=True)
    day: str = SQLField(index=True)  # YYYY-MM-DD（Asia/Shanghai）
    base: str = "USD"
    quote: str = "CNY"
    rate: float
    source: str = "manual"


# ---------------------------------------------------------------------------
# 优惠线报（应用的内容主体，商品目录从线报里长出来）
# ---------------------------------------------------------------------------


class Deal(SQLModel, table=True):
    """一条优惠线报（smzdm 好价等）。按 (source, source_id) 幂等。"""

    id: int | None = SQLField(default=None, primary_key=True)
    source: str = SQLField(default="smzdm", index=True)
    source_id: str = SQLField(index=True)  # smzdm 文章 ID，如 184615805
    url: str = ""  # 线报原文
    title: str
    summary: str = ""  # 优惠说明摘要（og:description）：叠券/满减/到手条件
    price_cents: int = 0  # 线报标价（券前）；0 = 未知/免费信息型
    currency: str = "CNY"
    channel: str = ""  # 京东 / 天猫 / 官网 ...
    image: str = ""
    tags_json: str = "[]"
    published_at: NaiveDatetime | None = None
    matched_variant_id: int | None = SQLField(
        default=None, foreign_key="variant.id", index=True
    )  # 命中已有/新长出的 variant；NULL = 未匹配（照常展示）
    content_hash: str = ""  # 完整内容去重；不把线报价当作渠道报价
    last_checked_at: NaiveDatetime | None = None
    expires_at: NaiveDatetime | None = None
    expired: bool = False
    created_at: NaiveDatetime = SQLField(default_factory=utc_now)

    __table_args__ = (UniqueConstraint("source", "source_id"),)


# ---------------------------------------------------------------------------
# 采集器统一产出（pydantic，非表）
# ---------------------------------------------------------------------------


class DealDraft(BaseModel):
    """线报采集器的统一产出（smzdm 等）。"""

    source: str = "smzdm"
    source_id: str
    url: str = ""
    title: str
    summary: str = ""
    price_cents: int = 0
    currency: str = "CNY"
    channel: str = ""
    image: str = ""
    tags: list[str] = Field(default_factory=list)
    published_at: datetime | None = None
    checked_at: datetime | None = None
    expires_at: datetime | None = None
    expired: bool = False


class CouponInfo(BaseModel):
    """采集到的原始券信息，规则引擎可将其转成 PromoRule。"""

    name: str = ""
    amount_cents: int = 0
    threshold_cents: int = 0
    start_time: NaiveDatetime | None = None
    end_time: NaiveDatetime | None = None


class RawListing(BaseModel):
    """各渠道采集器统一产出的原始挂链，进入 SKU 归一化流程。"""

    source: str  # jd_union / tbk / avantlink / web
    channel_slug: str  # 对应 Channel.slug
    external_id: str
    url: str = ""
    title: str
    image: str = ""
    merchant: str = ""
    brand_hint: str = ""
    style_number_hint: str = ""
    color_hint: str = ""
    size_hint: str = ""
    price_cents: int  # 现价（券前）
    list_price_cents: int = 0  # 原价
    currency: str = "CNY"
    in_stock: bool = True
    stock_verified: bool = True
    coupons: list[CouponInfo] = Field(default_factory=list)
    collected_at: datetime = Field(default_factory=utc_now)
