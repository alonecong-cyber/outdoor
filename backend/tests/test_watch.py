"""关注列表：匹配、目标价、新低、去重（全离线，价格为整数分）。"""

from __future__ import annotations

from datetime import timedelta

from sqlmodel import Session, select

from app.models import Deal, ProductWatch
from app.util import dump_json, utc_now
from app.watch import check_all_watches, check_watch, match_watch_deals

NOW = utc_now()


def _deal(
    session: Session,
    *,
    n: int,
    title: str,
    price_cents: int,
    channel: str = "京东",
    currency: str = "CNY",
    summary: str = "",
    expired: bool = False,
) -> Deal:
    deal = Deal(
        source="test",
        source_id=f"w{n}",
        url=f"https://example.com/w{n}",
        title=title,
        summary=summary,
        price_cents=price_cents,
        currency=currency,
        channel=channel,
        published_at=NOW,
        expired=expired,
    )
    session.add(deal)
    session.flush()
    return deal


def _watch(
    session: Session,
    *,
    name: str = "Beta AR",
    keywords: list[str] | None = None,
    target: int = 0,
    exclude: list[str] | None = None,
    must: list[str] | None = None,
    platforms: list[str] | None = None,
) -> ProductWatch:
    w = ProductWatch(
        name=name,
        keywords_json=dump_json(keywords or []),
        must_words_json=dump_json(must or []),
        exclude_words_json=dump_json(exclude or []),
        platforms_json=dump_json(platforms or []),
        target_price_cents=target,
    )
    session.add(w)
    session.flush()
    return w


def test_match_filters(session: Session):
    d1 = _deal(session, n=1, title="始祖鸟 Beta AR 男款 冲锋衣", price_cents=26320, channel="京东")
    _deal(session, n=2, title="始祖鸟 Beta AR 冲锋衣 保护套", price_cents=5900)
    d3 = _deal(
        session,
        n=3,
        title="今日必买：冲锋衣好价",
        summary="始祖鸟 Beta AR 三合一",
        price_cents=29900,
        channel="天猫",
    )
    _deal(
        session,
        n=4,
        title="Arc'teryx Beta AR Jacket M",
        price_cents=38475,
        channel="evo",
        currency="USD",
    )
    w = _watch(session, keywords=["始祖鸟 Beta AR"], exclude=["保护套"])
    matched = match_watch_deals(w, session.exec(select(Deal)).all())
    assert {d.id for d in matched} == {d1.id, d3.id}  # 排除保护套；USD 条无关键词命中


def test_target_hit_and_24h_dedupe(session: Session):
    d1 = _deal(session, n=10, title="始祖鸟 Beta AR 男款", price_cents=26320)
    w = _watch(session, keywords=["Beta AR"], target=30000)  # 目标 ¥300
    deals = [d1]
    first = check_watch(session, w, deals, now=NOW)
    assert first["matched"] == 1 and first["min_price_cents"] == 26320
    assert len(first["triggered"]) == 1 and first["triggered"][0]["kind"] == "target_hit"
    assert "≤ 目标 ¥300.00" in first["triggered"][0]["reason"]
    session.commit()
    # 24h 内同线报同类型不重复
    second = check_watch(session, w, deals, now=NOW + timedelta(hours=1))
    assert second["triggered"] == []
    # 24h 之后允许再次提醒
    third = check_watch(session, w, deals, now=NOW + timedelta(hours=25))
    assert len(third["triggered"]) == 1
    session.commit()


def test_new_low_only_after_history(session: Session):
    d1 = _deal(session, n=20, title="始祖鸟 Beta AR 男款", price_cents=26320)
    w = _watch(session, keywords=["Beta AR"])
    deals = [d1]
    first = check_watch(session, w, deals, now=NOW)
    assert first["previous_low_cents"] is None
    assert first["triggered"] == []  # 首次无历史，不报新低
    assert "¥263.20" in first["last_result"]
    session.commit()
    # 出现更低价线报 → 新低
    d2 = _deal(session, n=21, title="始祖鸟 Beta AR 男款 365 天新低", price_cents=24900)
    second = check_watch(session, w, [d1, d2], now=NOW + timedelta(hours=2))
    assert len(second["triggered"]) == 1 and second["triggered"][0]["kind"] == "new_low"
    assert "此前最低 ¥263.20" in second["triggered"][0]["reason"]
    session.commit()
    # 价格不变不再触发（24900 不再是「低于」此前最低）
    third = check_watch(session, w, [d1, d2], now=NOW + timedelta(hours=3))
    assert third["triggered"] == []
    session.commit()


