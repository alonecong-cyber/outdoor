"""权威榜单数据源：加载由 scripts/build_rankings.py 生成的 catalog.json。

catalog.json 来自 OutdoorGearLab 实测对比表 + Switchback Travel 编辑榜单的合并结果，
每个产品都带出处链接、排名、实测分（OGL）、美标价、海淘落地估算与本地产品图。
更新数据：cd backend && uv run python scripts/build_rankings.py

国内数据（scripts/enrich_cn.py 生成，缺失时自动跳过）：
- cn_catalog.json：国货品牌口碑款（什么值得买好价 + B站），与 catalog.json 同结构，`_cn` 为口碑明细
- cn_reviews.json：海外款的国内好价 / 原创测评 / B站视频 / 小红书笔记（import_mediacrawler.py）
- translations_zh.json：评价摘录等机器翻译（Qwen2.5 本地模型 / Google，经术语表修正）
- pros_cons_zh.json：优缺点人工翻译（优先级高于机翻）；奖项与分项名见 glossary_zh.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.rankings.catalog_config import CATEGORIES
from app.rankings.glossary_zh import BADGES_ZH, SUB_SCORES_ZH
from app.rankings.schemas import CategoryMeta, GearCategory, GearRankingItem

RANK_DIR = Path(__file__).parent
CATALOG_PATH = RANK_DIR / "catalog.json"
CN_CATALOG_PATH = RANK_DIR / "cn_catalog.json"
CN_REVIEWS_PATH = RANK_DIR / "cn_reviews.json"
TRANSLATIONS_PATH = RANK_DIR / "translations_zh.json"
PROS_CONS_ZH_PATH = RANK_DIR / "pros_cons_zh.json"  # 人工翻译，优先于机翻
_TIER_NAMES = {"budget": "入门性价比", "mid": "进阶主力", "flagship": "顶级旗舰"}


def _read(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def _cn_reviews(rec: dict) -> list[dict]:
    """国内口碑内容：原创测评 → B站 → 小红书 → 最近好价。"""
    out = (
        rec.get("smzdm_posts", [])[:3]
        + rec.get("bili_videos", [])[:3]
        + rec.get("xhs_notes", [])[:3]
        + rec.get("smzdm_deals", [])[:3]
    )
    return out


def _apply_cn(raw: dict, rec: dict, zh: dict[str, str]) -> dict:
    t = lambda s: zh.get(s, "")  # noqa: E731
    raw["pros_zh"] = [t(p) or p for p in raw["pros"]]
    raw["cons_zh"] = [t(c) or c for c in raw["cons"]]
    raw["sub_scores_zh"] = {
        k: SUB_SCORES_ZH.get(k) or t(k)
        for k in raw.get("sub_scores", {})
        if SUB_SCORES_ZH.get(k) or t(k)
    }
    for a in raw["authorities"]:
        a["badge_zh"] = BADGES_ZH.get(a["badge"]) or t(a["badge"])
        a["quote_zh"] = t(a["quote"])
    raw["is_cn_brand"] = raw.get("brand_country") == "中国"
    if rec:
        raw["cn_price"] = rec.get("cn_price")
        raw["cn_query"] = rec.get("smzdm_query", "")
        raw["cn_reviews"] = _cn_reviews(rec)
    return raw


def _retier_cn(items: list[dict]) -> None:
    """国货口碑款按同品类海外款的价位分界重新划分梯队。"""
    bounds: dict[str, dict[str, int]] = {}
    for r in items:
        if r["id"].startswith("cn_"):
            continue
        b = bounds.setdefault(r["category"], {})
        tier = r["price_tier"]
        b[tier] = max(b.get(tier, 0), r["price_guide"]["price_cents"])
    for r in items:
        if not r["id"].startswith("cn_"):
            continue
        b = bounds.get(r["category"], {})
        price = r["price_guide"]["price_cents"]
        tier = "flagship"
        if price <= b.get("budget", 0):
            tier = "budget"
        elif price <= b.get("mid", 0):
            tier = "mid"
        r["price_tier"], r["price_tier_name"] = tier, _TIER_NAMES[tier]


def _load_items() -> list[GearRankingItem]:
    raw = _read(CATALOG_PATH, []) + _read(CN_CATALOG_PATH, [])
    reviews = _read(CN_REVIEWS_PATH, {})
    zh = {**_read(TRANSLATIONS_PATH, {}), **_read(PROS_CONS_ZH_PATH, {})}
    _retier_cn(raw)
    out = []
    for r in raw:
        rec = {**(r.pop("_cn", None) or {}), **reviews.get(r["id"], {})}
        out.append(GearRankingItem.model_validate(_apply_cn(r, rec, zh)))
    return out


RANKING_ITEMS: list[GearRankingItem] = _load_items()


def _build_categories_meta() -> list[CategoryMeta]:
    """按 RANKING_ITEMS 动态计算每个品类的 total_count 与 tier_counts。"""
    tier_counts: dict[GearCategory, dict[str, int]] = {
        c.id: {"budget": 0, "mid": 0, "flagship": 0} for c in CATEGORIES
    }
    for item in RANKING_ITEMS:
        tier_counts[item.category][item.price_tier.value] += 1
    return [
        CategoryMeta(
            id=c.id,
            name=c.name,
            description=c.description,
            icon_name=c.icon_name,
            total_count=sum(tier_counts[c.id].values()),
            tier_counts=tier_counts[c.id],
        )
        for c in CATEGORIES
    ]


CATEGORIES_META: list[CategoryMeta] = _build_categories_meta()
