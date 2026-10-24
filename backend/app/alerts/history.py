"""价格历史判断：新低检测 + 历史不足豁免（M4）。

规则（PRD §7）：
- 新低 = 当前价 < 窗口内（默认 90 天）此前最低价；
- 历史不足 14 天不报新低（避免上架即"新低"的误报）；
- 同类事件 24h 去重在 alerts/service.py 的 recent_alert 判断。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import AlertEvent, AlertSubscription, Listing, PriceSnapshot
from app.util import dump_json, load_json, utc_now

MIN_HISTORY_DAYS = 14
DEFAULT_WINDOW_DAYS = 90
DEDUPE_HOURS = 24


def first_snapshot_ts(session: Session, listing_id: int) -> datetime | None:
    snap = session.exec(
        select(PriceSnapshot)
        .where(PriceSnapshot.listing_id == listing_id)
        .order_by(PriceSnapshot.ts.asc())  # type: ignore[union-attr]
        .limit(1)
    ).first()
    return snap.ts if snap else None


def is_new_low(
    session: Session,
    listing_id: int,
    price_cents: int,
    *,
    window_days: int = DEFAULT_WINDOW_DAYS,
    min_history_days: int = MIN_HISTORY_DAYS,
    now: datetime | None = None,
    before: datetime | None = None,
) -> bool:
    """当前价是否为窗口内新低。历史不足 min_history_days 天直接 False。

    before：当前这条快照自身的写入时刻。给了就以它为窗口上界（ts < before），
    只跟「此前」的价格比；不给则退回 ts < now。采集流程是先写快照再评估，
    若不传 before，刚写入的当前价会落进比较窗口，min 里含自己，新低永远判不出。
    """
    now = now or utc_now()
    first_ts = first_snapshot_ts(session, listing_id)
    if first_ts is None or (now - first_ts).days < min_history_days:
        return False
    bound = before if before is not None else now
    from app.storage import lowest_price

    previous_low = lowest_price(session, listing_id, days=window_days, before=bound)
    return previous_low is not None and price_cents < previous_low


def recent_alert(
    session: Session,
    subscription_id: int,
    kind: str,
    *,
    hours: int = DEDUPE_HOURS,
    now: datetime | None = None,
) -> bool:
    """同订阅同类型事件在 hours 小时内是否已发过（24h 去重）。"""
    now = now or utc_now()
    since = now - timedelta(hours=hours)
    event = session.exec(
        select(AlertEvent)
        .where(
            AlertEvent.subscription_id == subscription_id,
            AlertEvent.kind == kind,
            AlertEvent.created_at >= since,
        )
        .limit(1)
    ).first()
    return event is not None


def create_alert_event(
    session: Session,
    *,
    subscription_id: int,
    variant_id: int,
    kind: str,
    payload: dict,
    now: datetime | None = None,
) -> AlertEvent:
    event = AlertEvent(
        subscription_id=subscription_id,
        variant_id=variant_id,
        kind=kind,
        payload_json=dump_json(payload),
        created_at=now or utc_now(),
    )
    session.add(event)
    session.flush()
    return event


def evaluate_listing(
    session: Session,
    listing: Listing,
    price_cents: int,
    *,
    now: datetime | None = None,
    current_ts: datetime | None = None,
    previous_in_stock: bool | None = None,
) -> list[AlertEvent]:
    """对一个 listing 当前价评估所有相关订阅，生成（未去重前的）告警事件。

    订阅通过 variant_id 关联；kinds_json 里含 "price_below" 才判目标价，
    含 "new_low" 才判新低（且受历史≥14 天约束）。
    current_ts：当前这条价格的快照时刻，传给 is_new_low 排除自身（见其 docstring）。
    """
    now = now or utc_now()
    if listing.variant_id is None or not listing.active:
        return []
    subs = session.exec(
        select(AlertSubscription).where(
            AlertSubscription.variant_id == listing.variant_id, AlertSubscription.active
        )
    ).all()
    events: list[AlertEvent] = []
    for sub in subs:
        kinds = load_json(sub.kinds_json, [])
        if (
            "price_below" in kinds
            and sub.target_price_cents is not None
            and price_cents <= sub.target_price_cents
        ):
            if not recent_alert(session, sub.id, "price_below", now=now):
                events.append(
                    create_alert_event(
                        session,
                        subscription_id=sub.id,
                        variant_id=sub.variant_id,
                        kind="price_below",
                        payload={
                            "listing_id": listing.id,
                            "price_cents": price_cents,
                            "target_price_cents": sub.target_price_cents,
                            "url": listing.url,
                            "title": listing.title,
                        },
                        now=now,
                    )
                )
        if "new_low" in kinds and is_new_low(
            session, listing.id, price_cents, now=now, before=current_ts
        ):
            if not recent_alert(session, sub.id, "new_low", now=now):
                events.append(
                    create_alert_event(
                        session,
                        subscription_id=sub.id,
                        variant_id=sub.variant_id,
                        kind="new_low",
                        payload={
                            "listing_id": listing.id,
                            "price_cents": price_cents,
                            "url": listing.url,
                            "title": listing.title,
                        },
                        now=now,
                    )
                )
        if "restock" in kinds and previous_in_stock is False:
            if not recent_alert(session, sub.id, "restock", now=now):
                events.append(
                    create_alert_event(
                        session,
                        subscription_id=sub.id,
                        variant_id=sub.variant_id,
                        kind="restock",
                        payload={
                            "listing_id": listing.id,
                            "price_cents": price_cents,
                            "url": listing.url,
                            "title": listing.title,
                        },
                        now=now,
                    )
                )
    return events


def validate_alert_event(
    session: Session, event: AlertEvent, *, now: datetime | None = None
) -> tuple[dict | None, str]:
    """排队或重发事件在发出前必须仍然成立；返回当前价，不沿用旧价格。"""
    from app.offers import channel_quotes, current_cny_quotes
    from app.storage import last_snapshot

    now = now or utc_now()
    sub = session.get(AlertSubscription, event.subscription_id)
    if not sub or not sub.active or event.kind not in load_json(sub.kinds_json, []):
        return None, "订阅已取消或不再包含该提醒类型"
    if event.created_at < now - timedelta(hours=24):
        return None, "提醒已超过24小时，请以当前报价为准"
    original = load_json(event.payload_json, {})
    offers = current_cny_quotes(channel_quotes(session, sub.variant_id))
    offer = next((row for row in offers if row["listing_id"] == original.get("listing_id")), None)
    if offer is None:
        return None, "渠道已停用、报价待复核或当前库存不可确认"
    price = offer["effective_cents"]
    if event.kind == "price_below" and (
        sub.target_price_cents is None or price > sub.target_price_cents
    ):
        return None, "当前到手价已超过目标价"
    if event.kind == "new_low":
        snap = last_snapshot(session, offer["listing_id"])
        if not snap or not is_new_low(session, offer["listing_id"], price, now=now, before=snap.ts):
            return None, "当前到手价已不满足历史新低条件"
    return {
        **original,
        "kind": event.kind,
        "price_cents": price,
        "target_price_cents": sub.target_price_cents,
        "url": offer["url"],
        "title": offer["title"],
    }, ""
