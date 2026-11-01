"""权威榜单页解析器测试（以真实页面快照为准）。"""

from app.config import FIXTURES_DIR
from app.rankings.brands import detect_brand
from app.rankings.sources.ogl import parse_ogl_compare
from app.rankings.sources.switchback import parse_switchback


def test_parse_ogl_compare_table():
    html = (FIXTURES_DIR / "ogl_best_hardshell.html").read_text()
    prods = parse_ogl_compare(html)
    assert len(prods) == 12
    beta = prods[0]
    assert beta.rank == 1
    assert beta.name == "Arc'teryx Beta AR"
    assert beta.overall_score == 83
    assert beta.list_price_usd == 650
    assert beta.awards == ["Best Mobility"]
    assert beta.image_url.endswith("_L.jpg")
    assert beta.review_url.startswith("https://www.outdoorgearlab.com/reviews/")
    assert beta.ratings["Weather Protection (30%)"] == 9.3
    assert beta.specs["Measured Weight"] == "16 oz"
    assert "range of motion" in beta.pros


def test_parse_switchback_awards_in_h2():
    html = (FIXTURES_DIR / "switchback_best_rain_jackets.html").read_text()
    prods = parse_switchback(html)
    assert len(prods) >= 10
    first = prods[0]
    assert first.award == "Best Overall Rain Jacket"
    assert first.name == "Patagonia Torrentshell 3L"
    assert first.price_usd == 189
    assert first.image_url.startswith("https://www.switchbacktravel.com/")
    assert first.like and first.dislike
    assert prods[5].award == "Step Up From Budget"


def test_detect_brand():
    brand, model = detect_brand("Norrona Trollveggen Gore-Tex Pro Light")
    assert brand and brand.name_cn == "挪威小鸟"
    assert model == "Trollveggen Gore-Tex Pro Light"
    brand, _ = detect_brand("The North Face Summit Series Papsura")
    assert brand and brand.slug == "thenorthface"
    assert detect_brand("Amazon Essentials Full-Zip Polar Fleece")[0] is None
