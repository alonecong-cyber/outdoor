"""人工校对的固定译名：OGL 分项评分名、榜单奖项名（badges_zh.json）。优先级高于机器翻译。"""

import json
from pathlib import Path

BADGES_ZH: dict[str, str] = json.loads(
    Path(__file__).with_name("badges_zh.json").read_text(encoding="utf-8")
)

SUB_SCORES_ZH: dict[str, str] = {
    "Adaptability": "适应性",
    "Adjustability": "可调节性",
    "Battery Life": "续航",
    "Breathability": "透气性",
    "Climbing Ability": "攀爬性能",
    "Close Proximity": "近距离照明",
    "Comfort": "舒适度",
    "Comfort and Fit": "舒适与合身",
    "Comfort and Mobility": "舒适与活动性",
    "Construction Quality": "做工质量",
    "Drying Speed": "速干性",
    "Durability": "耐用性",
    "Ease of Set-Up": "搭建便利性",
    "Ease of Setup": "搭建便利性",
    "Ease of Use": "易用性",
    "Family Friendliness": "家庭友好度",
    "Features": "功能配置",
    "Features and Design": "功能与设计",
    "Foot Protection": "足部保护",
    "Hiking Comfort": "徒步舒适度",
    "Layering Ability": "叠穿适配性",
    "Livability": "居住空间",
    "Locking and Adjustability": "锁扣与调节",
    "Mobility": "活动性",
    "Mobility and Fit": "活动性与合身",
    "Packability": "收纳性",
    "Packed Size": "收纳体积",
    "Portability": "便携性",
    "Quality": "品质",
    "Quality of Construction": "做工质量",
    "Space and Comfort": "空间与舒适",
    "Stability": "稳定性",
    "Support": "支撑性",
    "Traction": "抓地力",
    "Trail Finding": "寻路照明",
    "Venting and Breathability": "通风与透气",
    "Versatility": "多用途性",
    "Warmth": "保暖性",
    "Water Resistance": "防水性",
    "Weather Protection": "防护性",
    "Weather Resistance": "防风雨性能",
    "Weight": "重量",
    "Weight and Packability": "重量与收纳",
    "Weight-to-Volume Ratio": "重量体积比",
    "Wicking and Breathability": "排汗与透气",
}
