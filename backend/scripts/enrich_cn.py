# ruff: noqa: E501
"""国内口碑增强：什么值得买（好价 + 原创测评）、中文翻译、国货精选。

用法（backend/ 下）：
    uv run python scripts/enrich_cn.py                 # 全部（有缓存的直接复用）
    uv run python scripts/enrich_cn.py --only smzdm    # smzdm / translate / picks
    uv run python scripts/enrich_cn.py --refresh       # 忽略缓存重新请求

产物：
- app/rankings/cn_reviews.json   每个产品的国内好价汇总 + 好价/原创列表
- app/rankings/cn_catalog.json   国货精选条目（与 catalog.json 同结构）
- app/rankings/translations_zh.json  英文优缺点/结论/奖项 → 中文
- frontend/public/rankings/cn_*.webp 国货精选产品图

什么值得买 api.smzdm.com 为免登录公开接口（无 robots 限制）；按 AGENTS.md 串行、≥10 秒/请求，
有缓存（data/raw_cache/cn）就不再请求，遇到错误码自动退避，不绕过任何登录/验证码。
B站（api.bilibili.com robots.txt 为 Disallow: /）与小红书（需登录+签名）不在此脚本内直接请求，
请用 MediaCrawler 自行采集后用 scripts/import_mediacrawler.py 导入。
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import sys
import threading
import time
from pathlib import Path
from urllib.parse import quote

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from build_rankings import cn_links  # noqa: E402

from app.rankings.brands import brand_by_slug, detect_brand  # noqa: E402
from app.rankings.catalog_config import CATEGORY_BY_ID  # noqa: E402
from app.rankings.cn_picks import CN_PICKS  # noqa: E402
from app.rankings.schemas import GearCategory  # noqa: E402
from app.rankings.sources.cn import (  # noqa: E402
    model_tokens,
    parse_smzdm_list,
    split_smzdm_mixed,
    summarize_prices,
)

RANK_DIR = ROOT / "backend" / "app" / "rankings"
CACHE = ROOT / "data" / "raw_cache" / "cn"
IMG_DIR = ROOT / "frontend" / "public" / "rankings"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"
TIER_CN = {"budget": "入门性价比", "mid": "进阶主力", "flagship": "顶级旗舰"}


class Fetcher:
    """带缓存、同站最小间隔、风控退避的 JSON 抓取器。"""

    def __init__(self, gap: float, refresh: bool, headers: dict[str, str] | None = None) -> None:
        self.gap = gap
        self.refresh = refresh
        self.last = 0.0
        self.client = httpx.Client(
            headers={"User-Agent": UA, **(headers or {})}, timeout=25, follow_redirects=True
        )
        CACHE.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _path(url: str, params: dict) -> Path:
        key = hashlib.md5(
            (url + json.dumps(params, sort_keys=True, ensure_ascii=False)).encode()
        ).hexdigest()
        return CACHE / f"{key}.json"

    def cached(self, url: str, params: dict) -> bool:
        return not self.refresh and self._path(url, params).exists()

    def get_json(self, url: str, params: dict, ok=lambda d: True) -> dict | None:
        path = self._path(url, params)
        if path.exists() and not self.refresh:
            return json.loads(path.read_text())
        for attempt in range(4):
            wait = self.gap - (time.time() - self.last)
            if wait > 0:
                time.sleep(wait)
            try:
                r = self.client.get(url, params=params)
                self.last = time.time()
                data = r.json()
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {url} {params.get('keyword')}: {exc}")
                time.sleep(10 * (attempt + 1))
                continue
            if ok(data):
                path.write_text(json.dumps(data, ensure_ascii=False))
                return data
            print(f"  ! risk/err {url} {data.get('code', data.get('error_code'))}，退避")
            time.sleep(60 * (attempt + 1))
        return None


def brand_words(slug: str) -> list[str]:
    b = brand_by_slug(slug)
    if not b:
        return []
    return [b.name_cn, b.name, *b.aliases]


def keyword(slug: str, model: str) -> str:
    b = brand_by_slug(slug)
    prefix = b.name_cn if b else ""
    if b and prefix.isascii() and len(prefix) <= 3:  # "OR" 之类缩写会让接口报错，改用英文全名
        prefix = b.name
    return f"{prefix} {model}".strip()


SMZDM_API = "https://api.smzdm.com/v1/list"


def smzdm(f: Fetcher, kw: str) -> tuple[dict, dict]:
    """返回 (好价 payload, 原创 payload)。优先用旧版分 type 缓存，否则一次混合检索后按频道拆分。"""
    typed = [
        {"keyword": kw, "type": t, "offset": 0, "limit": 20} for t in ("good_price", "yuanchuang")
    ]
    if all(f.cached(SMZDM_API, p) for p in typed):
        deals, posts = (f.get_json(SMZDM_API, p) or {} for p in typed)
        return deals, posts
    mixed = f.get_json(
        SMZDM_API,
        {"keyword": kw, "offset": 0, "limit": 40},
        ok=lambda d: str(d.get("error_code")) == "0",
    )
    return split_smzdm_mixed(mixed or {})


# ---------------------------------------------------------------- 翻译
GLOSSARY = [
    ("坑拉链", "腋下拉链"),
    ("坑式拉链", "腋下拉链"),
    ("坑邮编", "腋下拉链"),
    ("腋窝拉链", "腋下拉链"),
    ("头巾", "兜帽"),
    ("引擎盖", "兜帽"),
    ("罩子", "兜帽"),
    ("硬壳夹克", "硬壳冲锋衣"),
    ("更好的", "更好"),
    ("价格昂贵", "价格贵"),
    ("步道", "山径"),
    ("小径", "山径"),
    ("耐候性", "防护性"),
    ("物有所值", "性价比高"),
    ("最佳性价比", "最佳性价比"),
    ("鞋楦", "鞋楦"),
    ("脚趾盒", "鞋头空间"),
    ("脚趾箱", "鞋头空间"),
    ("趾箱", "鞋头空间"),
    ("加油", "保暖"),
    ("羊毛脂", "美利奴羊毛"),
]


def _fix(zh: str) -> str:
    for a, b in GLOSSARY:
        zh = zh.replace(a, b)
    return zh.strip()


def translate_all(texts: list[str]) -> dict[str, str]:
    path = RANK_DIR / "translations_zh.json"
    done: dict[str, str] = json.loads(path.read_text()) if path.exists() else {}
    todo = [t for t in dict.fromkeys(texts) if t and t not in done and re.search(r"[A-Za-z]", t)]
    print(f"translate: {len(todo)} new / {len(done)} cached")
    client = httpx.Client(timeout=30, headers={"User-Agent": UA})
    batch: list[str] = []
    api = "https://translate.googleapis.com/translate_a/single"
    params = {"client": "gtx", "sl": "en", "tl": "zh-CN", "dt": "t"}

    def call(q: str) -> list[str] | None:
        """单次请求；429/非 JSON 视为限流，等 10 分钟再试（最多 6 次），不换 UA/IP 绕过。"""
        for attempt in range(6):
            time.sleep(10)  # 同站 ≥10 秒/请求
            try:
                r = client.post(api, params=params, data={"q": q})
                if r.status_code == 200:
                    return "".join(seg[0] for seg in r.json()[0] if seg and seg[0]).split("\n")
                print(
                    f"  ! translate HTTP {r.status_code}，限流退避 10 分钟（{attempt + 1}/6）",
                    flush=True,
                )
            except Exception as exc:  # noqa: BLE001
                print("  ! translate", exc, flush=True)
            time.sleep(600)
        return None

    def flush() -> None:
        if not batch:
            return
        out = call("\n".join(s.replace("\n", " ") for s in batch))
        if out is None:
            raise SystemExit("翻译接口持续限流，已保存进度，稍后重跑 --only translate")
        if len(out) == len(batch):
            for en, zh in zip(batch, out, strict=True):
                done[en] = _fix(zh)
        else:  # 行数对不上就逐条翻
            for en in batch:
                one = call(en)
                if one:
                    done[en] = _fix("".join(one))
        batch.clear()
        path.write_text(json.dumps(done, ensure_ascii=False, indent=0, sort_keys=True))
        print(f"  translate {len(done)}", flush=True)

    for t in todo:
        batch.append(t)
        if len(batch) >= 60 or sum(len(x) for x in batch) > 4500:
            flush()
    flush()
    path.write_text(json.dumps(done, ensure_ascii=False, indent=0, sort_keys=True))
    return done


# ---------------------------------------------------------------- 主流程
def item_query(it: dict) -> tuple[str, list[str], list[str]]:
    _, model = detect_brand(it["name"])
    return (
        keyword(it["brand"], model or it["name"]),
        model_tokens(model or it["name"]),
        brand_words(it["brand"]),
    )


def run_smzdm(items: list[dict], f: Fetcher, out: dict) -> None:
    seen: dict[str, tuple] = {}
    for i, it in enumerate(items):
        kw, toks, bw = item_query(it)
        k = f"{kw}|{it['category']}"
        if k not in seen:
            deals_raw, posts_raw = smzdm(f, kw)
            deals = parse_smzdm_list(deals_raw, toks, bw, "好价", it["category"])
            posts = parse_smzdm_list(posts_raw, toks, bw, "测评文章", it["category"])
            seen[k] = (deals, posts)
        deals, posts = seen[k]
        rec = out.setdefault(it["id"], {})
        rec["cn_price"] = summarize_prices(deals)
        rec["smzdm_deals"] = [
            d.to_dict() for d in sorted(deals, key=lambda d: d.date, reverse=True)[:5]
        ]
        rec["smzdm_posts"] = [p.to_dict() for p in posts[:5]]
        rec["smzdm_query"] = kw
        if i % 50 == 0:
            print(f"  smzdm {i}/{len(items)}", flush=True)


def save_image(url: str, dest: Path) -> bool:
    from PIL import Image

    candidates = [re.sub(r"_(d|a|e|fo)\d+\.(jpg|png|jpeg)$", "", url), url]
    for u in candidates:
        try:
            r = httpx.get(
                u,
                headers={"User-Agent": UA, "Referer": "https://www.smzdm.com/"},
                timeout=25,
                follow_redirects=True,
            )
            r.raise_for_status()
            img = Image.open(io.BytesIO(r.content)).convert("RGB")
            if img.width < 150:
                continue
            img.thumbnail((720, 720))
            img.save(dest, "WEBP", quality=80, method=6)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


def run_picks(f_s: Fetcher) -> list[dict]:
    items: list[dict] = []
    for slug, model, cat_id, gender in CN_PICKS:
        b = brand_by_slug(slug)
        if not b:
            print("  ! unknown brand", slug)
            continue
        cat = CATEGORY_BY_ID[GearCategory(cat_id)]
        kw = keyword(slug, model)
        toks = model_tokens(model)
        bw = brand_words(slug)
        deals_raw, posts_raw = smzdm(f_s, kw)
        deals = parse_smzdm_list(deals_raw, toks, bw, "好价", cat_id)
        price = summarize_prices(deals)
        if not price or price["count"] < 2:
            print(f"  - drop {kw}: 好价不足")
            continue
        posts = parse_smzdm_list(posts_raw, toks, bw, "测评文章", cat_id)
        # 去掉离群价（如配件/童款），以中位数 ±60% 为界
        med = price["median_cny"]
        deals = [d for d in deals if d.price_cny and 0.4 * med <= d.price_cny <= 1.6 * med] or deals
        price = summarize_prices(deals) or price
        top = max(deals, key=lambda d: (d.metric_value, d.date))
        iid = f"cn_{cat_id}_{slug}_{re.sub(r'[^a-z0-9]+', '-', model.lower()).strip('-') or hashlib.md5(model.encode()).hexdigest()[:6]}"
        dest = IMG_DIR / f"{iid}.webp"
        pics = [d.cover for d in sorted(deals, key=lambda d: -d.metric_value) if d.cover]
        if not (dest.exists() or any(save_image(p, dest) for p in pics[:4])):
            print(f"  - drop {kw}: 无可用图片")
            continue
        title = re.sub(r"\s+", " ", top.title).strip()
        median = price["median_cny"]
        authorities = [
            {
                "source": "什么值得买",
                "badge": f"好价 {price['count']} 条",
                "score": None,
                "quote": title,
                "url": f"https://search.smzdm.com/?c=faxian&s={quote(kw)}&v=b",
                "rank": None,
                "rank_total": None,
            }
        ]
        if posts:
            authorities.append(
                {
                    "source": "什么值得买",
                    "badge": f"原创测评 {len(posts)} 篇",
                    "score": None,
                    "quote": posts[0].title,
                    "url": posts[0].url,
                    "rank": None,
                    "rank_total": None,
                }
            )
        items.append(
            {
                "id": iid,
                "name": f"{b.name} {model}",
                "name_cn": f"{b.name_cn} {model}" + ("" if cat.short in model else f" {cat.short}"),
                "brand": b.slug,
                "brand_name": f"{b.name} / {b.name_cn}" if b.name_cn != b.name else b.name,
                "brand_country": b.country,
                "category": cat_id,
                "category_name": cat.name,
                "gender": gender,
                "gender_name": {"men": "男款", "women": "女款"}.get(gender, "男女同款"),
                "price_tier": "budget",
                "price_tier_name": TIER_CN["budget"],
                "image": f"/rankings/{iid}.webp",
                "image_remote": pics[0] if pics else "",
                "image_credit": "什么值得买 好价图",
                "rating_score": None,
                "score_basis": "国内口碑（什么值得买好价 / 原创测评、B站视频），无实验室打分",
                "price_guide": {
                    "price_cents": int(median * 100),
                    "msrp_cny": f"¥{price['min_cny']:,.0f} 起",
                    "deal_cny": f"¥{price['min_cny']:,.0f}~¥{median:,.0f}",
                    "overseas_usd": "",
                    "overseas_landed_cny": "",
                    "promo_tips": f"什么值得买近期 {price['count']} 条好价（{', '.join(price['malls'])}），区间为最低价~中位价；检索词「{kw}」下可能含同系列不同型号。",
                },
                "specs": {
                    "weight": "",
                    "material": "",
                    "waterproof_rating": "",
                    "breathability": "",
                    "fabric_density": "",
                    "scenarios": list(cat.scenarios),
                    "key_features": [],
                },
                "spec_table": {
                    "代表款（好价标题）": title,
                    "常见商城": "、".join(price["malls"]),
                    "最近好价": price["latest_date"],
                },
                "sub_scores": {},
                "authorities": authorities,
                "pros": [
                    f"国内好价充足：近期 {price['count']} 条，低至 ¥{price['min_cny']:,.0f}",
                    *([f"常见渠道：{'、'.join(price['malls'])}"] if price["malls"] else []),
                    *([f"什么值得买原创测评 {len(posts)} 篇，可查看真实使用体验"] if posts else []),
                ],
                "cons": [
                    "无第三方实验室对比测试，暂无实测分",
                    "检索词下可能混入同系列不同型号，价格以下单页为准",
                ],
                "bottom_line": f"国内口碑款：什么值得买近期好价 {price['count']} 条，低至 ¥{price['min_cny']:,.0f}"
                + (f"；原创测评 {len(posts)} 篇" if posts else "")
                + "。",
                "gap_analysis": f"国内好价区间 ¥{price['min_cny']:,.0f}~¥{median:,.0f}，可与同品类海外款的海淘落地估算直接对比。",
                "matched_style_number": None,
                "cn_links": cn_links(f"{b.name_cn} {model}"),
                "buy_links": [],
                "_cn": {
                    "cn_price": price,
                    "smzdm_deals": [
                        d.to_dict() for d in sorted(deals, key=lambda d: d.date, reverse=True)[:5]
                    ],
                    "smzdm_posts": [p.to_dict() for p in posts[:5]],
                    "smzdm_query": kw,
                },
            }
        )
        print(f"  + {iid}: {price['count']} 好价, {len(posts)} 原创")
    return items


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--only", choices=["smzdm", "translate", "picks"])
    ap.add_argument(
        "--no-translate", action="store_true", help="跳过翻译（可单独 --only translate）"
    )
    args = ap.parse_args()
    items = json.loads((RANK_DIR / "catalog.json").read_text())
    out_path = RANK_DIR / "cn_reviews.json"
    out: dict = json.loads(out_path.read_text()) if out_path.exists() else {}
    f_s = Fetcher(10.0, args.refresh, {"Referer": "https://www.smzdm.com/"})
    reviews: dict = {}

    def smzdm_job() -> None:
        # 先跑国货精选（数量少、最想要），再给海外款补国内好价/原创
        if not args.only or args.only == "picks":
            picks = run_picks(f_s)
            (RANK_DIR / "cn_catalog.json").write_text(
                json.dumps(picks, ensure_ascii=False, indent=1)
            )
            print(f"wrote cn_catalog.json ({len(picks)} items)", flush=True)
        if not args.only or args.only == "smzdm":
            run_smzdm(items, f_s, reviews)

    job = threading.Thread(target=smzdm_job)
    job.start()
    if (not args.only and not args.no_translate) or args.only == "translate":
        texts: list[str] = []
        for it in items:
            texts += it["pros"] + it["cons"]
            for a in it["authorities"]:
                texts += [a["quote"], a["badge"]]
            texts += list(it.get("sub_scores", {}).keys())
        translate_all(texts)
    job.join()
    if reviews:
        for iid, rec in reviews.items():
            out.setdefault(iid, {}).update(rec)
        out_path.write_text(json.dumps(out, ensure_ascii=False, indent=0))
        print(f"wrote {out_path} ({len(out)} items)")


if __name__ == "__main__":
    main()
