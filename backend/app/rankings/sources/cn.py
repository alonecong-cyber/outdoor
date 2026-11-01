"""国内口碑数据：什么值得买公开接口返回值解析，以及 MediaCrawler（B站 / 小红书）导出文件导入。

- 什么值得买 `api.smzdm.com/v1/list`：type=good_price（好价爆料：价格/商城/值不值）、
  type=yuanchuang（原创测评文章），无需登录。
  不带 type 时返回混合结果（split_smzdm_mixed 按频道拆分），一次请求拿到两类。
- B站：api.bilibili.com 的 robots.txt 为 Disallow: /，不直接请求。
- 小红书 / 抖音：需要登录态与请求签名，本项目不做逆向。
- B站 / 小红书均推荐用开源工具
  MediaCrawler（https://github.com/NanmiCoder/MediaCrawler）在自己电脑上扫码登录采集，
  导出 JSON 后用 scripts/import_mediacrawler.py 导入（parse_mediacrawler_xhs / _bili）。

这里只做"JSON → 结构化 + 与产品型号匹配"，不发网络请求，便于用快照测试。
"""

from __future__ import annotations

import html
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

# 型号里不具区分度的词：匹配标题时忽略
_GENERIC = {
    "gore",
    "tex",
    "gtx",
    "goretex",
    "jacket",
    "jackets",
    "hoody",
    "hoodie",
    "hooded",
    "hood",
    "pants",
    "pant",
    "shoe",
    "shoes",
    "boot",
    "boots",
    "waterproof",
    "wp",
    "men",
    "women",
    "mens",
    "womens",
    "crew",
    "long",
    "sleeve",
    "the",
    "and",
    "with",
    "series",
    "full",
    "zip",
    "half",
    "top",
    "bottom",
    "bottoms",
    "tights",
    "pullover",
    "sock",
    "socks",
    "tent",
    "pack",
    "backpack",
    "sleeping",
    "bag",
    "pad",
    "headlamp",
    "trekking",
    "pole",
    "poles",
    "co",
    "op",
    "insulated",
    "down",
    "fleece",
    "parka",
    "vest",
    "short",
    "shorts",
}


# 版本后缀：型号 token 后紧跟这些词时属于另一款
_VARIANTS = {
    "ar",
    "sv",
    "lt",
    "fl",
    "sl",
    "ul",
    "mx",
    "pro",
    "max",
    "plus",
    "lite",
    "elite",
    "ultra",
}


def _norm(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]+>", "", text or ""))
    return text.replace("’", "'").lower()


def model_tokens(model: str) -> list[str]:
    """型号中用于匹配的关键 token（去掉通用词，保留数字与短后缀如 AR/SV/LT）。"""
    toks = re.findall(r"[a-z0-9]+(?:\.[0-9]+)?|[\u4e00-\u9fff]{2,}", _norm(model))
    return [t for t in toks if t not in _GENERIC]


# 品类关键词：好价标题（含商城类目）须命中其一，避免 "Beta AR 裤" 混进冲锋衣价格
CATEGORY_WORDS: dict[str, tuple[str, ...]] = {
    "hardshell": ("冲锋", "夹克", "外套", "jacket", "硬壳"),
    "rain_jacket": ("冲锋", "夹克", "外套", "jacket", "雨衣", "皮肤衣"),
    "softshell": ("软壳", "夹克", "外套", "jacket", "hoody"),
    "fleece": ("抓绒", "摇粒绒", "夹克", "外套", "fleece", "卫衣", "hoody"),
    "baselayer": ("打底", "内衣", "速干", "秋衣", "长袖", "短袖", "t恤", "羊毛衫", "裤", "上衣"),
    "down": ("羽绒",),
    "insulated": ("棉服", "棉衣", "保暖", "夹克", "外套", "jacket", "hoody"),
    "hiking_pants": ("裤",),
    "rain_pants": ("裤",),
    "socks": ("袜",),
    "shoes": ("鞋",),
    "hiking_boots": ("鞋", "靴"),
    "trail_running": ("鞋",),
    "approach": ("鞋",),
    "tents": ("帐",),
    "poles": ("杖",),
    "backpacks": ("包",),
    "daypacks": ("包",),
    "sleeping_bags": ("睡袋",),
    "sleeping_pads": ("垫",),
    "headlamps": ("灯",),
}


