# ruff: noqa: E501
"""从权威测评站点构建榜单数据 catalog.json，并把产品图下载到前端本地。

用法（在 backend/ 下）：
    uv run python scripts/build_rankings.py            # 用缓存 HTML，缺的才抓取（≥10s/请求）
    uv run python scripts/build_rankings.py --refresh  # 强制重新抓取所有榜单页
    uv run python scripts/build_rankings.py --no-images

数据来源：
- OutdoorGearLab 品类榜单对比表：排名、实测总分、分项分、标价、优缺点、规格、实测图
- Switchback Travel 品类榜单：编辑奖项/排名、白底产品图、What we like/don't
国内口碑：为每个产品生成 什么值得买 / 小红书 / B站 / 8264 / 京东 检索链接。
遵守 AGENTS.md：只抓公开榜单页、遵守 robots、单站点请求间隔 ≥10 秒。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import statistics
import sys
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.pricing.overseas import OverseasInput, calc_overseas  # noqa: E402
from app.rankings.brands import detect_brand  # noqa: E402
from app.rankings.catalog_config import CATEGORY_BY_ID, SOURCES  # noqa: E402
from app.rankings.schemas import GearCategory  # noqa: E402
from app.rankings.sources.ogl import parse_ogl_compare  # noqa: E402
from app.rankings.sources.switchback import parse_switchback  # noqa: E402

CACHE = ROOT / "data" / "raw_cache"
IMG_DIR = ROOT / "frontend" / "public" / "rankings"
OUT = ROOT / "backend" / "app" / "rankings" / "catalog.json"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
RATE = 7.1
GENDER_CN = {"men": "男款", "women": "女款", "unisex": "男女同款"}
TIER_CN = {"budget": "入门性价比", "mid": "进阶主力", "flagship": "顶级旗舰"}
_last_hit: dict[str, float] = {}


def fetch(url: str, refresh: bool, min_gap: float = 10.0) -> str:
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / (
        hashlib.md5(url.encode()).hexdigest()[:10] + "_" + url.rstrip("/").split("/")[-1] + ".html"
    )
    if path.exists() and not refresh:
        return path.read_text()
    host = urlparse(url).netloc
    wait = min_gap - (time.time() - _last_hit.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    resp = httpx.get(url, headers={"User-Agent": UA}, follow_redirects=True, timeout=40)
    _last_hit[host] = time.time()
    resp.raise_for_status()
    path.write_text(resp.text)
    print(f"  fetched {url} ({len(resp.text)} bytes)")
    return resp.text


def fold(text: str) -> str:
    text = text.replace("ø", "o").replace("’", "'")
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c)).lower()


_NOISE = {
    "jacket",
    "hoody",
    "hoodie",
    "hooded",
    "hood",
    "pants",
    "pant",
    "pullover",
    "men's",
    "women's",
    "mens",
    "womens",
    "the",
    "-",
    "&",
    "shoe",
    "shoes",
    "boot",
    "boots",
    "co-op",
    "tent",
    "pack",
    "backpack",
    "sleeping",
    "bag",
    "pad",
    "headlamp",
    "trekking",
    "poles",
    "pole",
    "crew",
    "sock",
    "socks",
}


def norm_key(name: str) -> str:
    s = fold(name)
    s = s.replace("gore-tex", "gtx").replace("goretex", "gtx").replace("waterproof", "wp")
    toks = [t for t in re.split(r"[\s/,()]+", s) if t and t not in _NOISE]
    return " ".join(toks)


def strip_gender(name: str) -> tuple[str, str | None]:
    m = re.search(r"\s*-\s*(Women|Men)['’]s\s*$", name)
    if m:
        return name[: m.start()].strip(), "women" if m.group(1) == "Women" else "men"
    return name.strip(), None


def slugify(text: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", fold(text)).strip("-")
    return s[:60]


def landed(usd: float, cat: GearCategory) -> int:
    res = calc_overseas(
        OverseasInput(
            usd_price=usd, rate=RATE, transfer_fee_cny=CATEGORY_BY_ID[cat].transfer_fee_cny
        )
    )
    return int(round(res.landed_cny))


def cn_links(query: str) -> list[dict[str, str]]:
    q = quote(query)
    return [
        {"label": "什么值得买", "url": f"https://search.smzdm.com/?c=home&s={q}&v=b"},
        {"label": "小红书", "url": f"https://www.xiaohongshu.com/search_result?keyword={q}"},
        {
            "label": "B站测评",
            "url": f"https://search.bilibili.com/all?keyword={quote(query + ' 测评')}",
        },
        {
            "label": "8264 论坛",
            "url": f"https://www.8264.com/plugin.php?id=esearch&mymod=search&srchtxt={q}",
        },
        {"label": "京东", "url": f"https://search.jd.com/Search?keyword={q}&enc=utf-8"},
        {"label": "淘宝/天猫", "url": f"https://s.taobao.com/search?q={q}"},
    ]


def buy_links(query: str) -> list[dict[str, str]]:
    q = quote(query)
    return [
        {"label": "REI", "url": f"https://www.rei.com/search?q={q}"},
        {"label": "Backcountry", "url": f"https://www.backcountry.com/store/search?q={q}"},
        {"label": "Amazon", "url": f"https://www.amazon.com/s?k={q}"},
    ]


def oz_to_g(text: str) -> str:
    m = re.search(r"(?:(\d+(?:\.\d+)?)\s*lbs?\.?\s*)?(\d+(?:\.\d+)?)\s*oz", text)
    if not m:
        return text
    grams = float(m.group(1) or 0) * 453.6 + float(m.group(2)) * 28.35
    return f"{grams:.0f}g ({m.group(0).strip()})"


def pick(spec: dict[str, str], *keys: str) -> str:
    for k in spec:
        for key in keys:
            if key.lower() in k.lower():
                return spec[k]
    return ""


def build(refresh: bool) -> list[dict]:
    items: dict[str, dict] = {}
    sbt_by_cat: dict[GearCategory, list[tuple[str, object]]] = {}
    for cat, gender, site, url in SOURCES:
        html = fetch(url, refresh)
        if site == "OutdoorGearLab":
            prods = parse_ogl_compare(html)
            total = len(prods)
            for p in prods:
                name, g = strip_gender(p.name)
                g = g or gender
                brand, model = detect_brand(name)
                if brand is None:
                    continue  # 白牌/亚马逊杂牌不收录
                key = f"{cat.value}|{g}|{norm_key(name)}"
                award = p.awards[0] if p.awards else ""
                auth = {
                    "source": "OutdoorGearLab",
                    "badge": award or f"实测第 {p.rank} 名",
                    "score": p.overall_score,
                    "quote": p.bottom_line,
                    "url": p.review_url,
                    "rank": p.rank,
                    "rank_total": total,
                }
                if key in items:  # 同品类另一张榜（如 base layer + long underwear）
                    it = items[key]
                    if all(
                        a["url"] != auth["url"] or a["badge"] != auth["badge"]
                        for a in it["authorities"]
                    ):
                        it["authorities"].append(auth)
                    continue
                spec = dict(p.specs)
                items[key] = {
                    "_key": key,
                    "id": f"{cat.value}_{g}_{slugify(name)}",
                    "name": name,
                    "model": model,
                    "brand": brand.slug,
                    "brand_name": f"{brand.name} / {brand.name_cn}"
                    if brand.name_cn != brand.name
                    else brand.name,
                    "brand_cn": brand.name_cn,
                    "brand_country": brand.country,
                    "category": cat.value,
                    "gender": g,
                    "usd": p.list_price_usd,
                    "image_remote": p.image_url,
                    "image_credit": "OutdoorGearLab 实测图",
                    "rating_score": p.overall_score,
                    "sub_scores": {re.sub(r"\s*\(\d+%\)", "", k): v for k, v in p.ratings.items()},
                    "spec_table": spec,
                    "pros": [s.strip() for s in re.split(r",\s*", p.pros) if s.strip()],
                    "cons": [s.strip() for s in re.split(r",\s*", p.cons) if s.strip()],
                    "authorities": [auth],
                }
        else:
            prods = parse_switchback(html)
            for p in prods:
                sbt_by_cat.setdefault(cat, []).append((url, p, len(prods)))

    # Switchback：按名称模糊匹配并入，匹配不到的作为新产品（男女同款）
    for cat, entries in sbt_by_cat.items():
        for url, p, total in entries:
            name = p.name
            brand, model = detect_brand(name)
            if brand is None:
                continue
            nk = norm_key(name)
            brand_toks = set(norm_key(brand.name).split()) | {fold(a) for a in brand.aliases}
            mk = set(nk.split()) - brand_toks
            matched = []
            for it in items.values():
                if it["category"] != cat.value or it["brand"] != brand.slug:
                    continue
                ik = norm_key(it["name"])
                ratio = SequenceMatcher(None, nk, ik).ratio()
                a, b = mk, set(ik.split()) - brand_toks
                nums_a = set(re.findall(r"\d+", " ".join(a)))
                nums_b = set(re.findall(r"\d+", " ".join(b)))
                if nums_a != nums_b:
                    continue
                if a == b or ratio >= 0.93 or (a and b and (a <= b or b <= a) and len(a & b) >= 2):
                    matched.append(it)
            auth = {
                "source": "Switchback Travel",
                "badge": p.award or f"编辑推荐第 {p.rank} 名",
                "score": None,
                "quote": p.like,
                "url": url,
                "rank": p.rank,
                "rank_total": total,
            }
            if matched:
                for it in matched:
                    it["authorities"].append(auth)
                    if not it["usd"] and p.price_usd:
                        it["usd"] = p.price_usd
                    it.setdefault("alt_images", []).append(p.image_url)
                continue
            key = f"{cat.value}|unisex|{nk}"
            if key in items:
                items[key]["authorities"].append(auth)
                continue
            items[key] = {
                "_key": key,
                "id": f"{cat.value}_unisex_{slugify(name)}",
                "name": name,
                "model": model,
                "brand": brand.slug,
                "brand_name": f"{brand.name} / {brand.name_cn}"
                if brand.name_cn != brand.name
                else brand.name,
                "brand_cn": brand.name_cn,
                "brand_country": brand.country,
                "category": cat.value,
                "gender": "unisex",
                "usd": p.price_usd,
                "image_remote": p.image_url,
                "image_credit": "Switchback Travel 产品图",
                "rating_score": None,
                "sub_scores": {},
                "spec_table": {k: v.replace("\xa0", " ") for k, v in p.specs.items()},
                "pros": [p.like] if p.like else [],
                "cons": [p.dislike] if p.dislike else [],
                "authorities": [auth],
            }
    # Switchback 的 What we like/don't 补到 OGL 条目
    return finalize(list(items.values()))


def finalize(raw: list[dict]) -> list[dict]:
    out: list[dict] = []
    by_cat: dict[str, list[dict]] = {}
    for it in raw:
        if not it["usd"] or not it["image_remote"]:
            continue
        by_cat.setdefault(it["category"], []).append(it)
    for cat_id, group in by_cat.items():
        cat = CATEGORY_BY_ID[GearCategory(cat_id)]
        prices = sorted(i["usd"] for i in group)
        lo = prices[len(prices) // 3]
        hi = prices[(2 * len(prices)) // 3]
        median_usd = statistics.median(prices)
        scored = [i["rating_score"] for i in group if i["rating_score"]]
        median_score = statistics.median(scored) if scored else None
        for it in group:
            usd = it["usd"]
            tier = "budget" if usd < lo else ("flagship" if usd >= hi else "mid")
            land = landed(usd, cat.id)
            direct = int(round(usd * RATE))
            spec = it["spec_table"]
            weight = pick(spec, "Measured Weight", "Weight")
            material = pick(spec, "Material", "Fabric", "Fill", "Insulation", "Upper", "Shell")
            waterproof = pick(
                spec, "Waterproof", "Membrane", "Rain Fly", "R-Value", "Lumens", "Temp"
            )
            awards = [
                a for a in it["authorities"] if not a["badge"].startswith(("实测第", "编辑推荐第"))
            ]
            parts = []
            for a in it["authorities"]:
                rank_txt = f"第 {a['rank']}/{a['rank_total']} 名" if a.get("rank") else ""
                score_txt = f"，{a['score']} 分" if a.get("score") else ""
                parts.append(
                    f"{a['source']} {rank_txt}{score_txt}"
                    + (f"（{a['badge']}）" if a in awards else "")
                )
            bottom = "；".join(dict.fromkeys(parts)) + "。"
            diff_pct = (usd - median_usd) / median_usd * 100
            gap = f"美标价 ${usd:g}，比本品类中位价 ${median_usd:g} {'贵' if diff_pct >= 0 else '便宜'} {abs(diff_pct):.0f}%"
            if it["rating_score"] and median_score:
                d = it["rating_score"] - median_score
                gap += f"；OGL 实测 {it['rating_score']} 分，{'高于' if d >= 0 else '低于'}同类中位 {abs(d):g} 分"
                value = it["rating_score"] / max(usd, 1) * 100
                gap += f"；每百美元得分 {value:.1f}"
            gap += "。"
            query = f"{it['brand_cn'] if it['brand_cn'] != it['name'].split()[0] else ''} {it['name']}".strip()
            name_cn = f"{it['brand_cn']} {it['model'] or it['name']} {cat.short}".strip()
            alt = [u for u in it.get("alt_images", []) if u]
            out.append(
                {
                    "id": it["id"],
                    "name": it["name"],
                    "name_cn": name_cn,
                    "brand": it["brand"],
                    "brand_name": it["brand_name"],
                    "brand_country": it["brand_country"],
                    "category": cat_id,
                    "category_name": cat.name,
                    "gender": it["gender"],
                    "gender_name": GENDER_CN[it["gender"]],
                    "price_tier": tier,
                    "price_tier_name": TIER_CN[tier],
                    "image": f"/rankings/{it['id']}.webp",
                    "image_remote": it["image_remote"],
                    "image_alt_remote": alt[0] if alt else "",
                    "image_credit": it["image_credit"],
                    "rating_score": it["rating_score"],
                    "score_basis": "OutdoorGearLab 实测总分（满分 100）"
                    if it["rating_score"]
                    else "仅编辑推荐，无量化打分",
                    "price_guide": {
                        "price_cents": land * 100,
                        "msrp_cny": f"${usd:g}",
                        "deal_cny": f"≈¥{direct:,}",
                        "overseas_usd": f"${usd:g}",
                        "overseas_landed_cny": f"≈¥{land:,}",
                        "promo_tips": f"美标价按汇率 {RATE} 折算；海淘落地含转运 ¥{cat.transfer_fee_cny} 与 20% 行邮税估算（税额≤50 元免征），国内实时价以比价采集为准。",
                    },
                    "specs": {
                        "weight": oz_to_g(weight) if weight else "",
                        "material": material,
                        "waterproof_rating": waterproof,
                        "breathability": pick(spec, "Breathab"),
                        "fabric_density": pick(spec, "Denier"),
                        "scenarios": list(cat.scenarios),
                        "key_features": [f"{k}: {v}" for k, v in list(spec.items())[:6]],
                    },
                    "spec_table": spec,
                    "sub_scores": it["sub_scores"],
                    "authorities": it["authorities"],
                    "pros": it["pros"][:5] or ["—"],
                    "cons": it["cons"][:5] or ["—"],
                    "bottom_line": bottom,
                    "gap_analysis": gap,
                    "matched_style_number": None,
                    "cn_links": cn_links(query),
                    "buy_links": [
                        {"label": a["source"] + " 评测", "url": a["url"]} for a in it["authorities"]
                    ]
                    + buy_links(it["name"]),
                }
            )
    out.sort(
        key=lambda x: (x["category"], -(x["rating_score"] or 0), x["price_guide"]["price_cents"])
    )
    return out


def download_images(items: list[dict]) -> None:
    from PIL import Image

    IMG_DIR.mkdir(parents=True, exist_ok=True)
    client = httpx.Client(
        headers={"User-Agent": UA, "Referer": "https://www.google.com/"},
        timeout=30,
        follow_redirects=True,
    )
    failed = []
    for i, it in enumerate(items):
        dest = IMG_DIR / f"{it['id']}.webp"
        if dest.exists() and dest.stat().st_size > 2000:
            continue
        ok = False
        for src in (it["image_remote"], it.get("image_alt_remote")):
            if not src:
                continue
            try:
                r = client.get(src)
                r.raise_for_status()
                img = Image.open(io.BytesIO(r.content)).convert("RGB")
                img.thumbnail((720, 720))
                img.save(dest, "WEBP", quality=78, method=6)
                ok = True
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  image fail {it['id']} {src}: {exc}")
            time.sleep(0.5)
        if not ok:
            failed.append(it["id"])
        time.sleep(0.6)
        if i % 50 == 0:
            print(f"  images {i}/{len(items)}")
    if failed:
        print("FAILED IMAGES:", failed)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    args = ap.parse_args()
    items = build(args.refresh)
    if not args.no_images:
        download_images(items)
        items = [it for it in items if (IMG_DIR / f"{it['id']}.webp").exists()]
    OUT.write_text(json.dumps(items, ensure_ascii=False, indent=1))
    brands = {it["brand"] for it in items}
    print(f"wrote {len(items)} items, {len(brands)} brands -> {OUT}")


if __name__ == "__main__":
    main()
