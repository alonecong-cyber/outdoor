"""国内口碑精选：海外测评站基本不覆盖的国货 / 国内常买款。

这里只列"品牌 + 型号 + 品类"作为检索种子；价格、图片、口碑全部来自什么值得买 / B站
公开接口的真实返回（scripts/enrich_cn.py）。接口里匹配不到好价的型号会被自动丢弃，
所以列错或停产的型号不会进入榜单。
"""

from __future__ import annotations

# (品牌 slug, 型号, 品类, 性别)
CN_PICKS: list[tuple[str, str, str, str]] = [
    # 硬壳 / 防水夹克
    ("kailas", "MONT-X", "hardshell", "unisex"),
    ("kailas", "风暴", "hardshell", "unisex"),
    ("pelliot", "巅峰", "hardshell", "unisex"),
    ("pelliot", "山壳", "hardshell", "unisex"),
    ("camel", "幻影黑", "hardshell", "unisex"),
    ("toread", "冲锋衣 三合一", "hardshell", "unisex"),
    ("decathlon", "MH500", "hardshell", "unisex"),
    ("decathlon", "MT500", "rain_jacket", "unisex"),
    ("decathlon", "MH900", "rain_jacket", "unisex"),
    ("pioneercamp", "冲锋衣", "hardshell", "unisex"),
    ("blackdeer", "冲锋衣", "hardshell", "unisex"),
    ("bosideng", "冲锋衣", "hardshell", "unisex"),
    # 软壳 / 抓绒
    ("kailas", "软壳", "softshell", "unisex"),
    ("decathlon", "MT900 软壳", "softshell", "unisex"),
    ("pelliot", "软壳", "softshell", "unisex"),
    ("decathlon", "MH520", "fleece", "unisex"),
    ("decathlon", "MH500 抓绒", "fleece", "unisex"),
    ("kailas", "Polartec", "fleece", "unisex"),
    ("pelliot", "抓绒", "fleece", "unisex"),
    ("pioneercamp", "抓绒", "fleece", "unisex"),
    # 打底 / 秋衣
    ("decathlon", "MT500 美利奴", "baselayer", "unisex"),
    ("kailas", "美利奴", "baselayer", "unisex"),
    ("uniqlo", "HEATTECH", "baselayer", "unisex"),
    ("uniqlo", "AIRism", "baselayer", "unisex"),
    ("pelliot", "速干衣", "baselayer", "unisex"),
    # 羽绒 / 棉服
    ("bosideng", "登峰", "down", "unisex"),
    ("bosideng", "极寒", "down", "unisex"),
    ("blackice", "羽绒服", "down", "unisex"),
    ("kailas", "羽绒服", "down", "unisex"),
    ("pelliot", "羽绒服", "down", "unisex"),
    ("uniqlo", "高级轻型羽绒", "down", "unisex"),
    ("decathlon", "MT900 羽绒", "down", "unisex"),
    ("decathlon", "MH500 棉服", "insulated", "unisex"),
    # 裤
    ("decathlon", "MH500 徒步裤", "hiking_pants", "unisex"),
    ("kailas", "速干裤", "hiking_pants", "unisex"),
    ("pelliot", "软壳裤", "hiking_pants", "unisex"),
    ("camel", "冲锋裤", "rain_pants", "unisex"),
    ("decathlon", "MT500 防水裤", "rain_pants", "unisex"),
    # 袜子
    ("kailas", "羊毛袜", "socks", "unisex"),
    ("decathlon", "MT500 袜", "socks", "unisex"),
    ("blackice", "羊毛袜", "socks", "unisex"),
    # 鞋（通勤+徒步 / 靴 / 越野跑）
    ("kailas", "徒步鞋", "shoes", "unisex"),
    ("decathlon", "MH500 徒步鞋", "shoes", "unisex"),
    ("decathlon", "MH100", "shoes", "unisex"),
    ("camel", "徒步鞋", "shoes", "unisex"),
    ("pelliot", "徒步鞋", "shoes", "unisex"),
    ("toread", "徒步鞋", "shoes", "unisex"),
    ("decathlon", "MH500 MID", "hiking_boots", "unisex"),
    ("kailas", "高帮", "hiking_boots", "unisex"),
    ("kailas", "FUGA EX", "trail_running", "unisex"),
    ("kailas", "FUGA DU", "trail_running", "unisex"),
    ("kailas", "FUGA Pro", "trail_running", "unisex"),
    ("anta", "越野跑鞋", "trail_running", "unisex"),
    ("lining", "越野跑鞋", "trail_running", "unisex"),
    ("xtep", "越野跑鞋", "trail_running", "unisex"),
    ("decathlon", "Kiprun", "trail_running", "unisex"),
    # 帐篷
    ("naturehike", "云尚", "tents", "unisex"),
    ("naturehike", "Mongar", "tents", "unisex"),
    ("naturehike", "云舟", "tents", "unisex"),
    ("mobigarden", "冷山", "tents", "unisex"),
    ("mobigarden", "零尘", "tents", "unisex"),
    ("lanshan", "云梦", "tents", "unisex"),
    ("blackdeer", "帐篷", "tents", "unisex"),
    ("decathlon", "MT900 帐篷", "tents", "unisex"),
    ("decathlon", "2 Seconds", "tents", "unisex"),
    ("camel", "帐篷", "tents", "unisex"),
    # 登山杖
    ("kailas", "登山杖", "poles", "unisex"),
    ("blackice", "登山杖", "poles", "unisex"),
    ("naturehike", "登山杖", "poles", "unisex"),
    ("decathlon", "MT500 登山杖", "poles", "unisex"),
    ("lanshan", "登山杖", "poles", "unisex"),
    # 背包
    ("kailas", "背包", "backpacks", "unisex"),
    ("decathlon", "MT500 背包", "backpacks", "unisex"),
    ("lanshan", "起点", "backpacks", "unisex"),
    ("naturehike", "背包", "backpacks", "unisex"),
    ("decathlon", "NH100", "daypacks", "unisex"),
    ("decathlon", "MH500 20L", "daypacks", "unisex"),
    # 睡袋 / 睡垫
    ("blackice", "睡袋", "sleeping_bags", "unisex"),
    ("naturehike", "羽绒睡袋", "sleeping_bags", "unisex"),
    ("mobigarden", "睡袋", "sleeping_bags", "unisex"),
    ("naturehike", "充气睡垫", "sleeping_pads", "unisex"),
    ("mobigarden", "自动充气垫", "sleeping_pads", "unisex"),
    ("decathlon", "充气睡垫", "sleeping_pads", "unisex"),
    # 头灯
    ("olight", "头灯", "headlamps", "unisex"),
    ("fenix", "HM65R", "headlamps", "unisex"),
    ("nitecore", "NU25", "headlamps", "unisex"),
    ("decathlon", "HL900", "headlamps", "unisex"),
]
