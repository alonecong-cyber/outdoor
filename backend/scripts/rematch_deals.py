"""重匹配存量线报到商品目录。

品牌词典/款号正则升级后，对 matched_variant_id 为空的 Deal 重跑 grow_variant；
对早期价格解析失败（price_cents=0 但标题带价格尾巴）的 Deal 用当前正则重提价格。
用法：uv run python scripts/rematch_deals.py
"""

from __future__ import annotations

import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.collectors.smzdm import PRICE_TAIL_RE  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.deals import content_hash, grow_variant  # noqa: E402
from app.models import Deal, DealDraft  # noqa: E402


def rematch_variants(session: Session) -> tuple[int, int]:
    """未匹配线报重挂 Variant。返回 (待匹配数, 新挂上数)。"""
    deals = session.exec(
        select(Deal).where(Deal.matched_variant_id.is_(None))  # type: ignore[union-attr]
    ).all()
    matched = 0
    for deal in deals:
        variant_id = grow_variant(session, deal.title)
        if variant_id is not None:
            deal.matched_variant_id = variant_id
            matched += 1
    return len(deals), matched


def reprice_zero(session: Session) -> int:
    """price_cents=0 但标题尾巴其实有价格的，重提价格（如 "1648元返200积分后"）。"""
    fixed = 0
    for deal in session.exec(select(Deal).where(Deal.price_cents == 0)).all():
        m = PRICE_TAIL_RE.search(deal.title.strip())
        if not m:
            continue
        cents = int((Decimal(m.group(2)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        deal.title = m.group(1).strip()
        deal.price_cents = cents
        deal.content_hash = content_hash(
            DealDraft(
                source=deal.source,
                source_id=deal.source_id,
                url=deal.url,
                title=deal.title,
                price_cents=cents,
                currency=deal.currency,
                channel=deal.channel,
            )
        )
        fixed += 1
    return fixed


def main() -> None:
    engine = get_engine(get_settings().db_path)
    init_db(engine)
    with Session(engine) as session:
        pending, matched = rematch_variants(session)
        repriced = reprice_zero(session)
        session.commit()
        total = len(session.exec(select(Deal)).all())
        print(
            f"待匹配 {pending} 条 → 新挂上 {matched} 条；补提价格 {repriced} 条；Deal 总数 {total}"
        )


if __name__ == "__main__":
    main()