def category_matches(text: str, category: str | None) -> bool:
    if not category or category not in CATEGORY_WORDS:
        return True
    t = _norm(text)
    return any(w in t for w in CATEGORY_WORDS[category])


# 强品类词：内容里出现别的品类强词、却没有本品类词时，视为在说别的款（如 Beta AR 裤）
_STRONG = ("裤", "鞋", "靴", "袜", "帐篷", "登山杖", "睡袋", "睡垫", "头灯", "背包", "羽绒")


def content_category_ok(text: str, category: str | None) -> bool:
    if not category or category not in CATEGORY_WORDS or category_matches(text, category):
        return True
    if category in ("hiking_pants", "rain_pants"):  # 裤子常与同名夹克共用型号，必须明确提到"裤"
        return False
    t = _norm(text)
    own = CATEGORY_WORDS[category]
    return not any(w in t for w in _STRONG if not any(w in o or o in w for o in own))


def title_matches(title: str, tokens: list[str], brand_words: list[str]) -> bool:
    """标题须包含品牌（中文或英文任一）且包含全部型号关键 token。"""
    if not tokens:
        return False
    t = _norm(title)
    if brand_words and not any(b.lower() in t for b in brand_words if b):
        return False
    for tok in tokens:
        if tok.isdigit() or len(tok) <= 3:
            # 短 token / 纯数字要求边界，避免 "ar" 命中 "arc'teryx"、"6" 命中 "16"
            if not re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", t):
                return False
        elif tok not in t.replace(" ", "") and tok not in t:
            return False
    # 型号后紧跟其它版本后缀（如查 "Beta" 却是 "Beta AR"）视为不同款
    last = re.escape(tokens[-1])
    for m in re.finditer(rf"(?<![a-z0-9]){last}[\s\-]*([a-z]+)(?![a-z])", t):
        if m.group(1) in _VARIANTS and m.group(1) not in tokens:
            return False
    return True


@dataclass
class CnContent:
    platform: str  # 什么值得买 / B站 / 小红书
    kind: str  # 好价 / 测评文章 / 视频 / 笔记
    title: str
    url: str
    author: str = ""
    metric_label: str = ""  # 如 "播放"、"值"、"点赞"
    metric_value: int = 0
    date: str = ""  # YYYY-MM-DD
    cover: str = ""
    price_cny: float | None = None
    mall: str = ""
    summary: str = ""  # 正文摘要（什么值得买原创 / 小红书笔记前 120 字）

    def to_dict(self) -> dict:
        return asdict(self)


def _ts_date(ts: str | int | None) -> str:
    try:
        return datetime.fromtimestamp(int(ts or 0), tz=UTC).strftime("%Y-%m-%d") if ts else ""
    except (ValueError, OverflowError, OSError):
        return ""


def _int(v: object) -> int:
    try:
        return int(str(v).replace(",", "").strip() or 0)
    except ValueError:
        m = re.match(r"([\d.]+)\s*万", str(v))
        return int(float(m.group(1)) * 10000) if m else 0


def _https(url: str) -> str:
    return "https://" + url[len("http://") :] if url.startswith("http://") else url


def parse_smzdm_list(
    payload: dict,
    tokens: list[str],
    brand_words: list[str],
    kind: str,
    category: str | None = None,
) -> list[CnContent]:
    rows = (payload.get("data") or {}).get("rows") or [] if isinstance(payload, dict) else []
    out: list[CnContent] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        title = _norm(r.get("article_title", ""))
        content = _norm(r.get("article_filter_content", "")) if kind != "好价" else ""
        haystack = f"{title} {_norm(r.get('article_brand', ''))} {content[:300]}"
        if not title_matches(haystack, tokens, brand_words):
            continue
        cats = " ".join(
            str(c.get("title", "")) for c in r.get("article_category") or [] if isinstance(c, dict)
        )
        if kind == "好价" and not category_matches(title + " " + cats, category):
            continue
        if kind != "好价" and not content_category_ok(f"{title} {content[:300]}", category):
            continue
        price = None
        m = re.search(r"([\d,]+(?:\.\d+)?)\s*元", str(r.get("article_price", "")))
        if m:
            price = float(m.group(1).replace(",", ""))
        worthy = _int(r.get("article_worthy"))
        out.append(
            CnContent(
                platform="什么值得买",
                kind=kind,
                title=html.unescape(r.get("article_title", "")),
                url=_https(r.get("article_url", "")),
                author=r.get("article_referrals", "") or "",
                metric_label="值" if kind == "好价" else "收藏",
                metric_value=worthy if kind == "好价" else _int(r.get("article_collection")),
                date=_ts_date(r.get("publish_date_lt")),
                cover=_https(str(r.get("article_pic", ""))),
                price_cny=price if kind == "好价" else None,
                mall=r.get("article_mall", "") or "",
                summary=html.unescape(r.get("article_filter_content", "") or "")[:120],
            )
        )
    return out


