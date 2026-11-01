"""权威榜单与多维横评 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.rankings.data import CATEGORIES_META, RANKING_ITEMS
from app.rankings.schemas import (
    CategoryMeta,
    CompareMatrixResponse,
    GearCategory,
    GearRankingItem,
    PriceTier,
)

router = APIRouter(prefix="/rankings", tags=["rankings"])


class CompareRequest(BaseModel):
    ids: list[str]


class BrandStat(BaseModel):
    brand: str
    brand_name: str
    country: str
    count: int
    categories: list[str]


class SourceStat(BaseModel):
    source: str
    count: int


@router.get("/categories", response_model=list[CategoryMeta])
def list_categories() -> list[CategoryMeta]:
    """获取所有权威榜单评测分类与各价位段数量统计。"""
    return CATEGORIES_META


@router.get("", response_model=list[GearRankingItem])
def list_rankings(
    category: GearCategory | None = None,
    tier: PriceTier | None = None,
    source: str | None = Query(
        None, description="权威来源，如 OutdoorGearLab / Switchback / SMZDM 等"
    ),
    brand: str | None = None,
    gender: str | None = Query(None, description="men / women / unisex"),
    q: str | None = None,
    sort: str | None = Query(
        None, description="排序：price_asc / price_desc / score_desc / value_desc / awards_desc"
    ),
) -> list[GearRankingItem]:
    """多维检索权威榜单与装备推荐库。"""
    results = list(RANKING_ITEMS)

    if category:
        results = [item for item in results if item.category == category]

    if tier:
        results = [item for item in results if item.price_tier == tier]

    if source:
        source_clean = source.strip().lower()
        results = [
            item
            for item in results
            if any(source_clean in auth.source.lower() for auth in item.authorities)
        ]

    if brand:
        brand_clean = brand.strip().lower()
        results = [item for item in results if item.brand.lower() == brand_clean]

    if gender:
        results = [item for item in results if item.gender in (gender, "unisex")]

    if q and q.strip():
        term = q.strip().lower()
        results = [
            item
            for item in results
            if term in item.name.lower()
            or term in item.name_cn.lower()
            or term in item.brand_name.lower()
            or term in item.category_name.lower()
            or term in item.specs.material.lower()
            or term in item.bottom_line.lower()
            or term in item.brand.lower()
            or any(term in sc.lower() for sc in item.specs.scenarios)
        ]

    if sort == "price_asc":
        results.sort(key=lambda x: x.price_guide.price_cents)
    elif sort == "price_desc":
        results.sort(key=lambda x: x.price_guide.price_cents, reverse=True)
    elif sort == "score_desc":
        results.sort(key=lambda x: (x.rating_score or 0, len(x.authorities)), reverse=True)
    elif sort == "value_desc":
        # 每百元得分（只对有实测分的产品有意义，无分的排后）
        results.sort(
            key=lambda x: (x.rating_score or 0) / max(x.price_guide.price_cents, 1), reverse=True
        )
    elif sort == "awards_desc":
        results.sort(key=lambda x: (len(x.authorities), x.rating_score or 0), reverse=True)

    return results


@router.get("/brands", response_model=list[BrandStat])
def list_brands(category: GearCategory | None = None) -> list[BrandStat]:
    """品牌列表（按收录产品数降序），可按品类过滤。"""
    stats: dict[str, BrandStat] = {}
    for item in RANKING_ITEMS:
        if category and item.category != category:
            continue
        st = stats.setdefault(
            item.brand,
            BrandStat(
                brand=item.brand,
                brand_name=item.brand_name,
                country=item.brand_country,
                count=0,
                categories=[],
            ),
        )
        st.count += 1
        if item.category_name not in st.categories:
            st.categories.append(item.category_name)
    return sorted(stats.values(), key=lambda s: (-s.count, s.brand))


@router.get("/sources", response_model=list[SourceStat])
def list_sources() -> list[SourceStat]:
    """权威来源及其覆盖产品数。"""
    counts: dict[str, int] = {}
    for item in RANKING_ITEMS:
        for src in {a.source for a in item.authorities}:
            counts[src] = counts.get(src, 0) + 1
    return [SourceStat(source=k, count=v) for k, v in sorted(counts.items(), key=lambda x: -x[1])]


@router.get("/compare", response_model=CompareMatrixResponse)
def compare_rankings_query(
    ids: str = Query(..., description="以逗号分隔的产品 ID 列表，如 id1,id2,id3"),
) -> CompareMatrixResponse:
    """GET 方式的多商品横向对比。"""
    id_list = [i.strip() for i in ids.split(",") if i.strip()]
    return _build_comparison(id_list)


@router.post("/compare", response_model=CompareMatrixResponse)
def compare_rankings_post(body: CompareRequest) -> CompareMatrixResponse:
    """POST 方式的多商品横向对比。"""
    return _build_comparison(body.ids)


@router.get("/{item_id}", response_model=GearRankingItem)
def get_ranking_detail(item_id: str) -> GearRankingItem:
    """获取单件装备权威测评与横评详情。"""
    for item in RANKING_ITEMS:
        if item.id == item_id:
            return item
    raise HTTPException(status_code=404, detail="未找到该榜单装备")


def _build_comparison(ids: list[str]) -> CompareMatrixResponse:
    if len(ids) < 2:
        raise HTTPException(status_code=400, detail="至少需要选择 2 款装备进行横向对比")
    if len(ids) > 4:
        raise HTTPException(status_code=400, detail="最多同时支持 4 款装备同屏横向对比")

    item_map = {item.id: item for item in RANKING_ITEMS}
    selected_items: list[GearRankingItem] = []
    missing_ids = []

    for item_id in ids:
        if item_id in item_map:
            selected_items.append(item_map[item_id])
        else:
            missing_ids.append(item_id)

    if missing_ids:
        raise HTTPException(status_code=404, detail=f"未找到以下对比装备: {', '.join(missing_ids)}")

    categories = {it.category for it in selected_items}
    is_same_category = len(categories) == 1
    common_category = selected_items[0].category if is_same_category else None
    common_category_name = selected_items[0].category_name if is_same_category else "跨品类综合对比"

    gap_summary = _gap_summary(selected_items, is_same_category)

    attributes = [
        "产品图",
        "美标价 / 人民币折算",
        "海淘落地估算",
        "价位梯队",
        "权威榜单排名与得分",
        "分项实测评分",
        "材质",
        "重量",
        "完整规格",
        "实测优点 (Pros)",
        "实测缺点 (Cons)",
        "差价分析",
    ]

    return CompareMatrixResponse(
        items=selected_items,
        attributes=attributes,
        category=common_category,
        category_name=common_category_name,
        gap_summary=gap_summary,
    )


def _gap_summary(items: list[GearRankingItem], same_category: bool) -> str:
    """基于真实数据（价格、OGL 总分、分项分）生成对比结论。"""
    by_price = sorted(items, key=lambda x: x.price_guide.price_cents)
    lo, hi = by_price[0], by_price[-1]
    parts: list[str] = []
    if hi.price_guide.price_cents > lo.price_guide.price_cents:
        diff = (hi.price_guide.price_cents - lo.price_guide.price_cents) / 100
        parts.append(f"最贵的「{hi.name_cn}」比最便宜的「{lo.name_cn}」海淘落地约贵 ¥{diff:,.0f}")
    scored = [it for it in items if it.rating_score]
    if len(scored) >= 2:
        best = max(scored, key=lambda x: x.rating_score or 0)
        value = max(scored, key=lambda x: (x.rating_score or 0) / x.price_guide.price_cents)
        parts.append(f"OGL 实测最高分：「{best.name_cn}」{best.rating_score} 分")
        parts.append(f"性价比（每元得分）最高：「{value.name_cn}」")
        if same_category:
            dims: set[str] = set()
            for it in scored:
                dims.update(it.sub_scores)
            wins = []
            for dim in sorted(dims):
                cands = [it for it in scored if dim in it.sub_scores]
                if len(cands) >= 2:
                    w = max(cands, key=lambda x: x.sub_scores[dim])
                    wins.append(f"{dim}→{w.name}")
            if wins:
                parts.append("分项胜出：" + "，".join(wins))
    if not parts:
        return "所选产品价格与评分接近，建议按版型、重量和使用场景取舍。"
    return "；".join(parts) + "。"
