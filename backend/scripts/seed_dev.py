"""开发库种子：灌入演示数据，供本地前后端联调。

用法：cd backend && uv run python scripts/seed_dev.py
默认写 var/outdoordeal.db（DB_PATH 可覆盖）。
"""

from __future__ import annotations

import sys
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlmodel import Session  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_engine, init_db  # noqa: E402
from app.models import RawListing  # noqa: E402
from app.storage import (  # noqa: E402
    add_price_snapshot,
    get_or_create_brand,
    get_or_create_channel,
    get_or_create_style,
    get_or_create_variant,
    save_raw_listing,
)
from app.util import utc_now  # noqa: E402


def raw(source: str, slug: str, ext: str, title: str, price: int, url: str) -> RawListing:
    return RawListing(
        source=source,
        channel_slug=slug,
        external_id=ext,
        url=url,
        title=title,
        price_cents=price,
    )


def seed() -> None:
    settings = get_settings()
    engine = get_engine(settings.db_path)
    init_db(engine)
    with Session(engine) as session:
        arcteryx = get_or_create_brand(session, "arcteryx", "Arc'teryx", name_cn="始祖鸟")
        tnf = get_or_create_brand(session, "the-north-face", "The North Face", name_cn="北面")

        beta = get_or_create_style(session, arcteryx.id, "27910",
                                   name="Beta LT 夹克", category="硬壳")
        torrent = get_or_create_style(session, arcteryx.id, "195871510",
                                      name="Torrentshell 3L 雨衣", category="雨壳")
        puffer = get_or_create_style(session, tnf.id, "NF0A3VU7",
                                     name="1996 复刻羽绒服", category="羽绒服")

        v1 = get_or_create_variant(session, beta.id, "Black", "M")
        v2 = get_or_create_variant(session, torrent.id, "Silt Green", "L")
        v3 = get_or_create_variant(session, puffer.id, "TNF Black", "L")

        jd = get_or_create_channel(session, "jd", kind="jd_union", name="京东")
        tb = get_or_create_channel(session, "taobao", kind="tbk", name="淘宝")
        us = get_or_create_channel(session, "official-us", kind="official_us",
                                   name="美国官网", currency="USD", country="US")

        now = utc_now()

        def history(listing_id: int, start: int, steps: list[int]) -> None:
            add_price_snapshot(session, listing_id=listing_id, price_cents=start,
                               ts=now - timedelta(days=80))
            for i, price in enumerate(steps):
                add_price_snapshot(session, listing_id=listing_id, price_cents=price,
                                   ts=now - timedelta(days=70 - i * 14))

        l1, _ = save_raw_listing(session, raw=raw("jd_union", "jd", "100012345",
                                              "始祖鸟 Arc'teryx Beta LT 夹克 27910 黑色 M", 399800,
                                              "https://item.jd.com/100012345.html"),
                                 channel_id=jd.id, variant_id=v1.id)
        history(l1.id, 469800, [449800, 429800, 399800])

        l2, _ = save_raw_listing(session, raw=raw("tbk", "taobao", "tao-27910",
                                              "Arc'teryx Beta LT 硬壳 黑 M", 389900,
                                              "https://detail.tmall.com/item.htm?id=1"),
                                 channel_id=tb.id, variant_id=v1.id)
        history(l2.id, 459900, [429900, 409900, 389900])

        l3, _ = save_raw_listing(session, raw=raw("web_product", "official-us", "27910",
                                              "Arc'teryx Beta LT Jacket - Black, M", 59900,
                                              "https://arcteryx.com/shop/beta-lt"),
                                 channel_id=us.id, variant_id=v1.id)
        history(l3.id, 59900, [54900, 49900, 44900])

        l4, _ = save_raw_listing(session, raw=raw("jd_union", "jd", "100077001",
                                              "始祖鸟 Torrentshell 3L 雨衣 淤泥绿 L", 289000,
                                              "https://item.jd.com/100077001.html"),
                                 channel_id=jd.id, variant_id=v2.id)
        history(l4.id, 329000, [309000, 299000, 289000])

        l5, _ = save_raw_listing(session, raw=raw("jd_union", "jd", "100098765",
                                              "北面 1996 复刻 Nuptse 羽绒服 黑 L", 289800,
                                              "https://item.jd.com/100098765.html"),
                                 channel_id=jd.id, variant_id=v3.id)
        history(l5.id, 329800, [319800, 299800, 289800])

        session.commit()
        print(f"seeded {settings.db_path}: 2 brands, 3 styles, 3 variants, 5 listings")


if __name__ == "__main__":
    seed()