def test_expired_and_usd_not_compared(session: Session):
    # 过期线报命中关键词但不参与比价；USD 只计数不比 CNY
    d_exp = _deal(session, n=30, title="始祖鸟 Beta AR 过期", price_cents=1000, expired=True)
    d_usd = _deal(
        session,
        n=31,
        title="始祖鸟 Beta AR evo 折扣",
        price_cents=38475,
        channel="evo",
        currency="USD",
    )
    d_cny = _deal(session, n=32, title="始祖鸟 Beta AR 京东", price_cents=26320)
    w = _watch(session, keywords=["Beta AR"])
    result = check_watch(session, w, [d_exp, d_usd, d_cny], now=NOW)
    assert result["matched"] == 3  # 三条都命中关键词（含过期）
    assert result["min_price_cents"] == 26320  # 过期 1000 不计入最低
    assert result["usd_count"] == 1
    session.commit()


def test_platforms_filter(session: Session):
    d1 = _deal(session, n=40, title="始祖鸟 Beta AR", price_cents=26320, channel="京东")
    d2 = _deal(session, n=41, title="始祖鸟 Beta AR", price_cents=19900, channel="拼多多")
    w = _watch(session, keywords=["Beta AR"], platforms=["京东", "天猫"])
    result = check_watch(session, w, [d1, d2], now=NOW)
    assert result["matched"] == 1 and result["min_price_cents"] == 26320
    session.commit()


def test_check_all_watches_aggregates(session: Session):
    _deal(session, n=50, title="始祖鸟 Beta AR 男款", price_cents=26320)
    w1 = _watch(session, name="鸟", keywords=["Beta AR"], target=30000)
    w2 = _watch(session, name="没人买的词", keywords=["不存在"], target=1)
    result = check_all_watches(session, now=NOW)
    assert result["checked"] == 2 and result["triggered"] == 1
    by_name = {r["name"]: r for r in result["results"]}
    assert by_name["鸟"]["watch_id"] == w1.id
    assert by_name["鸟"]["triggered"] and by_name["没人买的词"]["triggered"] == []
    assert by_name["没人买的词"]["watch_id"] == w2.id


def test_watch_api(client):
    created = client.post(
        "/api/watch",
        json={
            "name": "Beta AR 男款",
            "keywords": ["Beta AR"],
            "target_price": 300,  # 元 → 30000 分
            "qty": 1,
        },
    )
    assert created.status_code == 200, created.text
    watch_id = created.json()["id"]
    assert created.json()["target_price_cents"] == 30000

    listed = client.get("/api/watch").json()
    assert any(w["id"] == watch_id for w in listed)

    # 造一条命中线报：直接写测试库
    from sqlmodel import Session as _Session

    engine = client.app.state.db_engine
    with _Session(engine) as s:
        _deal(s, n=60, title="始祖鸟 Beta AR 男款 冲锋衣", price_cents=26320)
        s.commit()

    check = client.post("/api/watch/check").json()
    assert check["triggered"] == 1, check

    alerts = client.get(f"/api/watch/{watch_id}/alerts").json()
    assert len(alerts) == 1
    assert alerts[0]["kind"] == "target_hit"
    assert "¥300.00" in alerts[0]["reason"]
    assert alerts[0]["deal_title"] == "始祖鸟 Beta AR 男款 冲锋衣"

    # 编辑（改目标价）与暂停
    put = client.put(
        f"/api/watch/{watch_id}",
        json={"name": "Beta AR 男款", "keywords": ["Beta AR"], "target_price": 200},
    )
    assert put.status_code == 200 and put.json()["target_price_cents"] == 20000
    active = client.post(f"/api/watch/{watch_id}/active", params={"active": "false"})
    assert active.json()["active"] is False

    # 404 路径
    assert client.get("/api/watch/99999/alerts").status_code == 404
    deleted = client.delete(f"/api/watch/{watch_id}")
    assert deleted.status_code == 204
    assert client.get("/api/watch").json() == []
