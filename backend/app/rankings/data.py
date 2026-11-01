"""权威榜单数据源：加载由 scripts/build_rankings.py 生成的 catalog.json。

catalog.json 来自 OutdoorGearLab 实测对比表 + Switchback Travel 编辑榜单的合并结果，
每个产品都带出处链接、排名、实测分（OGL）、美标价、海淘落地估算与本地产品图。
更新数据：cd backend && uv run python scripts/build_rankings.py
"""

from __future__ import annotations

import json
from pathlib import Path

from app.rankings.catalog_config import CATEGORIES
from app.rankings.schemas import CategoryMeta, GearCategory, GearRankingItem

CATALOG_PATH = Path(__file__).with_name("catalog.json")


def _load_items() -> list[GearRankingItem]:
    raw = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    return [GearRankingItem.model_validate(r) for r in raw]


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
