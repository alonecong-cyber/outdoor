"""权威装备榜单与横评对比 API 测试。"""

from fastapi.testclient import TestClient

from app.main import create_app


def test_list_categories():
    client = TestClient(create_app())
    resp = client.get("/api/rankings/categories")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 10
    categories = {c["id"] for c in data}
    expected = {
        "hardshell",
        "softshell",
        "fleece",
        "baselayer",
        "socks",
        "shoes",
        "tents",
        "poles",
        "insulated",
        "backpacks",
    }
    assert categories == expected
    for c in data:
        # 扩充后每品类 ≥5 款、三价位段全覆盖，统计与真实条目一致（动态计算）
        assert c["total_count"] >= 5
        assert c["tier_counts"]["budget"] >= 1
        assert c["tier_counts"]["mid"] >= 1
        assert c["tier_counts"]["flagship"] >= 1
        assert sum(c["tier_counts"].values()) == c["total_count"]
    # 基础 30 + 扩展 34 = 64
    assert sum(c["total_count"] for c in data) == 64


def test_list_rankings_all():
    client = TestClient(create_app())
    resp = client.get("/api/rankings")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 64
    for item in items:
        assert item["id"]
        assert item["name"]
        assert item["image"].startswith("http")
        assert item["rating_score"] > 70
        assert item["price_guide"]["price_cents"] > 0
        assert item["price_tier"] in {"budget", "mid", "flagship"}
        assert len(item["authorities"]) >= 1
        assert len(item["pros"]) >= 1
        assert len(item["cons"]) >= 1
        assert item["gap_analysis"]


def test_filter_by_category():
    client = TestClient(create_app())
    resp = client.get("/api/rankings?category=hardshell")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 8
    for it in items:
        assert it["category"] == "hardshell"
    tiers = {it["price_tier"] for it in items}
    assert tiers == {"budget", "mid", "flagship"}


def test_filter_by_tier():
    client = TestClient(create_app())
    resp = client.get("/api/rankings?tier=budget")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 20
    for it in items:
        assert it["price_tier"] == "budget"


def test_rankings_multi_brand_matrix():
    """扩充后每品类须形成多品牌梯队：三价位段全覆盖、品牌数 ≥2、款式数 ≥5。"""
    client = TestClient(create_app())
    resp = client.get("/api/rankings")
    items = resp.json()
    assert len(items) == 64
    by_category: dict[str, list[dict]] = {}
    for it in items:
        by_category.setdefault(it["category"], []).append(it)
    assert len(by_category) == 10
    for cat, its in by_category.items():
        assert len(its) >= 5, f"{cat} 仅 {len(its)} 款"
        tiers = {it["price_tier"] for it in its}
        assert tiers == {"budget", "mid", "flagship"}, f"{cat} 价位段不全: {sorted(tiers)}"
        brands = {it["brand"] for it in its}
        assert len(brands) >= 2, f"{cat} 品牌数不足: {brands}"


def test_filter_by_source():
    client = TestClient(create_app())
    resp = client.get("/api/rankings?source=OutdoorGearLab")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 5
    for it in items:
        sources = [a["source"].lower() for a in it["authorities"]]
        assert any("outdoorgearlab" in s for s in sources)


def test_search_and_sort():
    client = TestClient(create_app())
    resp = client.get("/api/rankings?q=始祖鸟&sort=price_desc")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 4
    # 检验降序排序
    prices = [it["price_guide"]["price_cents"] for it in items]
    assert prices == sorted(prices, reverse=True)


def test_get_ranking_detail():
    client = TestClient(create_app())
    resp = client.get("/api/rankings/hardshell_arcteryx_beta_ar")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Arc'teryx Beta AR Jacket"
    assert data["brand"] == "arcteryx"
    assert "DropHood" in data["bottom_line"] or any(
        "DropHood" in f for f in data["specs"]["key_features"]
    )

    resp_404 = client.get("/api/rankings/non_existent_item")
    assert resp_404.status_code == 404


def test_compare_rankings_success():
    client = TestClient(create_app())
    # GET 形式比较
    ids = "hardshell_decathlon_mh500,hardshell_patagonia_torrentshell,hardshell_arcteryx_beta_ar"
    resp = client.get(f"/api/rankings/compare?ids={ids}")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["items"]) == 3
    assert data["category"] == "hardshell"
    assert data["category_name"] == "硬壳冲锋衣"
    assert "差价" in data["gap_summary"]
    assert len(data["attributes"]) >= 8

    # POST 形式比较
    resp_post = client.post(
        "/api/rankings/compare",
        json={"ids": ["hardshell_decathlon_mh500", "hardshell_arcteryx_beta_ar"]},
    )
    assert resp_post.status_code == 200
    data_post = resp_post.json()
    assert len(data_post["items"]) == 2


def test_compare_rankings_validation():
    client = TestClient(create_app())
    # 少于 2 款
    resp_one = client.post("/api/rankings/compare", json={"ids": ["hardshell_arcteryx_beta_ar"]})
    assert resp_one.status_code == 400

    # 超过 4 款
    resp_many = client.post(
        "/api/rankings/compare",
        json={
            "ids": [
                "hardshell_decathlon_mh500",
                "hardshell_patagonia_torrentshell",
                "hardshell_arcteryx_beta_ar",
                "softshell_pioneer_camp",
                "softshell_marmot_rom",
            ]
        },
    )
    assert resp_many.status_code == 400

    # 不存在的款
    resp_miss = client.post(
        "/api/rankings/compare",
        json={"ids": ["hardshell_decathlon_mh500", "invalid_id_xxx"]},
    )
    assert resp_miss.status_code == 404