def split_smzdm_mixed(payload: dict) -> tuple[dict, dict]:
    """不带 type 的混合检索结果按频道拆分：11=原创测评，其余（1 海淘 / 2 国内 …）=好价。"""
    rows = ((payload or {}).get("data") or {}).get("rows") or []
    posts = [r for r in rows if str(r.get("article_channel_id")) == "11"]
    deals = [r for r in rows if str(r.get("article_channel_id")) != "11"]
    return {"data": {"rows": deals}}, {"data": {"rows": posts}}


def parse_mediacrawler_bili(
    videos: list[dict], tokens: list[str], brand_words: list[str], category: str | None = None
) -> list[CnContent]:
    """MediaCrawler B站导出（store/bilibili 的 video 字段）→ CnContent。

    api.bilibili.com 的 robots.txt 为 Disallow: /，本项目不直接请求，只导入用户自行采集的文件。
    """
    out: list[CnContent] = []
    for v in videos:
        title = html.unescape(re.sub(r"<[^>]+>", "", str(v.get("title", ""))))
        text = f"{title} {v.get('desc', '')}"
        if not title_matches(text, tokens, brand_words) or not content_category_ok(text, category):
            continue
        bvid = v.get("bvid") or ""
        url = v.get("video_url") or (f"https://www.bilibili.com/video/{bvid}" if bvid else "")
        if not url:
            continue
        out.append(
            CnContent(
                platform="B站",
                kind="视频",
                title=title[:80],
                url=_https(url),
                author=v.get("nickname", ""),
                metric_label="播放",
                metric_value=_int(v.get("video_play_count")),
                date=_ts_date(v.get("create_time")),
                cover=_https(str(v.get("video_cover_url", ""))),
                summary=str(v.get("desc", ""))[:120],
            )
        )
    out.sort(key=lambda c: c.metric_value, reverse=True)
    return out


def parse_mediacrawler_xhs(
    notes: list[dict], tokens: list[str], brand_words: list[str], category: str | None = None
) -> list[CnContent]:
    """MediaCrawler 小红书导出（store/xhs 的 note 字段）→ CnContent。"""
    out: list[CnContent] = []
    for n in notes:
        text = f"{n.get('title', '')} {n.get('desc', '')} {n.get('tag_list', '')}"
        if not title_matches(text, tokens, brand_words) or not content_category_ok(text, category):
            continue
        cover = str(n.get("image_list", "")).split(",")[0]
        ts = n.get("time")
        out.append(
            CnContent(
                platform="小红书",
                kind="笔记",
                title=(n.get("title") or n.get("desc", ""))[:80],
                url=n.get("note_url", ""),
                author=n.get("nickname", ""),
                metric_label="点赞",
                metric_value=_int(n.get("liked_count")),
                date=_ts_date(int(ts) // 1000 if ts and int(ts) > 10**11 else ts),
                cover=cover,
                summary=str(n.get("desc", ""))[:120],
            )
        )
    out.sort(key=lambda c: c.metric_value, reverse=True)
    return out


def summarize_prices(deals: list[CnContent]) -> dict | None:
    """国内好价汇总：最低 / 中位 / 条数 / 最近日期 / 常见商城。"""
    prices = [d.price_cny for d in deals if d.price_cny and d.price_cny > 1]
    if not prices:
        return None
    # 剔除离群价（配件/定金/错标）：保留中位数 0.4~2.5 倍区间
    mid = statistics.median(prices)
    kept = [p for p in prices if 0.4 * mid <= p <= 2.5 * mid]
    prices = kept or prices
    malls: dict[str, int] = {}
    for d in deals:
        if d.mall:
            malls[d.mall] = malls.get(d.mall, 0) + 1
    return {
        "min_cny": min(prices),
        "median_cny": statistics.median(prices),
        "count": len(prices),
        "latest_date": max((d.date for d in deals if d.date), default=""),
        "malls": sorted(malls, key=lambda k: -malls[k])[:3],
    }
