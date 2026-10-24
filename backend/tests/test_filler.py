"""凑单 0-1 背包测试。"""

from __future__ import annotations

from app.pricing import FillerItem, best_filler


def item(i: str, cents: int) -> FillerItem:
    return FillerItem(id=i, name=f"凑单品 {i}", price_cents=cents)


class TestBestFiller:
    def test_exact_threshold(self):
        # 手算：门槛 3000，候选 1000/1500/800/2000。
        # 可行子集：{a,d}=3000(恰达标)、{b,d}=3500、{a,b,d}=4500 …
        # 最少多花 → 3000，选 [a,d]
        items = [item("a", 100000), item("b", 150000), item("c", 80000), item("d", 200000)]
        chosen = best_filler(300000, items)
        assert chosen is not None
        assert sum(x.price_cents for x in chosen) == 300000
        assert {x.id for x in chosen} == {"a", "d"}

    def test_zero_threshold_needs_nothing(self):
        # 门槛 0 → 空列表（什么都不用凑）
        assert best_filler(0, [item("a", 1000)]) == []

    def test_unreachable_returns_none(self):
        # 手算：门槛 5000，只有 1000 的候选，怎么凑都够不到 → None（提示凑单无解）
        assert best_filler(500000, [item("a", 100000)]) is None

    def test_prefers_cheap_overflow(self):
        # 手算：门槛 1000，候选 999/1001/1200 → 1001 恰超 1 块，最优
        items = [item("x", 99900), item("y", 100100), item("z", 120000)]
        chosen = best_filler(100000, items)
        assert chosen is not None
        assert {c.id for c in chosen} == {"y"}
