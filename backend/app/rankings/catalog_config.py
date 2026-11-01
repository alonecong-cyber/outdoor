"""榜单品类与权威来源配置（构建脚本与 API 共用）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.rankings.schemas import GearCategory


@dataclass(frozen=True)
class CategoryInfo:
    id: GearCategory
    name: str
    short: str  # 拼中文名时用的品类后缀
    description: str
    icon_name: str
    scenarios: tuple[str, ...]
    transfer_fee_cny: int  # 转运费估算（按典型重量）


CATEGORIES: list[CategoryInfo] = [
    CategoryInfo(
        GearCategory.HARDSHELL,
        "硬壳冲锋衣",
        "硬壳冲锋衣",
        "全天候防暴雨、防狂风、抗撕裂的终极防护层",
        "mountain",
        ("高山攀登", "暴雨徒步", "滑雪"),
        90,
    ),
    CategoryInfo(
        GearCategory.RAIN_JACKET,
        "轻量防水夹克",
        "防水夹克",
        "比硬壳更轻更便宜，徒步/通勤/旅行的日常防雨层",
        "mountain",
        ("城市通勤", "徒步防雨", "旅行"),
        70,
    ),
    CategoryInfo(
        GearCategory.SOFTSHELL,
        "软壳",
        "软壳",
        "四向弹力、高透气、防风防泼水的高机动活动层",
        "filter",
        ("快速徒步", "攀岩", "城市通勤"),
        70,
    ),
    CategoryInfo(
        GearCategory.FLEECE,
        "抓绒中层",
        "抓绒",
        "动态排汗透气与静止锁温的保暖中层",
        "grid",
        ("秋冬中层", "营地保暖", "日常休闲"),
        70,
    ),
    CategoryInfo(
        GearCategory.BASELAYER,
        "排汗打底 / 秋衣",
        "打底",
        "贴身第一层：美利奴羊毛 / 化纤速干，导汗、调温、防异味",
        "check",
        ("贴身打底", "冬季保暖", "多日徒步"),
        50,
    ),
    CategoryInfo(
        GearCategory.DOWN,
        "羽绒服",
        "羽绒服",
        "高蓬松度羽绒，营地静态保暖与城市冬季通勤",
        "clock",
        ("冬季通勤", "营地保暖", "高海拔"),
        90,
    ),
    CategoryInfo(
        GearCategory.INSULATED,
        "棉服 / 人造保暖",
        "棉服",
        "湿水仍保暖的化纤填充，适合高强度动态保暖",
        "clock",
        ("动态保暖", "潮湿环境", "日常穿搭"),
        80,
    ),
    CategoryInfo(
        GearCategory.HIKING_PANTS,
        "徒步裤",
        "徒步裤",
        "弹力、耐磨、速干，徒步与日常通勤两用",
        "filter",
        ("徒步", "城市通勤", "攀岩"),
        60,
    ),
    CategoryInfo(
        GearCategory.RAIN_PANTS,
        "防水裤 / 雨裤",
        "防水裤",
        "暴雨与雪地的下半身防护",
        "mountain",
        ("暴雨徒步", "雪地", "骑行"),
        60,
    ),
    CategoryInfo(
        GearCategory.SOCKS,
        "户外袜",
        "袜子",
        "防水泡、缓冲、抗菌防臭的羊毛 / 功能袜",
        "bell",
        ("徒步", "越野跑", "日常"),
        30,
    ),
    CategoryInfo(
        GearCategory.SHOES,
        "徒步鞋（通勤+徒步）",
        "徒步鞋",
        "低帮轻量，城市通勤与轻徒步两不误",
        "arrow",
        ("城市通勤", "轻徒步", "旅行"),
        120,
    ),
    CategoryInfo(
        GearCategory.HIKING_BOOTS,
        "徒步靴（中高帮）",
        "徒步靴",
        "中高帮护踝，重装与复杂地形长线",
        "arrow",
        ("重装徒步", "复杂地形", "雪地"),
        150,
    ),
    CategoryInfo(
        GearCategory.TRAIL_RUNNING,
        "越野跑鞋",
        "越野跑鞋",
        "轻快抓地，也是轻量徒步党的心头好",
        "arrow",
        ("越野跑", "轻量徒步", "日常跑"),
        110,
    ),
    CategoryInfo(
        GearCategory.APPROACH,
        "接近鞋",
        "接近鞋",
        "徒步+攀爬混合地形，鞋头橡胶耐磨",
        "arrow",
        ("接近路段", "岩石地形", "旅行"),
        120,
    ),
    CategoryInfo(
        GearCategory.TENTS,
        "帐篷",
        "帐篷",
        "背包轻量帐 / 超轻帐 / 露营大帐",
        "mountain",
        ("背包徒步", "露营", "超轻长线"),
        150,
    ),
    CategoryInfo(
        GearCategory.POLES,
        "登山杖",
        "登山杖",
        "下坡护膝，分担冲击与复杂路段支撑",
        "chevron",
        ("徒步下坡", "长线重装", "越野跑"),
        80,
    ),
    CategoryInfo(
        GearCategory.BACKPACKS,
        "重装背包",
        "背包",
        "40L+ 多日徒步背负系统",
        "grid",
        ("多日徒步", "重装", "超轻长线"),
        150,
    ),
    CategoryInfo(
        GearCategory.DAYPACKS,
        "日行包",
        "日行包",
        "15–35L 一日徒步 / 通勤两用",
        "grid",
        ("一日徒步", "城市通勤", "旅行"),
        80,
    ),
    CategoryInfo(
        GearCategory.SLEEPING_BAGS,
        "睡袋",
        "睡袋",
        "羽绒 / 化纤睡袋，按温标与重量取舍",
        "clock",
        ("背包露营", "高海拔", "超轻长线"),
        120,
    ),
    CategoryInfo(
        GearCategory.SLEEPING_PADS,
        "防潮垫 / 睡垫",
        "睡垫",
        "R 值决定保暖，充气 / 自充 / 泡沫垫",
        "grid",
        ("背包露营", "冬季露营", "自驾露营"),
        100,
    ),
    CategoryInfo(
        GearCategory.HEADLAMPS,
        "头灯",
        "头灯",
        "流明、续航、重量与防水",
        "bell",
        ("夜爬", "露营", "越野跑"),
        40,
    ),
]

CATEGORY_BY_ID: dict[GearCategory, CategoryInfo] = {c.id: c for c in CATEGORIES}

# (品类, 性别, 站点, URL)
SOURCES: list[tuple[GearCategory, str, str, str]] = []
_OGL = "https://www.outdoorgearlab.com/topics/"
_SBT = "https://www.switchbacktravel.com/"
for _cat, _gender, _path in [
    (GearCategory.HARDSHELL, "men", "clothing-mens/best-hardshell-jacket"),
    (GearCategory.HARDSHELL, "women", "clothing-womens/best-hardshell-jacket-womens"),
    (GearCategory.RAIN_JACKET, "men", "clothing-mens/best-rain-jacket-men"),
    (GearCategory.RAIN_JACKET, "women", "clothing-womens/best-rain-jacket-womens"),
    (GearCategory.SOFTSHELL, "men", "clothing-mens/best-softshell-jacket-men"),
    (GearCategory.SOFTSHELL, "women", "clothing-womens/best-softshell-jacket-womens"),
    (GearCategory.FLEECE, "men", "clothing-mens/best-fleece-jacket-men"),
    (GearCategory.FLEECE, "women", "clothing-womens/best-fleece-jacket-womens"),
    (GearCategory.BASELAYER, "men", "clothing-mens/best-base-layer-men"),
    (GearCategory.BASELAYER, "women", "clothing-womens/best-base-layer-womens"),
    (GearCategory.BASELAYER, "men", "clothing-mens/best-long-underwear-men"),
    (GearCategory.BASELAYER, "women", "clothing-womens/best-long-underwear-womens"),
    (GearCategory.DOWN, "men", "clothing-mens/best-down-jacket-men"),
    (GearCategory.DOWN, "women", "clothing-womens/best-down-jacket-womens"),
    (GearCategory.INSULATED, "men", "clothing-mens/best-insulated-jacket-men"),
    (GearCategory.INSULATED, "women", "clothing-womens/best-insulated-jacket-womens"),
    (GearCategory.HIKING_PANTS, "men", "clothing-mens/best-hiking-pants-men"),
    (GearCategory.HIKING_PANTS, "women", "clothing-womens/best-hiking-pants-women"),
    (GearCategory.RAIN_PANTS, "men", "clothing-mens/best-rain-pants-men"),
    (GearCategory.RAIN_PANTS, "women", "clothing-womens/best-rain-pants-womens"),
    (GearCategory.SOCKS, "unisex", "shoes-and-boots/best-hiking-socks"),
    (GearCategory.SHOES, "men", "shoes-and-boots/best-hiking-shoes-men"),
    (GearCategory.SHOES, "women", "shoes-and-boots/best-hiking-shoes-womens"),
    (GearCategory.HIKING_BOOTS, "men", "shoes-and-boots/best-hiking-boots-men"),
    (GearCategory.HIKING_BOOTS, "women", "shoes-and-boots/best-hiking-boots-womens"),
    (GearCategory.TRAIL_RUNNING, "men", "shoes-and-boots/best-trail-running-shoes-men"),
    (GearCategory.TRAIL_RUNNING, "women", "shoes-and-boots/best-trail-running-shoes-womens"),
    (GearCategory.APPROACH, "men", "climbing/best-approach-shoes"),
    (GearCategory.TENTS, "unisex", "camping-and-hiking/best-backpacking-tent"),
    (GearCategory.TENTS, "unisex", "camping-and-hiking/best-ultralight-tent"),
    (GearCategory.TENTS, "unisex", "camping-and-hiking/best-camping-tent"),
    (GearCategory.POLES, "unisex", "camping-and-hiking/best-trekking-poles"),
    (GearCategory.BACKPACKS, "unisex", "camping-and-hiking/best-backpacks-backpacking"),
    (GearCategory.BACKPACKS, "women", "camping-and-hiking/best-backpacks-womens"),
    (GearCategory.DAYPACKS, "unisex", "camping-and-hiking/best-daypack"),
    (GearCategory.SLEEPING_BAGS, "unisex", "camping-and-hiking/best-backpacking-sleeping-bag"),
    (GearCategory.SLEEPING_PADS, "unisex", "camping-and-hiking/best-sleeping-pad"),
    (GearCategory.HEADLAMPS, "unisex", "camping-and-hiking/best-headlamp"),
]:
    SOURCES.append((_cat, _gender, "OutdoorGearLab", _OGL + _path))
for _cat, _slug in [
    (GearCategory.HARDSHELL, "best-hardshell-jackets"),
    (GearCategory.RAIN_JACKET, "best-rain-jackets"),
    (GearCategory.SOFTSHELL, "best-softshell-jackets"),
    (GearCategory.FLEECE, "best-fleece-jackets"),
    (GearCategory.BASELAYER, "best-baselayers"),
    (GearCategory.DOWN, "best-down-jackets"),
    (GearCategory.INSULATED, "best-synthetic-insulated-jackets"),
    (GearCategory.HIKING_PANTS, "best-hiking-pants"),
    (GearCategory.RAIN_PANTS, "best-rain-pants"),
    (GearCategory.SOCKS, "best-hiking-socks"),
    (GearCategory.SHOES, "best-hiking-shoes"),
    (GearCategory.HIKING_BOOTS, "best-hiking-boots"),
    (GearCategory.TRAIL_RUNNING, "best-trail-running-shoes"),
    (GearCategory.APPROACH, "best-approach-shoes"),
    (GearCategory.TENTS, "best-backpacking-tents"),
    (GearCategory.TENTS, "best-camping-tents"),
    (GearCategory.POLES, "best-trekking-poles"),
    (GearCategory.BACKPACKS, "best-backpacking-backpacks"),
    (GearCategory.DAYPACKS, "best-daypacks-hiking"),
    (GearCategory.SLEEPING_BAGS, "best-backpacking-sleeping-bags"),
    (GearCategory.SLEEPING_PADS, "best-backpacking-sleeping-pads"),
    (GearCategory.HEADLAMPS, "best-headlamps"),
]:
    SOURCES.append((_cat, "unisex", "Switchback Travel", _SBT + _slug))
