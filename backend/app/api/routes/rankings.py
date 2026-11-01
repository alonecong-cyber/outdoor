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
    q: str | None = None,
    sort: str | None = Query(None, description="排序：price_asc / price_desc / score_desc"),
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
            or any(term in sc.lower() for sc in item.specs.scenarios)
        ]

    if sort == "price_asc":
        results.sort(key=lambda x: x.price_guide.price_cents)
    elif sort == "price_desc":
        results.sort(key=lambda x: x.price_guide.price_cents, reverse=True)
    elif sort == "score_desc":
        results.sort(key=lambda x: x.rating_score, reverse=True)

    return results


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

    # 生成跨价位横向差价与边际效用总结
    tiers_present = {it.price_tier for it in selected_items}
    if len(tiers_present) > 1 and is_same_category:
        sorted_by_price = sorted(selected_items, key=lambda x: x.price_guide.price_cents)
        lowest = sorted_by_price[0]
        highest = sorted_by_price[-1]
        gap_summary = (
            f"【差价与选购结论】：从「{lowest.name_cn}」({lowest.price_guide.deal_cny}) "
            f"到「{highest.name_cn}」({highest.price_guide.deal_cny})，"
            f"差价主要体现在核心面料膜层科技、物理抗撕裂 D 数与极端耐候寿命上。"
            f"日常 80% 通勤与轻度徒步建议选性价比入门/中端款；"
            f"若涉及高海拔暴风雪或长距离多日穿越，旗舰款安全边际无可替代。"
        )
    else:
        gap_summary = "本组对比专注于相同梯队在材质剪裁、重量控制与权威机构实测优缺点上的细微取舍。"

    attributes = [
        "高清大图",
        "指导价 / 国内大促到手价",
        "海淘原价 / 折算落地到手价",
        "价位梯队",
        "权威测评荣誉与得分",
        "核心材质与面料科技",
        "防水与透气等级",
        "重量与收纳特性",
        "适用场景定位",
        "实测优势 (Pros)",
        "实测短板 (Cons)",
        "差价买到了什么 (Gap Analysis)",
    ]

    return CompareMatrixResponse(
        items=selected_items,
        attributes=attributes,
        category=common_category,
        category_name=common_category_name,
        gap_summary=gap_summary,
    )
