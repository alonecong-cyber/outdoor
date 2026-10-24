"""归一化：从标题/提示字段提取款号、颜色、尺码（M2，验收 ≥90% 准确率）。

提取策略（PRD §6）：
1. 款号：品牌正则（始祖鸟 5 位数字 / TNF NF0A… / Patagonia 5 位数字）优先，
   词典优先级：style_number_hint > 标题正则；
2. 颜色：中英颜色词典 + 常见品牌色名（长词优先，避免"军绿"被"绿"截胡）；
3. 尺码：字母码（XS–4XL）+ 鞋码（US/EU/UK），中文标题里"X码"兜底。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# ---------- 款号 ----------

ARCTERYX_STYLE_RE = re.compile(r"\b(\d{5})\b")
TNF_STYLE_RE = re.compile(r"\b(NF[0-9A-Z]{5,9})\b")
PATAGONIA_STYLE_RE = re.compile(r"\b(\d{5}(?:-\w{1,3})?)\b")
# 哥伦比亚 XE5743 / PM4951：两字母+4-5 位数字
COLUMBIA_STYLE_RE = re.compile(r"\b([A-Z]{2}\d{4,5})\b")
# 国产户外（骆驼/伯希和等）：标题品牌词后紧跟的 4 位款号，如 "骆驼 3514"
CN_OUTDOOR_STYLE_RE = re.compile(r"\b(\d{4})\b")
# 通用款号形态（跨品牌兜底，均要求词边界，避开尺码/年份/颜色词）：
# - 字母 1-3 位 + 数字 3-7 位：LH300 / MT6325102 / A6687 / J035795 / MH100
# - 数字字母交替 4 位短码（TNF 新码）：8P0D / 8AV7
# - 4 位数字 + 2 位字母（大鹅）：1925MB
GENERIC_LEAD_ALPHA_RE = re.compile(r"\b([A-Z]{1,3}\d{3,7})\b")
GENERIC_ALTERNATING_RE = re.compile(r"\b(\d[A-Z]\d[A-Z])\b")
GENERIC_NUM_ALPHA_RE = re.compile(r"\b(\d{4}[A-Z]{2})\b")

BRAND_STYLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "arcteryx": ARCTERYX_STYLE_RE,
    "the-north-face": TNF_STYLE_RE,
    "tnf": TNF_STYLE_RE,
    "patagonia": PATAGONIA_STYLE_RE,
    "columbia": COLUMBIA_STYLE_RE,
    "camel": CN_OUTDOOR_STYLE_RE,
    "pelliot": CN_OUTDOOR_STYLE_RE,
    "kailas": CN_OUTDOOR_STYLE_RE,
}

# ---------- 颜色（长词在前，防短词抢先命中） ----------

COLOR_TERMS = [
    # 英文（品牌常用色名）
    "black",
    "black heather",
    "heather black",
    "black sapphire",
    "white",
    "grey",
    "gray",
    "navy",
    "blue",
    "royal blue",
    "sky blue",
    "forest green",
    "olive green",
    "green",
    "khaki",
    "tan",
    "brown",
    "beige",
    "red",
    "burgundy",
    "orange",
    "amber",
    "yellow",
    "gold",
    "purple",
    "violet",
    "pink",
    "teal",
    "turquoise",
    "cyan",
    "military green",
    "camo",
    "camouflage",
    "graphene grey",
    "osprey",
    "solitude",
    "pumice grey",
    "canyon brown",
    # 中文
    "黑色",
    "白色",
    "灰色",
    "深灰",
    "浅灰",
    "藏青",
    "海军蓝",
    "蓝色",
    "天蓝",
    "森林绿",
    "橄榄绿",
    "军绿",
    "绿色",
    "卡其",
    "棕",
    "棕色",
    "米色",
    "红色",
    "酒红",
    "砖红",
    "橙色",
    "琥珀",
    "黄色",
    "金色",
    "紫色",
    "粉",
    "粉色",
    "青色",
    "湖蓝",
    "迷彩",
    "花灰",
]
# ---------- 尺码 ----------

LETTER_SIZE_RE = re.compile(r"\b(XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)\b")
US_SIZE_RE = re.compile(r"\bUS\s*(\d{1,2}(?:\.\d)?)\b", re.I)
EU_SIZE_RE = re.compile(r"\bEU\s*(\d{2})\b", re.I)
UK_SIZE_RE = re.compile(r"\bUK\s*(\d{1,2}(?:\.\d)?)\b", re.I)
CN_SIZE_RE = re.compile(r"\b(\d{3}/\d{2,3}[A-Z]?)\b")  # 175/96A 国标码

SIZE_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "2XL": 5, "XXXL": 6, "3XL": 6}


# 仅收录确认等价的色名；深浅色、品牌专有色不能按包含关系折叠。
COLOR_ALIASES: dict[str, str] = {
    "黑色": "black",
    "白色": "white",
    "灰色": "grey",
    "gray": "grey",
    "深灰": "dark grey",
    "dark gray": "dark grey",
    "浅灰": "light grey",
    "light gray": "light grey",
    "藏青": "navy",
    "海军蓝": "navy",
    "navy blue": "navy",
    "蓝色": "blue",
    "深蓝": "dark blue",
    "浅蓝": "light blue",
    "天蓝": "sky blue",
    "深绿": "dark green",
    "浅绿": "light green",
    "森林绿": "forest green",
    "橄榄绿": "olive green",
    "军绿": "military green",
    "绿色": "green",
    "卡其": "khaki",
    "棕": "brown",
    "棕色": "brown",
    "米色": "beige",
    "红色": "red",
    "酒红": "burgundy",
    "砖红": "brick red",
    "橙色": "orange",
    "琥珀": "amber",
    "黄色": "yellow",
    "金色": "gold",
    "紫色": "purple",
    "粉": "pink",
    "粉色": "pink",
    "青色": "cyan",
    "湖蓝": "lake blue",
    "迷彩": "camo",
    "camouflage": "camo",
    "花灰": "heather grey",
    "heather gray": "heather grey",
}
_COLOR_LOOKUP = sorted(
    set(COLOR_TERMS) | set(COLOR_ALIASES) | set(COLOR_ALIASES.values()),
    key=lambda term: (-len(term), term),
)


def normalize_color(color: str) -> str:
    """规范化已知同义色名；未知色保留其完整名称，绝不按子串或相似度合并。"""
    value = " ".join(color.lower().split())
    return COLOR_ALIASES.get(value, value)


def normalize_size(size: str) -> str:
    """统一大小写、鞋码空格及字母码别名，保留不同鞋码体系。"""
    value = "".join(size.upper().split())
    return {"2XL": "XXL", "3XL": "XXXL"}.get(value, value)


@dataclass
class ExtractedFeatures:
    """从 listing 标题/提示提取的结构化特征。"""

    style_number: str = ""
    color: str = ""
    size: str = ""
    brand_slug: str = ""
    reasons: list[str] = field(default_factory=list)


def extract_style_number(text: str, brand_slug: str = "", style_hint: str = "") -> str:
    """款号提取：hint 优先 → 品牌正则 → 通用 5 位数字。"""
    if style_hint and re.fullmatch(r"[0-9A-Z-]{4,12}", style_hint.strip().upper()):
        return style_hint.strip().upper()
    pattern = BRAND_STYLE_PATTERNS.get(brand_slug)
    if pattern:
        m = pattern.search(text)
        if m:
            return m.group(1).upper()
    # 通用兜底：品牌专属码 → 品牌码形态 → 通用款号形态 → 孤立 5 位数字
    for regex in (
        TNF_STYLE_RE,
        ARCTERYX_STYLE_RE,
        GENERIC_LEAD_ALPHA_RE,
        GENERIC_ALTERNATING_RE,
        GENERIC_NUM_ALPHA_RE,
    ):
        m = regex.search(text)
        if m:
            return m.group(1).upper()
    return ""


def extract_color(text: str, color_hint: str = "") -> str:
    """颜色提取：hint 优先（原样保留），否则词典长词优先。"""
    if color_hint:
        return color_hint.strip()
    lower = text.lower()
    for term in _COLOR_LOOKUP:
        # ASCII 字母边界允许“Black男款”，但不能把 Blackbird 当作 black。
        pattern = rf"(?<![a-z]){re.escape(term)}(?![a-z])" if term.isascii() else re.escape(term)
        if re.search(pattern, lower):
            return term
    return ""


def extract_size(text: str) -> str:
    """尺码提取：字母码 > 鞋码（US/EU/UK）> 国标码。"""
    m = LETTER_SIZE_RE.search(text)
    if m:
        return m.group(1)
    for regex in (US_SIZE_RE, EU_SIZE_RE, UK_SIZE_RE):
        m = regex.search(text)
        if m:
            return m.group(0).upper().replace(" ", "")
    m = CN_SIZE_RE.search(text)
    if m:
        return m.group(1)
    return ""


def extract_features(
    title: str,
    *,
    brand_slug: str = "",
    style_hint: str = "",
    color_hint: str = "",
    size_hint: str = "",
) -> ExtractedFeatures:
    """一站式提取。size_hint（来自 SKU 规格字段）优先于标题。"""
    feats = ExtractedFeatures(brand_slug=brand_slug)
    feats.style_number = extract_style_number(title, brand_slug, style_hint)
    feats.color = normalize_color(extract_color(title, color_hint))
    feats.size = normalize_size(size_hint) or normalize_size(extract_size(title))
    if feats.style_number:
        feats.reasons.append(f"款号={feats.style_number}")
    if feats.color:
        feats.reasons.append(f"颜色={feats.color}")
    if feats.size:
        feats.reasons.append(f"尺码={feats.size}")
    return feats
