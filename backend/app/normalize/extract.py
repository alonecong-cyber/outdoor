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

BRAND_STYLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "arcteryx": ARCTERYX_STYLE_RE,
    "the-north-face": TNF_STYLE_RE,
    "tnf": TNF_STYLE_RE,
    "patagonia": PATAGONIA_STYLE_RE,
}

# ---------- 颜色（长词在前，防短词抢先命中） ----------

COLOR_TERMS = [
    # 英文（品牌常用色名）
    "black", "white", "grey", "gray", "navy", "blue", "royal blue", "sky blue",
    "forest green", "olive green", "green", "khaki", "tan", "brown", "beige",
    "red", "burgundy", "orange", "amber", "yellow", "gold", "purple", "violet",
    "pink", "teal", "turquoise", "cyan", "military green", "camo", "camouflage",
    "graphene grey", "osprey", "solitude", "pumice grey", "canyon brown",
    # 中文
    "黑色", "白色", "灰色", "深灰", "浅灰", "藏青", "海军蓝", "蓝色", "天蓝",
    "森林绿", "橄榄绿", "军绿", "绿色", "卡其", "棕", "棕色", "米色", "红色",
    "酒红", "砖红", "橙色", "琥珀", "黄色", "金色", "紫色", "粉", "粉色",
    "青色", "湖蓝", "迷彩", "花灰",
]
# 去重并按长度降序（长词优先匹配）
_COLOR_LOOKUP = sorted(set(COLOR_TERMS), key=len, reverse=True)

# ---------- 尺码 ----------

LETTER_SIZE_RE = re.compile(
    r"\b(XXXS|XXS|XS|S|M|L|XL|XXL|XXXL|2XL|3XL|4XL|5XL)\b"
)
US_SIZE_RE = re.compile(r"\bUS\s*(\d{1,2}(?:\.\d)?)\b", re.I)
EU_SIZE_RE = re.compile(r"\bEU\s*(\d{2})\b", re.I)
UK_SIZE_RE = re.compile(r"\bUK\s*(\d{1,2}(?:\.\d)?)\b", re.I)
CN_SIZE_RE = re.compile(r"\b(\d{3}/\d{2,3}[A-Z]?)\b")  # 175/96A 国标码

SIZE_ORDER = {"XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4, "XXL": 5, "2XL": 5, "XXXL": 6, "3XL": 6}


@dataclass
class ExtractedFeatures:
    """从 listing 标题/提示提取的结构化特征。"""

    style_number: str = ""
    color: str = ""
    size: str = ""
    brand_slug: str = ""
    reasons: list[str] = field(default_factory=list)


def extract_style_number(
    text: str, brand_slug: str = "", style_hint: str = ""
) -> str:
    """款号提取：hint 优先 → 品牌正则 → 通用 5 位数字。"""
    if style_hint and re.fullmatch(r"[0-9A-Z-]{4,12}", style_hint.strip().upper()):
        return style_hint.strip().upper()
    pattern = BRAND_STYLE_PATTERNS.get(brand_slug)
    if pattern:
        m = pattern.search(text)
        if m:
            return m.group(1).upper()
    # 通用兜底：TNF 风格型号或孤立 5 位数字
    m = TNF_STYLE_RE.search(text) or ARCTERYX_STYLE_RE.search(text)
    return m.group(1).upper() if m else ""


def extract_color(text: str, color_hint: str = "") -> str:
    """颜色提取：hint 优先（原样保留），否则词典长词优先。"""
    if color_hint:
        return color_hint.strip()
    lower = text.lower()
    for term in _COLOR_LOOKUP:
        if term in lower:
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
    feats.color = extract_color(title, color_hint)
    feats.size = size_hint.strip().upper() or extract_size(title)
    if feats.style_number:
        feats.reasons.append(f"款号={feats.style_number}")
    if feats.color:
        feats.reasons.append(f"颜色={feats.color}")
    if feats.size:
        feats.reasons.append(f"尺码={feats.size}")
    return feats
