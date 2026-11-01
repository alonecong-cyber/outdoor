"""户外品牌词典：英文名（含常见写法）→ slug / 中文名 / 国家。

用于从测评站点的产品名里识别品牌、生成中文展示名。按别名长度倒序匹配，
避免 "The North Face" 被 "North" 之类短别名截断。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class Brand:
    slug: str
    name: str
    name_cn: str
    country: str
    aliases: tuple[str, ...] = ()


BRANDS: list[Brand] = [
    Brand("arcteryx", "Arc'teryx", "始祖鸟", "加拿大", ("Arcteryx", "Arc’teryx")),
    Brand("patagonia", "Patagonia", "巴塔哥尼亚", "美国"),
    Brand("thenorthface", "The North Face", "北面", "美国", ("North Face", "TNF")),
    Brand("mammut", "Mammut", "猛犸象", "瑞士"),
    Brand("norrona", "Norrøna", "挪威小鸟", "挪威", ("Norrona",)),
    Brand("outdoorresearch", "Outdoor Research", "OR", "美国"),
    Brand("rab", "Rab", "Rab", "英国"),
    Brand("montbell", "Montbell", "梦倍路", "日本", ("Mont-bell", "mont-bell")),
    Brand("marmot", "Marmot", "土拨鼠", "美国"),
    Brand("mountainhardwear", "Mountain Hardwear", "山浩", "美国"),
    Brand("columbia", "Columbia", "哥伦比亚", "美国"),
    Brand("rei", "REI Co-op", "REI", "美国", ("REI", "REl Co-op")),
    Brand("helly", "Helly Hansen", "海丽汉森", "挪威"),
    Brand("himali", "Himali", "Himali", "美国"),
    Brand("lasportiva", "La Sportiva", "拉思珀蒂瓦", "意大利"),
    Brand("salomon", "Salomon", "萨洛蒙", "法国"),
    Brand("blackdiamond", "Black Diamond", "黑钻", "美国", ("BD",)),
    Brand("fjallraven", "Fjällräven", "北极狐", "瑞典", ("Fjallraven",)),
    Brand("haglofs", "Haglöfs", "火柴棍", "瑞典", ("Haglofs",)),
    Brand("jackwolfskin", "Jack Wolfskin", "狼爪", "德国"),
    Brand("vaude", "Vaude", "巍德", "德国"),
    Brand("ortovox", "Ortovox", "Ortovox", "德国"),
    Brand("dynafit", "Dynafit", "Dynafit", "德国"),
    Brand("millet", "Millet", "觅乐", "法国"),
    Brand("decathlon", "Decathlon", "迪卡侬", "法国", ("Quechua", "Forclaz")),
    Brand("kuhl", "Kuhl", "Kuhl", "美国", ("KÜHL",)),
    Brand("prana", "prAna", "prAna", "美国", ("Prana",)),
    Brand("eddiebauer", "Eddie Bauer", "艾迪堡", "美国"),
    Brand("llbean", "L.L.Bean", "L.L.Bean", "美国", ("LL Bean", "L.L. Bean")),
    Brand("cotopaxi", "Cotopaxi", "Cotopaxi", "美国"),
    Brand("frogg", "Frogg Toggs", "Frogg Toggs", "美国"),
    Brand("enlightened", "Enlightened Equipment", "EE", "美国"),
    Brand("feathered", "Feathered Friends", "Feathered Friends", "美国"),
    Brand("westernmountaineering", "Western Mountaineering", "西部山地", "美国"),
    Brand("nemo", "NEMO", "NEMO", "美国", ("Nemo",)),
    Brand("bigagnes", "Big Agnes", "比格尼斯", "美国"),
    Brand("msr", "MSR", "MSR", "美国"),
    Brand("zpacks", "Zpacks", "Zpacks", "美国"),
    Brand("durston", "Durston", "Durston", "加拿大", ("Durston Gear",)),
    Brand("gossamer", "Gossamer Gear", "Gossamer Gear", "美国"),
    Brand("hyperlite", "Hyperlite Mountain Gear", "HMG", "美国", ("Hyperlite",)),
    Brand("tarptent", "Tarptent", "Tarptent", "美国"),
    Brand("sixmoon", "Six Moon Designs", "Six Moon", "美国"),
    Brand("seatosummit", "Sea to Summit", "海峰", "澳大利亚"),
    Brand("thermarest", "Therm-a-Rest", "Therm-a-Rest", "美国", ("Thermarest", "Therm-A-Rest")),
    Brand("exped", "Exped", "Exped", "瑞士"),
    Brand("klymit", "Klymit", "Klymit", "美国"),
    Brand("coleman", "Coleman", "科勒曼", "美国"),
    Brand("kelty", "Kelty", "Kelty", "美国"),
    Brand("marmotgear", "Marmot", "土拨鼠", "美国"),
    Brand("hilleberg", "Hilleberg", "希尔伯格", "瑞典"),
    Brand("snowpeak", "Snow Peak", "雪峰", "日本"),
    Brand("naturehike", "Naturehike", "挪客", "中国"),
    Brand("mobigarden", "MobiGarden", "牧高笛", "中国"),
    Brand("kailas", "KAILAS", "凯乐石", "中国", ("Kailas",)),
    Brand("toread", "Toread", "探路者", "中国"),
    Brand("pelliot", "Pelliot", "伯希和", "中国"),
    Brand("osprey", "Osprey", "小鹰", "美国"),
    Brand("gregory", "Gregory", "格里高利", "美国"),
    Brand("deuter", "Deuter", "多特", "德国"),
    Brand("mysteryranch", "Mystery Ranch", "神秘农场", "美国"),
    Brand("ula", "ULA", "ULA", "美国", ("ULA Equipment",)),
    Brand("granite", "Granite Gear", "Granite Gear", "美国"),
    Brand("kelty_pack", "Kelty", "Kelty", "美国"),
    Brand("leki", "Leki", "莱基", "德国", ("LEKI",)),
    Brand("komperdell", "Komperdell", "Komperdell", "奥地利"),
    Brand("cascade", "Cascade Mountain Tech", "Cascade", "美国"),
    Brand("trekology", "Trekology", "Trekology", "美国"),
    Brand("darntough", "Darn Tough", "Darn Tough", "美国"),
    Brand("smartwool", "Smartwool", "Smartwool", "美国"),
    Brand("icebreaker", "Icebreaker", "Icebreaker", "新西兰"),
    Brand("injinji", "Injinji", "Injinji", "美国"),
    Brand("farmtofeet", "Farm to Feet", "Farm to Feet", "美国"),
    Brand("wigwam", "Wigwam", "Wigwam", "美国"),
    Brand("bombas", "Bombas", "Bombas", "美国"),
    Brand("feetures", "Feetures", "Feetures", "美国"),
    Brand("balega", "Balega", "Balega", "南非"),
    Brand("stance", "Stance", "Stance", "美国"),
    Brand("swiftwick", "Swiftwick", "Swiftwick", "美国"),
    Brand("minus33", "Minus33", "Minus33", "美国"),
    Brand("ridgemerino", "Ridge Merino", "Ridge Merino", "美国"),
    Brand("woolx", "Woolx", "Woolx", "美国"),
    Brand("ombraz", "Ombraz", "Ombraz", "美国"),
    Brand("uniqlo", "Uniqlo", "优衣库", "日本"),
    Brand("ibex", "Ibex", "Ibex", "美国"),
    Brand("ridge", "Ridge", "Ridge", "美国"),
    Brand("duckworth", "Duckworth", "Duckworth", "美国"),
    Brand("allbirds", "Allbirds", "Allbirds", "美国"),
    Brand("merrell", "Merrell", "迈乐", "美国"),
    Brand("keen", "KEEN", "科恩", "美国", ("Keen",)),
    Brand("hoka", "Hoka", "HOKA", "美国", ("HOKA", "Hoka One One")),
    Brand("altra", "Altra", "Altra", "美国"),
    Brand("lowa", "Lowa", "LOWA", "德国", ("LOWA",)),
    Brand("scarpa", "Scarpa", "思卡帕", "意大利"),
    Brand("asolo", "Asolo", "Asolo", "意大利"),
    Brand("zamberlan", "Zamberlan", "赞贝拉", "意大利"),
    Brand("oboz", "Oboz", "Oboz", "美国"),
    Brand("vasque", "Vasque", "Vasque", "美国"),
    Brand("danner", "Danner", "丹纳", "美国"),
    Brand("timberland", "Timberland", "添柏岚", "美国"),
    Brand("adidas", "Adidas", "阿迪达斯", "德国", ("adidas", "Adidas Terrex", "adidas Terrex")),
    Brand("nike", "Nike", "耐克", "美国"),
    Brand("brooks", "Brooks", "布鲁克斯", "美国"),
    Brand("saucony", "Saucony", "索康尼", "美国"),
    Brand("newbalance", "New Balance", "新百伦", "美国"),
    Brand("on", "On", "昂跑", "瑞士", ("On Running", "On Cloud")),
    Brand("topo", "Topo Athletic", "Topo", "美国", ("Topo",)),
    Brand("inov8", "Inov-8", "Inov-8", "英国", ("Inov8",)),
    Brand("vivobarefoot", "Vivobarefoot", "Vivobarefoot", "英国"),
    Brand("xeroshoes", "Xero Shoes", "Xero", "美国", ("Xero",)),
    Brand("teva", "Teva", "Teva", "美国"),
    Brand("chaco", "Chaco", "Chaco", "美国"),
    Brand("fivetennnis", "Five Ten", "Five Ten", "美国"),
    Brand("evolv", "Evolv", "Evolv", "美国"),
    Brand("mammutshoe", "Mammut", "猛犸象", "瑞士"),
    Brand("asics", "Asics", "亚瑟士", "日本", ("ASICS",)),
    Brand("mizuno", "Mizuno", "美津浓", "日本"),
    Brand("northside", "Northside", "Northside", "美国"),
    Brand("ahnu", "Ahnu", "Ahnu", "美国"),
    Brand("forsake", "Forsake", "Forsake", "美国"),
    Brand("kamik", "Kamik", "Kamik", "加拿大"),
    Brand("sorel", "Sorel", "Sorel", "加拿大"),
    Brand("bogs", "Bogs", "Bogs", "美国"),
    Brand("petzl", "Petzl", "Petzl", "法国"),
    Brand("nitecore", "Nitecore", "奈特科尔", "中国"),
    Brand("biolite", "BioLite", "BioLite", "美国", ("Biolite",)),
    Brand("ledlenser", "Ledlenser", "Ledlenser", "德国"),
    Brand("fenix", "Fenix", "菲尼克斯", "中国", ("Fenix Lighting",)),
    Brand("princeton", "Princeton Tec", "Princeton Tec", "美国"),
    Brand("energizer", "Energizer", "劲量", "美国"),
    Brand("coast", "Coast", "Coast", "美国"),
    Brand("olight", "Olight", "傲雷", "中国"),
    Brand("goal0", "Goal Zero", "Goal Zero", "美国"),
    Brand("stoic", "Stoic", "Stoic", "美国"),
    Brand("nemoequip", "NEMO Equipment", "NEMO", "美国"),
    Brand("alps", "ALPS Mountaineering", "ALPS", "美国", ("Alps Mountaineering",)),
    Brand("teton", "TETON Sports", "TETON", "美国", ("Teton Sports",)),
    Brand("marmotbag", "Marmot", "土拨鼠", "美国"),
    Brand("katabatic", "Katabatic Gear", "Katabatic", "美国", ("Katabatic",)),
    Brand("zenbivy", "Zenbivy", "Zenbivy", "美国"),
    Brand("paria", "Paria Outdoor Products", "Paria", "美国", ("Paria",)),
    Brand("lanshan", "3F UL Gear", "三峰出", "中国", ("3F UL",)),
    Brand("smartwoolsock", "Smartwool", "Smartwool", "美国"),
    Brand("vuori", "Vuori", "Vuori", "美国"),
    Brand("lululemon", "Lululemon", "露露乐蒙", "加拿大", ("lululemon",)),
    Brand("houdini", "Houdini", "Houdini", "瑞典"),
    Brand("peakperformance", "Peak Performance", "Peak Performance", "瑞典"),
    Brand("klattermusen", "Klättermusen", "攀山鼠", "瑞典", ("Klattermusen",)),
    Brand("bergans", "Bergans", "Bergans", "挪威"),
    Brand("sierradesigns", "Sierra Designs", "Sierra Designs", "美国"),
    Brand("ultimatedirection", "Ultimate Direction", "Ultimate Direction", "美国"),
    Brand("nathan", "Nathan", "Nathan", "美国"),
    Brand("camelbak", "CamelBak", "驼峰", "美国", ("Camelbak",)),
    Brand("topodesigns", "Topo Designs", "Topo Designs", "美国"),
    Brand("fjallravenpack", "Fjällräven", "北极狐", "瑞典"),
    Brand("bluffworks", "Bluffworks", "Bluffworks", "美国"),
    Brand("mountainsmith", "Mountainsmith", "Mountainsmith", "美国"),
    Brand("alpkit", "Alpkit", "Alpkit", "英国"),
    Brand("wildthings", "Wild Things", "Wild Things", "美国"),
    Brand("arcteryxveilance", "Veilance", "始祖鸟 Veilance", "加拿大"),
    Brand("gorewear", "Gorewear", "Gorewear", "德国", ("GOREWEAR",)),
    Brand("janji", "Janji", "Janji", "美国"),
    Brand("tracksmith", "Tracksmith", "Tracksmith", "美国"),
    Brand("nnormal", "NNormal", "NNormal", "西班牙", ("Nnormal",)),
    Brand("craft", "Craft", "Craft", "瑞典"),
    Brand("scott", "Scott", "斯科特", "瑞士"),
    Brand("rossignol", "Rossignol", "金鸡", "法国"),
    Brand("joma", "Joma", "Joma", "西班牙"),
    Brand("stio", "Stio", "Stio", "美国"),
    Brand("karitraa", "Kari Traa", "Kari Traa", "挪威"),
    Brand("lebent", "Le Bent", "Le Bent", "澳大利亚"),
    Brand("salewa", "Salewa", "沙乐华", "意大利"),
    Brand("slingfin", "SlingFin", "SlingFin", "美国"),
    Brand("helinox", "Helinox", "Helinox", "韩国"),
    Brand("norda", "Norda", "Norda", "加拿大"),
    Brand("mountainequipment", "Mountain Equipment", "Mountain Equipment", "英国"),
    Brand("monsroyale", "Mons Royale", "Mons Royale", "新西兰"),
    Brand("showerspass", "Showers Pass", "Showers Pass", "美国"),
    Brand("sockwell", "Sockwell", "Sockwell", "美国"),
    Brand("wrightsock", "Wrightsock", "Wrightsock", "美国"),
    Brand("artilect", "Artilect", "Artilect", "美国"),
    Brand("cep", "CEP", "CEP", "德国"),
    Brand("underarmour", "Under Armour", "安德玛", "美国"),
    Brand("carhartt", "Carhartt", "卡哈特", "美国"),
    Brand("filson", "Filson", "Filson", "美国"),
    Brand("merinotech", "Merino.tech", "Merino.tech", "美国"),
    Brand("meriwool", "Meriwool", "Meriwool", "美国"),
    Brand("nortiv8", "Nortiv 8", "Nortiv 8", "美国", ("NORTIV 8",)),
    Brand("sitka", "Sitka", "Sitka", "美国"),
    Brand("whiteduck", "White Duck", "White Duck", "美国"),
    Brand("zempire", "Zempire", "Zempire", "新西兰"),
    Brand("cabelas", "Cabela's", "Cabela's", "美国"),
    Brand("burgeon", "Burgeon", "Burgeon", "美国"),
    Brand("courier", "Courier", "Courier", "美国"),
    Brand("ombrazsun", "Ombraz", "Ombraz", "美国"),
    Brand("camel", "CAMEL", "骆驼", "中国", ("Camel",)),
    Brand("bosideng", "Bosideng", "波司登", "中国", ("BOSIDENG",)),
    Brand("blackice", "Black Ice", "黑冰", "中国", ("BLACKICE", "Blackice")),
    Brand("blackdeer", "Blackdeer", "黑鹿", "中国", ("BLACKDEER",)),
    Brand("pioneercamp", "Pioneer Camp", "拓路者", "中国"),
    Brand("anta", "ANTA", "安踏", "中国", ("Anta",)),
    Brand("lining", "Li-Ning", "李宁", "中国", ("LI-NING", "Li Ning")),
    Brand("xtep", "Xtep", "特步", "中国", ("XTEP",)),
    Brand("beneunder", "Beneunder", "蕉下", "中国"),
    Brand("bluefield", "Bluefield", "蓝色领域", "中国"),
    Brand("keenutility", "KEEN Utility", "KEEN Utility", "美国"),
]

# 去重：同 slug 后定义的仅作别名补充（如 marmotgear/marmotbag 并入 marmot）
_ALIAS_MERGE = {
    "ombrazsun": "ombraz",
    "marmotgear": "marmot",
    "marmotbag": "marmot",
    "kelty_pack": "kelty",
    "mammutshoe": "mammut",
    "smartwoolsock": "smartwool",
    "fjallravenpack": "fjallraven",
    "nemoequip": "nemo",
}

_BY_SLUG: dict[str, Brand] = {}
for _b in BRANDS:
    if _b.slug in _ALIAS_MERGE:
        continue
    _BY_SLUG[_b.slug] = _b


def _fold(text: str) -> str:
    text = text.replace("ø", "o").replace("Ø", "O").replace("’", "'")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


_ALIASES: list[tuple[str, str]] = []
for _b in BRANDS:
    slug = _ALIAS_MERGE.get(_b.slug, _b.slug)
    for alias in (_b.name, *_b.aliases):
        _ALIASES.append((_fold(alias), slug))
_ALIASES.sort(key=lambda x: len(x[0]), reverse=True)


def brand_by_slug(slug: str) -> Brand | None:
    return _BY_SLUG.get(slug)


def detect_brand(product_name: str) -> tuple[Brand | None, str]:
    """返回 (品牌, 去掉品牌前缀后的型号名)。识别不到时品牌为 None、型号为原名。"""
    folded = _fold(product_name)
    for alias, slug in _ALIASES:
        if re.match(rf"{re.escape(alias)}(?![a-z0-9])", folded):
            model = product_name[len(alias) :].strip(" -")
            return _BY_SLUG[slug], model
    return None, product_name
