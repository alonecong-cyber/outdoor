"""国内口碑数据：什么值得买 / B站 快照解析、MediaCrawler 小红书导入、译文与国货款合并。"""

import json
import sys
from pathlib import Path

from app.rankings.sources.cn import (
    model_tokens,
    parse_mediacrawler_bili,
    parse_mediacrawler_xhs,
    parse_smzdm_list,
    split_smzdm_mixed,
    summarize_prices,
    title_matches,
)

FIX = Path(__file__).resolve().parents[2] / "data" / "fixtures"
BETA = (model_tokens("Beta AR"), ["始祖鸟", "Arc'teryx", "arcteryx"])


def _load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_model_tokens_and_matching():
    assert model_tokens("Beta AR Jacket") == ["beta", "ar"]
    assert title_matches("始祖鸟 BETA AR JACKET 男子冲锋衣", *BETA)
    assert not title_matches("始祖鸟 Beta LT 冲锋衣", *BETA)  # 缺少 AR
    assert not title_matches("Salomon Beta AR", *BETA)  # 品牌不符
    # 查 "Beta" 时，"Beta AR" 属于另一版本
    assert not title_matches("始祖鸟 Beta AR 冲锋衣", ["beta"], BETA[1])
    assert title_matches("始祖鸟 Beta Jacket 冲锋衣", ["beta"], BETA[1])


def test_parse_smzdm_good_price_snapshot():
    deals = parse_smzdm_list(_load("smzdm_good_price_beta_ar.json"), *BETA, "好价", "hardshell")
    assert deals and all(d.platform == "什么值得买" and d.kind == "好价" for d in deals)
    assert all(d.price_cny and d.url.startswith("https://") for d in deals)
    summary = summarize_prices(deals)
    assert summary and summary["count"] == len(deals)
    assert summary["min_cny"] <= summary["median_cny"]
    assert "京东" in summary["malls"]


def test_parse_smzdm_articles_and_mixed_split():
    posts = parse_smzdm_list(_load("smzdm_yuanchuang_beta_ar.json"), *BETA, "测评文章")
    assert posts and all("beta" in p.title.lower() for p in posts)
    good = _load("smzdm_good_price_beta_ar.json")["data"]["rows"]
    arts = _load("smzdm_yuanchuang_beta_ar.json")["data"]["rows"]
    deals, articles = split_smzdm_mixed({"data": {"rows": good + arts}})
    assert len(deals["data"]["rows"]) == len(good)
    assert len(articles["data"]["rows"]) == len(arts)


def test_mediacrawler_bili_import():
    vids = parse_mediacrawler_bili(_load("mediacrawler_bili_videos.json"), *BETA)
    assert len(vids) == 1  # 第二条是 "Beta"（无 AR）对比视频
    v = vids[0]
    assert v.platform == "B站" and v.metric_value == 153000 and v.date == "2024-06-01"
    assert v.url.startswith("https://www.bilibili.com/video/") and v.cover.startswith("https://")


def test_summarize_prices_drops_outliers():
    deals = parse_smzdm_list(_load("smzdm_good_price_beta_ar.json"), *BETA, "好价", "hardshell")
    deals[0].price_cny = 99.0  # 配件 / 定金类离群价
    summary = summarize_prices(deals)
    assert summary and summary["min_cny"] > 1000


def test_mediacrawler_xhs_import():
    notes = _load("mediacrawler_xhs_notes.json")
    hits = parse_mediacrawler_xhs(notes, *BETA, "hardshell")
    assert len(hits) == 1
    n = hits[0]
    assert n.platform == "小红书" and n.metric_value == 12000 and n.date == "2024-06-01"
    assert n.cover.startswith("https://") and n.url.endswith("64f000000000000000000001")

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import import_mediacrawler as im

    items = [
        {
            "id": "a",
            "name": "Arc'teryx Beta AR Jacket",
            "brand": "arcteryx",
            "category": "hardshell",
        },
        {
            "id": "b",
            "name": "Arc'teryx Beta Jacket",
            "brand": "arcteryx",
            "category": "rain_jacket",
        },
        {
            "id": "c",
            "name": "Arc'teryx Beta AR Pant",
            "brand": "arcteryx",
            "category": "rain_pants",
        },
        {
            "id": "d",
            "name": "Salomon Speedcross 6",
            "brand": "salomon",
            "category": "trail_running",
        },
    ]
    matched = im.match_notes(items, notes + _load("mediacrawler_bili_videos.json"))
    assert set(matched) == {"a", "b", "d"}  # b：视频标题里的 "始祖鸟 Beta" 正是 Beta Jacket
    assert set(matched["a"]) == {"xhs_notes", "bili_videos"}
    assert set(matched["b"]) == {"bili_videos"}
    assert set(matched["d"]) == {"xhs_notes"}
