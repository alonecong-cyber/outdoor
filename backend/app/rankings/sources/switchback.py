"""Switchback Travel 品类榜单页解析。

页面结构：<h2>奖项/推荐理由</h2> 紧跟 <h3>Men's X & Women's Y ($价格)</h3>，
其后若干段落含白底产品图、规格（Category/Weight/...）和 What we like / What we don't。
h3 出现的先后顺序即编辑排名。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.switchbacktravel.com"
_OTHER_FAV = (
    r"^Our Other Favorite .*?(Jackets|Pants|Shoes|Boots|Tents|Packs|Backpacks|Daypacks"
    r"|Bags|Pads|Poles|Headlamps|Socks|Layers|Baselayers)\s+"
)
_STOP_H2 = re.compile(
    r"comparison table|buying advice|testing process|tested and dismissed|difference between|"
    r"how we test|why trust|what is|faq",
    re.I,
)


@dataclass
class SbtProduct:
    rank: int
    award: str
    name: str  # 去掉 Men's/Women's 与价格后的主名称（取第一个）
    raw_title: str
    price_usd: float | None
    image_url: str = ""
    specs: dict[str, str] = field(default_factory=dict)
    like: str = ""
    dislike: str = ""


def _clean_name(title: str) -> str:
    title = re.sub(r"\(\$[^)]*\)", "", title)
    first = re.split(r"\s+&\s+|\s+and\s+(?=Women)", title)[0]
    first = re.sub(r"^(Men[’']s|Women[’']s|Unisex)\s+", "", first.strip())
    return first.replace("’", "'").strip(" ,")


def _abs(src: str) -> str:
    if not src:
        return ""
    url = urljoin(BASE_URL, src)
    return quote(url, safe=":/%?=&")


def parse_switchback(html: str) -> list[SbtProduct]:
    soup = BeautifulSoup(html, "lxml")
    out: list[SbtProduct] = []
    award = ""
    for h in soup.find_all(["h2", "h3"]):
        text = h.get_text(" ", strip=True).replace("\u200b", "").strip()
        m = re.search(r"\(\$([\d,]+(?:\.\d+)?)", text)
        if not m:
            if h.name == "h2":
                if _STOP_H2.search(text) and out:
                    break
                award = text
            continue
        title_award = award
        if ":" in text.split("($")[0]:
            head, text = text.split(":", 1)
            title_award = re.sub(
                _OTHER_FAV,
                "",
                head,
            ).strip()
            text = text.strip()
        prod = SbtProduct(
            rank=len(out) + 1,
            award=title_award,
            name=_clean_name(text),
            raw_title=text,
            price_usd=float(m.group(1).replace(",", "")),
        )
        node: Tag | None = h
        for _ in range(8):
            node = node.find_next_sibling() if node else None
            if node is None or node.name in ("h2", "h3"):
                break
            img = node if node.name == "img" else node.find("img")
            if img is not None and not prod.image_url:
                prod.image_url = _abs(str(img.get("src") or img.get("data-src") or ""))
            strongs = node.find_all("strong") if isinstance(node, Tag) else []
            for st in strongs:
                key = st.get_text(" ", strip=True).rstrip(":").strip()
                val_parts: list[str] = []
                for sib in st.next_siblings:
                    if getattr(sib, "name", None) in ("strong", "br"):
                        if getattr(sib, "name", None) == "strong":
                            break
                        continue
                    val_parts.append(
                        sib.get_text(" ", strip=True) if isinstance(sib, Tag) else str(sib)
                    )
                val = " ".join(v.strip() for v in val_parts if v.strip()).strip(" :\xa0")
                if not key or not val or len(key) > 40:
                    continue
                low = key.lower()
                if low.startswith("what we like"):
                    prod.like = val
                elif low.startswith("what we don"):
                    prod.dislike = val
                else:
                    prod.specs[key] = val
        out.append(prod)
    return out
