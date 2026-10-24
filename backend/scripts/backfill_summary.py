"""给存量 Deal 回填 summary（og:description 优惠说明）。

存量线报入库早于 summary 字段，逐条重抓详情页（≥10s/请求）解析。
用法：uv run python scripts/backfill_summary.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session, select  # noqa: E402

from app.collectors.smzdm import SmzdmFeedCollector, parse_deal_page  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.models import Deal  # noqa: E402


def main() -> None:
    engine = get_engine(get_settings().db_path)
    init_db(engine)
    collector = SmzdmFeedCollector()
    try:
        with Session(engine) as session:
            deals = session.exec(
                select(Deal).where(Deal.summary == "")  # type: ignore[arg-type]
            ).all()
            todo = [d for d in deals if d.url]
            print(f"待回填 {len(todo)} 条（每条 ≥10s）…", flush=True)
            fixed = 0
            for i, deal in enumerate(todo, 1):
                try:
                    html = collector.fetch_page(deal.url)
                except Exception as e:  # noqa: BLE001 单条失败不中断
                    print(f"[{i}/{len(todo)}] {deal.source_id} 拉取失败: {e}", flush=True)
                    continue
                draft = parse_deal_page(html, deal.url)
                if draft.summary:
                    deal.summary = draft.summary
                    fixed += 1
                session.add(deal)
                session.commit()
                print(f"[{i}/{len(todo)}] {deal.source_id} ok", flush=True)
            print(f"回填完成：{fixed}/{len(todo)}")
    finally:
        collector.close()


if __name__ == "__main__":
    main()
