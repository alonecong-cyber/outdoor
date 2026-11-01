"""OutdoorGearLab（GearLab）品类榜单页解析。

榜单页底部的 Product Comparison Table 是一张"列=产品、行=属性"的大表，包含：
排名、产品名、评测链接、实测图、奖项、美元标价、总分、Bottom Line、Pros/Cons、
分项评分（带权重）以及规格参数。这里把它转成每个产品一条 dict。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, Tag

BASE_URL = "https://www.outdoorgearlab.com"


@dataclass
class OglProduct:
    rank: int
    gear_id: str
    name: str
    review_url: str
    image_url: str
    awards: list[str] = field(default_factory=list)
    list_price_usd: float | None = None
    overall_score: int | None = None
    bottom_line: str = ""
    pros: str = ""
    cons: str = ""
    ratings: dict[str, float] = field(default_factory=dict)  # "Weather Protection (30%)" -> 9.3
    specs: dict[str, str] = field(default_factory=dict)


def _text(node: Tag | None) -> str:
    return node.get_text(" ", strip=True) if node else ""


def _hd_image(url: str) -> str:
    """OGL 图片尺寸后缀 _SM/_M/_L/_XL/_XXL，统一取 _L（600px）作为卡片图。"""
    return re.sub(r"_(SM|M|L|XL|XXL)\.jpg$", "_L.jpg", url)


def _compare_table(soup: BeautifulSoup) -> Tag | None:
    for table in soup.find_all("table"):
        if table.find("input", attrs={"name": "gearid_array[]"}):
            return table
    return None


def parse_title(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    h1 = soup.find("h1")
    return _text(h1)


def parse_ogl_compare(html: str) -> list[OglProduct]:
    soup = BeautifulSoup(html, "lxml")
    table = _compare_table(soup)
    if table is None:
        return []
    rows = table.find_all("tr", recursive=False) or table.find_all("tr")
    header = rows[0]
    products: list[OglProduct] = []
    for th in header.find_all("th"):
        box = th.find("input", attrs={"name": "gearid_array[]"})
        if box is None:
            continue
        rank_txt = _text(th.select_one(".compare_rank_left"))
        img = th.find("img")
        link = th.select_one(".compare_product_name a")
        img_url = (img.get("data-src") or img.get("src") or "") if img else ""
        products.append(
            OglProduct(
                rank=int(re.sub(r"\D", "", rank_txt) or 0),
                gear_id=str(box.get("value")),
                name=_text(link),
                review_url=BASE_URL + str(link.get("href")) if link else "",
                image_url=_hd_image(str(img_url)) if str(img_url).startswith("http") else "",
            )
        )

    section = ""
    for row in rows[1:]:
        th = row.find("th")
        label = _text(th).replace("\xa0", " ").strip()
        tds = row.find_all("td")
        if label.startswith("Rating Categories"):
            section = "ratings"
            continue
        if label == "Specifications":
            section = "specs"
            continue
        if len(tds) != len(products):
            continue
        for prod, td in zip(products, tds, strict=True):
            value = _text(td)
            if label == "Awards":
                prod.awards = [a for a in (value,) if a]
            elif label == "Price":
                m = re.search(r"\$([\d,]+(?:\.\d+)?)", value)
                prod.list_price_usd = float(m.group(1).replace(",", "")) if m else None
            elif label.startswith("Overall Score"):
                prod.overall_score = int(value) if value.isdigit() else None
            elif label == "Bottom Line":
                prod.bottom_line = value
            elif label == "Pros":
                prod.pros = value
            elif label == "Cons":
                prod.cons = value
            elif label.startswith("Star Rating"):
                continue
            elif section == "ratings":
                try:
                    prod.ratings[label] = float(value)
                except ValueError:
                    pass
            elif section == "specs" and value:
                prod.specs[label] = value
    return products
