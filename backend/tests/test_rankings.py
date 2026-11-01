"""权威装备榜单与横评对比 API 测试（数据来自 catalog.json）。"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from app.rankings.catalog_config import CATEGORIES
from app.rankings.data import RANKING_ITEMS

FRONTEND_PUBLIC = Path(__file__).resolve().parents[2] / "frontend" / "public"
BETA_AR = "hardshell_men_arc-teryx-beta-ar"


def _client() -> TestClient:
    return TestClient(create_app())


def test_list_categories():
    data = _client().get("/api/rankings/categories").json()
    assert {c["id"] for c in data} == {c.id.value for c in CATEGORIES}
    assert len(data) >= 20
    for c in data:
        assert c["total_count"] >= 8, c["id"]
        assert sum(c["tier_counts"].values()) == c["total_count"]
        for tier in ("budget", "mid", "flagship"):
            assert c["tier_counts"][tier] >= 1, (c["id"], tier)
    assert sum(c["total_count"] for c in data) == len(RANKING_ITEMS)


def test_every_item_has_image_price_and_source():
    """图片必须全：每个产品都有本地图且文件存在、互不重复；价格与出处链接齐全。"""
    seen_images: set[str] = set()
    ids: set[str] = set()
    for item in RANKING_ITEMS:
        assert item.id not in ids
        ids.add(item.id)
        assert item.image.startswith("/rankings/"), item.id
        assert (FRONTEND_PUBLIC / item.image.lstrip("/")).is_file(), item.id
        assert item.image not in seen_images
        seen_images.add(item.image)
        assert item.image_remote.startswith("https://")
        assert item.price_guide.price_cents > 0
        assert item.price_guide.overseas_usd.startswith("$")
        assert item.authorities, item.id
        for auth in item.authorities:
            assert auth.url.startswith("https://"), item.id
        assert item.cn_links


def test_many_brands_per_category():
    brands = {it.brand for it in RANKING_ITEMS}
    assert len(brands) >= 80
    by_cat: dict[str, set[str]] = {}
    for it in RANKING_ITEMS:
        by_cat.setdefault(it.category.value, set()).add(it.brand)
    for cat, bs in by_cat.items():
        assert len(bs) >= 5, f"{cat} 品牌数不足: {bs}"


def test_filter_by_category_gender_and_source():
    items = _client().get("/api/rankings?category=hardshell&gender=women").json()
    assert items
    assert all(it["category"] == "hardshell" for it in items)
    assert all(it["gender"] in ("women", "unisex") for it in items)

    items = _client().get("/api/rankings?source=Switchback").json()
    assert items
    assert all(any("switchback" in a["source"].lower() for a in it["authorities"]) for it in items)


def test_search_and_sort():
    items = _client().get("/api/rankings?q=始祖鸟&sort=price_desc").json()
    assert len(items) >= 10
    assert all(it["brand"] == "arcteryx" for it in items)
    prices = [it["price_guide"]["price_cents"] for it in items]
    assert prices == sorted(prices, reverse=True)

    scored = _client().get("/api/rankings?category=shoes&sort=score_desc").json()
    scores = [it["rating_score"] or 0 for it in scored]
    assert scores == sorted(scores, reverse=True)


def test_brands_and_sources_endpoints():
    brands = _client().get("/api/rankings/brands").json()
    assert len(brands) >= 80
    assert brands[0]["count"] >= brands[-1]["count"]
    sources = {s["source"] for s in _client().get("/api/rankings/sources").json()}
    assert {"OutdoorGearLab", "Switchback Travel"} <= sources


def test_get_ranking_detail():
    data = _client().get(f"/api/rankings/{BETA_AR}").json()
    assert data["brand"] == "arcteryx"
    assert data["rating_score"] and data["rating_score"] > 70
    assert {a["source"] for a in data["authorities"]} == {"OutdoorGearLab", "Switchback Travel"}
    assert data["sub_scores"]
    assert _client().get("/api/rankings/non_existent_item").status_code == 404


def test_compare_rankings():
    ids = [it.id for it in RANKING_ITEMS if it.category.value == "hardshell" and it.rating_score][
        :3
    ]
    resp = _client().get(f"/api/rankings/compare?ids={','.join(ids)}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["category"] == "hardshell"
    assert "OGL 实测最高分" in data["gap_summary"]

    client = _client()
    assert client.post("/api/rankings/compare", json={"ids": ids[:1]}).status_code == 400
    many = [it.id for it in RANKING_ITEMS[:5]]
    assert client.post("/api/rankings/compare", json={"ids": many}).status_code == 400
    assert client.post("/api/rankings/compare", json={"ids": [ids[0], "nope"]}).status_code == 404
