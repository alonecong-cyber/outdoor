"""品牌词典：线报标题 → 品牌识别，商品目录从线报里自动长出来的入口。

词典只是识别规则，不预置任何单品；命中即 get_or_create Brand，
未命中的线报照常入库展示（matched_variant_id = NULL），绝不猜。
"""

from __future__ import annotations

import re

# slug → (英文名, 中文名, 别名)。slug 与既有 Brand.slug 保持一致。
BRAND_ALIASES: dict[str, tuple[str, str, tuple[str, ...]]] = {
    "arcteryx": ("Arc'teryx", "始祖鸟", ("arcteryx", "arc'teryx", "始祖鸟", "ARC TERYX")),
    "the-north-face": (
        "The North Face",
        "北面",
        ("the north face", "northface", "北面", "乐斯菲斯"),
    ),
    "tnf": ("The North Face", "北面", ()),
    "patagonia": ("Patagonia", "巴塔哥尼亚", ("patagonia", "巴塔哥尼亚", "巴塔")),
    "mammut": ("Mammut", "猛犸象", ("mammut", "猛犸象", "长毛象")),
    "marmot": ("Marmot", "土拨鼠", ("marmot", "土拨鼠")),
    "mountain-hardwear": ("Mountain Hardwear", "山浩", ("mountain hardwear", "山浩", "螺母")),
    "columbia": ("Columbia", "哥伦比亚", ("columbia", "哥伦比亚")),
    "kailas": ("KAILAS", "凯乐石", ("kailas", "凯乐石")),
    "blackyak": ("BLACKYAK", "布来亚克", ("blackyak", "black yak", "布来亚克")),
    "fjallraven": ("Fjällräven", "北极狐", ("fjallraven", "fjällräven", "北极狐")),
    "helly-hansen": ("Helly Hansen", "海丽汉森", ("helly hansen", "hellyhansen", "海丽汉森", "hh")),
    "salomon": ("Salomon", "萨洛蒙", ("salomon", "萨洛蒙")),
    "decathlon": ("Decathlon", "迪卡侬", ("decathlon", "迪卡侬")),
    "camel": ("Camel", "骆驼", ("camel", "骆驼", "骆驼牌")),
    "pelliot": ("Pelliot", "伯希和", ("pelliot", "伯希和")),
    "skechers": ("Skechers", "斯凯奇", ("skechers", "斯凯奇")),
    "anta": ("ANTA", "安踏", ("anta", "安踏")),
    "toreador": ("Toreador", "探路者", ("toreador", "探路者")),
    "thenorthface-cn": ("The North Face", "北面", ()),
}

# tnf / thenorthface-cn 是历史别名，指向 the-north-face
_BRAND_REDIRECTS = {"tnf": "the-north-face", "thenorthface-cn": "the-north-face"}

# 展示用（前端品牌筛选 chips）
OUTDOOR_BRANDS: list[tuple[str, str]] = [
    ("arcteryx", "始祖鸟"),
    ("the-north-face", "北面"),
    ("patagonia", "巴塔哥尼亚"),
    ("mammut", "猛犸象"),
    ("marmot", "土拨鼠"),
    ("columbia", "哥伦比亚"),
    ("kailas", "凯乐石"),
    ("camel", "骆驼"),
    ("pelliot", "伯希和"),
    ("fjallraven", "北极狐"),
    ("salomon", "萨洛蒙"),
    ("decathlon", "迪卡侬"),
]

# 别名 → slug 的匹配表，按别名长度降序（"始祖鸟"优先于"鸟"类短词）
_ALIAS_TABLE: list[tuple[str, str]] = sorted(
    (
        (alias.lower(), slug)
        for slug, (_name, _name_cn, aliases) in BRAND_ALIASES.items()
        for alias in aliases
        if aliases
    ),
    key=lambda x: len(x[0]),
    reverse=True,
)


def detect_brand(text: str) -> str | None:
    """从线报标题识别品牌 slug；未命中返回 None（线报照常展示，不猜）。"""
    lower = text.lower()
    for alias, slug in _ALIAS_TABLE:
        if alias in lower:
            return _BRAND_REDIRECTS.get(slug, slug)
    return None


def brand_display(slug: str) -> tuple[str, str]:
    """slug → (英文名, 中文名)。"""
    slug = _BRAND_REDIRECTS.get(slug, slug)
    name, name_cn, _ = BRAND_ALIASES[slug]
    return name, name_cn


_STYLE_JUNK_RE = re.compile(r"\s+")


def clean_style_name(title: str, brand_names: tuple[str, ...]) -> str:
    """从线报标题剥离品牌词后作为款式名兜底（无官方名时的占位）。"""
    name = title
    for word in brand_names:
        name = name.replace(word, "")
    return _STYLE_JUNK_RE.sub(" ", name).strip()[:80]
