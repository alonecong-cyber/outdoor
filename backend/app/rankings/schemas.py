"""权威榜单与多维装备横评数据模型定义。

包含：
- 装备条目（含各价位梯队、权威榜单背书、价格指南、核心物理规格、优缺点实测）
- 跨价位横评与差价分析模型
- 品类统计与检索模型
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PriceTier(StrEnum):
    BUDGET = "budget"  # 百元入门平替 (< ¥1,000)
    MID = "mid"  # 千元进阶中端 (¥1,000 ~ ¥2,500)
    FLAGSHIP = "flagship"  # 顶级专业旗舰 (¥2,500+)


class GearCategory(StrEnum):
    HARDSHELL = "hardshell"  # 硬壳冲锋衣
    RAIN_JACKET = "rain_jacket"  # 轻量防水夹克
    SOFTSHELL = "softshell"  # 软壳
    FLEECE = "fleece"  # 抓绒中层
    BASELAYER = "baselayer"  # 打底秋衣 / 排汗内衣
    DOWN = "down"  # 羽绒服
    INSULATED = "insulated"  # 棉服 / 人造保暖
    HIKING_PANTS = "hiking_pants"  # 徒步裤
    RAIN_PANTS = "rain_pants"  # 防水裤
    SOCKS = "socks"  # 户外袜
    SHOES = "shoes"  # 低帮徒步鞋（通勤+徒步）
    HIKING_BOOTS = "hiking_boots"  # 中高帮徒步靴
    TRAIL_RUNNING = "trail_running"  # 越野跑鞋
    APPROACH = "approach"  # 接近鞋
    TENTS = "tents"  # 帐篷
    POLES = "poles"  # 登山杖
    BACKPACKS = "backpacks"  # 重装背包
    DAYPACKS = "daypacks"  # 日行包
    SLEEPING_BAGS = "sleeping_bags"  # 睡袋
    SLEEPING_PADS = "sleeping_pads"  # 睡垫
    HEADLAMPS = "headlamps"  # 头灯


class ReviewAuthority(BaseModel):
    source: str  # 测评机构：如 OGL, Switchback, CleverHiker, RunRepeat, SMZDM, 8264
    badge: str  # 如 Editors' Choice, #1 Best Overall, Best Buy, 神价爆款
    score: int | None = None  # 1-100 分制
    quote: str = ""  # 权威机构一句话评价（原文）
    url: str = ""  # 出处链接（评测页 / 榜单页）
    rank: int | None = None  # 该榜单内排名
    rank_total: int | None = None  # 该榜单参评总数
    badge_zh: str = ""  # 奖项中文译名
    quote_zh: str = ""  # 评价中文译文（机器翻译 + 术语校正）


class GearSpec(BaseModel):
    weight: str = ""  # 如 "455g"
    material: str = ""  # 如 "GORE-TEX Pro Most Rugged 3L (40D+80D)"
    waterproof_rating: str = ""  # 如 "28,000 mm"
    breathability: str = ""  # 如 "25,000 g/m²/24h (RET < 6)"
    fabric_density: str = ""  # 如 "40D / 80D 加强"
    scenarios: list[str] = Field(
        default_factory=list
    )  # 如 ["高海拔攀登", "暴风雨徒步", "城市通勤"]
    key_features: list[str] = Field(default_factory=list)  # 核心卖点清单


class ExternalLink(BaseModel):
    label: str  # 如 "什么值得买"、"小红书"
    url: str


class CnContent(BaseModel):
    """国内平台内容：什么值得买好价/原创、B站视频、小红书笔记。"""

    platform: str  # 什么值得买 / B站 / 小红书
    kind: str  # 好价 / 测评文章 / 视频 / 笔记
    title: str
    url: str
    author: str = ""
    metric_label: str = ""  # 值 / 收藏 / 播放 / 点赞
    metric_value: int = 0
    date: str = ""
    cover: str = ""
    price_cny: float | None = None
    mall: str = ""
    summary: str = ""


class CnPrice(BaseModel):
    """什么值得买好价汇总（已剔除离群价）。"""

    min_cny: float
    median_cny: float
    count: int
    latest_date: str = ""
    malls: list[str] = Field(default_factory=list)


class PriceGuide(BaseModel):
    price_cents: int  # 排序基准参考到手价 (分)
    msrp_cny: str  # 专柜指导标价，如 "¥6,400"
    deal_cny: str  # 国内大促券后参考价，如 "¥4,600~¥5,200"
    overseas_usd: str = ""  # 美元原价，如 "$600"
    overseas_landed_cny: str = ""  # 海淘落地到手折算价，如 "¥3,800~¥4,200"
    promo_tips: str = ""  # 优惠与凑单提示


class GearRankingItem(BaseModel):
    id: str  # 唯一 slug，如 "hardshell_arcteryx_beta_ar"
    name: str  # 国际英文名，如 "Arc'teryx Beta AR Jacket"
    name_cn: str  # 中文名，如 "始祖鸟 Beta AR 冲锋衣"
    brand: str  # 品牌 slug，如 "arcteryx"
    brand_name: str  # 品牌展示名，如 "Arc'teryx / 始祖鸟"
    category: GearCategory  # 品类 enum
    category_name: str  # 品类中文展示名
    price_tier: PriceTier  # 价位梯度
    price_tier_name: str  # 梯队中文名，如 "顶级专业旗舰"
    image: str  # 高清 CDN 图片链接
    rating_score: int | None = None  # OGL 实测总分 (满分 100)；仅有编辑推荐无打分时为空
    price_guide: PriceGuide  # 立体价格指南
    specs: GearSpec  # 详细技术物理规格
    authorities: list[ReviewAuthority]  # 权威榜单奖项与评价列表
    pros: list[str]  # 实测优点
    cons: list[str]  # 实测缺点/注意事项
    bottom_line: str  # 权威总评一句话
    gap_analysis: str  # 深度差价与性价比深度解析
    matched_style_number: str | None = None  # 系统内对应的 Style 款号（便于关联比价）
    gender: str = "unisex"  # men / women / unisex
    gender_name: str = "通用"
    brand_country: str = ""
    image_remote: str = ""  # 原始图片 URL（本地图失效时回退）
    image_credit: str = ""  # 图片来源站点
    score_basis: str = ""  # 评分口径说明
    spec_table: dict[str, str] = Field(default_factory=dict)  # 测评站完整规格表（原文）
    sub_scores: dict[str, float] = Field(default_factory=dict)  # 分项评分（满分 10）
    cn_links: list[ExternalLink] = Field(default_factory=list)  # 国内口碑/购买检索
    buy_links: list[ExternalLink] = Field(default_factory=list)  # 海外购买/评测
    pros_zh: list[str] = Field(default_factory=list)  # 优点中文
    cons_zh: list[str] = Field(default_factory=list)  # 缺点中文
    sub_scores_zh: dict[str, str] = Field(default_factory=dict)  # 分项名 英→中
    is_cn_brand: bool = False  # 国货品牌
    cn_price: CnPrice | None = None  # 国内好价汇总
    cn_query: str = ""  # 国内检索关键词
    cn_reviews: list[CnContent] = Field(default_factory=list)  # 国内口碑内容


class CategoryMeta(BaseModel):
    id: GearCategory
    name: str
    description: str
    icon_name: str
    total_count: int
    tier_counts: dict[str, int]


class CompareMatrixColumn(BaseModel):
    product: GearRankingItem
    highlight_strengths: list[str]
    target_users: str


class CompareMatrixResponse(BaseModel):
    items: list[GearRankingItem]
    attributes: list[str]
    category: GearCategory | None = None
    category_name: str = ""
    gap_summary: str = ""  # 跨价位差价核心原因总结
