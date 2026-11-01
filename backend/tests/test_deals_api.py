"""线报流 API：GET /api/deals、POST /api/deals/ingest（注入假采集器）。"""

from __future__ import annotations

from sqlmodel import Session

from app.deals import ingest_deals, save_deal
from app.main import app
from app.models import DealDraft


class _FakeCollector:
    """离线假 smzdm 采集器：返回 fixture 详情页解析结果。"""

    def __init__(self, drafts):
        self.drafts = drafts

    def collect(self, since_id=0, *, limit=None):
        return self.drafts

    def collect_categories(self, slugs=None, *, exclude_ids=None, limit=None):
        return self.drafts

    def close(self):
        pass


def _draft(source_id: str, title: str, price: int, channel: str) -> DealDraft:
    return DealDraft(
        source_id=source_id,
        url=f"https://www.smzdm.com/p/{source_id}/",
        title=title,
        price_cents=price,
        channel=channel,
    )


def test_deals_feed_order_and_shape(client, session):
    ingest_deals(
        session,
        [
            _draft("300", "始祖鸟 Beta LT 硬壳夹克 男款 27910 黑色 M 3998元", 399800, "淘宝"),
            _draft("301", "蒂佳婷 蓝色药丸补水面膜 5片 100元", 10000, "京东"),
        ],
    )
    session.commit()  # API 走独立 session，先落盘
    resp = client.get("/api/deals")
    assert resp.status_code == 200
    deals = resp.json()
    assert len(deals) == 2
    # 新→旧
    assert deals[0]["source_id"] == "301"
    d = deals[1]
    assert d["title"] == "始祖鸟 Beta LT 硬壳夹克 男款 27910 黑色 M 3998元"
    assert d["price_cents"] == 399800
    assert d["channel"] == "淘宝"
    assert d["variant"] is not None
    assert d["variant"]["brand_slug"] == "arcteryx"
    assert d["variant"]["color"] == "black"
    # 未匹配线报 variant 为 null
    assert deals[0]["variant"] is None


def test_deals_feed_filters(client, session):
    ingest_deals(
        session,
        [
            _draft("310", "始祖鸟 Beta LT 硬壳夹克 男款 27910 黑色 M 3998元", 399800, "淘宝"),
            _draft("311", "北面 1996 复刻羽绒服 NF0A3VU7 黑色 L 2898元", 289800, "京东"),
            _draft("312", "蒂佳婷 面膜 5片 100元", 10000, "京东"),
        ],
    )
    session.commit()
    # q 过滤
    deals = client.get("/api/deals", params={"q": "面膜"}).json()
    assert [d["source_id"] for d in deals] == ["312"]
    # brand 过滤只留已匹配该品牌的
    deals = client.get("/api/deals", params={"brand": "arcteryx"}).json()
    assert [d["source_id"] for d in deals] == ["310"]
    assert deals[0]["variant"]["brand_slug"] == "arcteryx"


def test_deals_ingest_endpoint_with_injected_collector(client):
    drafts = [
        _draft("320", "始祖鸟 Gamma LT 软壳衣 男款 26994 黑色 L 3299元", 329900, "京东"),
        _draft("321", "蒂佳婷 面膜 100元", 10000, "京东"),
    ]
    app.state.smzdm_collector_factory = lambda: _FakeCollector(drafts)
    try:
        resp = client.post("/api/deals/ingest", params={"details": 5})
    finally:
        del app.state.smzdm_collector_factory
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] and body["saved"] == 2 and body["created"] == 2 and body["matched"] == 1
    # 再拉一轮：重复线报不新建
    app.state.smzdm_collector_factory = lambda: _FakeCollector(drafts)
    try:
        resp2 = client.post("/api/deals/ingest", params={"details": 5})
    finally:
        del app.state.smzdm_collector_factory
    assert resp2.json()["created"] == 0


def test_deals_ingest_failure_returns_502(client):
    class _Boom:
        def collect(self, *a, **k):
            raise RuntimeError("network down")

    app.state.smzdm_collector_factory = lambda: _Boom()
    try:
        resp = client.post("/api/deals/ingest")
    finally:
        del app.state.smzdm_collector_factory
    assert resp.status_code == 502
    assert "线报拉取失败" in resp.json()["detail"]


def test_deal_notes(client):
    app = client.app
    # 造一条线报
    drafts = [
        DealDraft(
            source="test",
            source_id="n1",
            url="https://x/1",
            title="始祖鸟 Beta AR 男款",
            price_cents=26320,
            currency="CNY",
            channel="京东",
        )
    ]
    with Session(app.state.db_engine) as s:
        save_deal(s, drafts[0])
        s.commit()
    deal_id = client.get("/api/deals").json()[0]["id"]

    assert client.get(f"/api/deals/{deal_id}/notes").json() == []
    created = client.post(f"/api/deals/{deal_id}/notes", json={"body": "等 88VIP 再买"})
    assert created.status_code == 200 and created.json()["body"] == "等 88VIP 再买"
    assert client.post(f"/api/deals/{deal_id}/notes", json={"body": "   "}).status_code == 400

    notes = client.get(f"/api/deals/{deal_id}/notes").json()
    assert len(notes) == 1
    note_id = notes[0]["id"]
    assert client.delete(f"/api/deals/{deal_id}/notes/{note_id}").status_code == 200
    assert client.get(f"/api/deals/{deal_id}/notes").json() == []
    # 404
    assert client.get("/api/deals/99999/notes").status_code == 404
