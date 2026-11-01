"""关注列表检查：匹配站内线报，目标价/新低触发可解释的命中记录。

口径（第一阶段）：
- 匹配：keywords（空则用 name）任一命中 标题+摘要；must_words 须全部在标题中；
  exclude_words 命中任一即排除；platforms 非空时 deal.channel 须在列表内。
- 目标价：目标价>0 且最低线报 CNY 价 ≤ 目标价 → target_hit。
- 新低：本轮最低线报价 < 该关注历史已记录的最低价（WatchAlert）→ new_low；
  口径是「自开始记录以来」，首次检查没有历史，只记录不提醒。
- 去重：24h 内同关注同线报同类型不重复建记录。
- 币种：只有 CNY 线报参与目标价/新低比较；USD 线报计入命中数但不比价。
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlmodel import Session, select

from app.models import Deal, ProductWatch, WatchAlert
from app.util import load_json, utc_now

DEDUPE_HOURS = 24


def watch_keywords(watch: ProductWatch) -> list[str]:
    keywords = load_json(watch.keywords_json, [])
    return [str(k).strip() for k in keywords if str(k).strip()] or [watch.name.strip()]


def match_watch_deals(watch: ProductWatch, deals: list[Deal]) -> list[Deal]:
    """按关注条件过滤线报；不修改输入顺序。"""
    keywords = watch_keywords(watch)
    must = [str(w).strip() for w in load_json(watch.must_words_json, []) if str(w).strip()]
    exclude = [str(w).strip() for w in load_json(watch.exclude_words_json, []) if str(w).strip()]
    platforms = [str(p).strip() for p in load_json(watch.platforms_json, []) if str(p).strip()]
    out: list[Deal] = []
    for deal in deals:
        haystack = f"{deal.title} {deal.summary}"
        if not any(k in haystack for k in keywords):
            continue
        if not all(w in deal.title for w in must):
            continue
        if any(w in haystack for w in exclude):
            continue
        if platforms and not any(p in deal.channel for p in platforms):
            continue
        out.append(deal)
    return out


def _recent_alert(session: Session, watch_id: int, deal_id: int, kind: str, now: datetime) -> bool:
    since = now - timedelta(hours=DEDUPE_HOURS)
    return (
        session.exec(
            select(WatchAlert)
            .where(
                WatchAlert.watch_id == watch_id,
                WatchAlert.deal_id == deal_id,
                WatchAlert.kind == kind,
                WatchAlert.created_at >= since,  # type: ignore[union-attr]
            )
            .limit(1)
        ).first()
        is not None
    )


def _record(
    session: Session,
    watch: ProductWatch,
    deal: Deal,
    kind: str,
    price_cents: int,
    reason: str,
    now: datetime,
) -> WatchAlert:
    alert = WatchAlert(
        watch_id=watch.id,  # type: ignore[arg-type]
        deal_id=deal.id,  # type: ignore[arg-type]
        kind=kind,
        price_cents=price_cents,
        reason=reason,
        created_at=now,
    )
    session.add(alert)
    session.flush()
    return alert


def check_watch(
    session: Session,
    watch: ProductWatch,
    deals: list[Deal],
    *,
    now: datetime | None = None,
) -> dict:
    """检查一个关注；返回命中数、最低价与触发记录。不 commit（调用方统一提交）。"""
    now = now or utc_now()
    matched = match_watch_deals(watch, deals)
    cny = [d for d in matched if d.currency == "CNY" and d.price_cents > 0 and not d.expired]
    usd_count = sum(1 for d in matched if d.currency != "CNY" and d.price_cents > 0)
    best = min(cny, key=lambda d: d.price_cents) if cny else None
    low_before = watch.last_low_price_cents or None  # 自开始记录以来的最低线报价
    triggered: list[dict] = []
    if best is not None:
        when = (best.published_at or best.created_at).strftime("%m-%d %H:%M")
        price = f"¥{best.price_cents / 100:.2f}"
        if watch.target_price_cents > 0 and best.price_cents <= watch.target_price_cents:
            target = f"¥{watch.target_price_cents / 100:.2f}"
            if not _recent_alert(session, watch.id, best.id, "target_hit", now):
                reason = f"线报价 {price} ≤ 目标 {target}（{best.channel}、{when} 发布）"
                alert = _record(session, watch, best, "target_hit", best.price_cents, reason, now)
                triggered.append(
                    {"id": alert.id, "kind": "target_hit", "deal_id": best.id, "reason": reason}
                )
        if low_before is not None and best.price_cents < low_before:
            low = f"¥{low_before / 100:.2f}"
            if not _recent_alert(session, watch.id, best.id, "new_low", now):
                reason = f"新低 {price}（此前最低 {low}、{best.channel}、{when} 发布）"
                alert = _record(session, watch, best, "new_low", best.price_cents, reason, now)
                triggered.append(
                    {"id": alert.id, "kind": "new_low", "deal_id": best.id, "reason": reason}
                )
        if low_before is None or best.price_cents < low_before:
            watch.last_low_price_cents = best.price_cents
    # 一句话结果：给列表页看
    if best is None:
        result = f"命中 {len(matched)} 条，暂无可比的人民币线报价" + (
            f"（USD {usd_count} 条未比价）" if usd_count else ""
        )
    else:
        result = f"命中 {len(matched)} 条，最低线报价 {price}（{best.channel}）"
    watch.last_checked_at = now
    watch.last_result = result
    session.add(watch)
    return {
        "watch_id": watch.id,  # type: ignore[arg-type]
        "name": watch.name,
        "matched": len(matched),
        "min_price_cents": best.price_cents if best else None,
        "previous_low_cents": low_before,
        "usd_count": usd_count,
        "triggered": triggered,
        "last_result": result,
    }


def check_all_watches(session: Session, *, now: datetime | None = None) -> dict:
    """检查全部激活关注（对站内已有线报，不发外部请求）。"""
    now = now or utc_now()
    deals = list(session.exec(select(Deal)).all())
    watches = session.exec(select(ProductWatch).where(ProductWatch.active)).all()
    results = [check_watch(session, watch, deals, now=now) for watch in watches]
    session.commit()
    return {
        "checked": len(results),
        "triggered": sum(len(r["triggered"]) for r in results),
        "results": results,
    }


def send_pending_watch_alerts(session: Session, *, now: datetime | None = None) -> dict:
    """外发未发送的关注提醒；业务通知须显式启用（与 send_pending_alerts 同口径）。"""
    from app.alerts import send_alert

    now = now or utc_now()
    events = session.exec(
        select(WatchAlert).where(WatchAlert.sent_at.is_(None)).order_by(WatchAlert.id.asc())
    ).all()
    sent = failed = 0
    for event in events:
        deal = session.get(Deal, event.deal_id)
        if deal is None:
            event.send_error = "线报已不存在"
            failed += 1
            session.add(event)
            continue
        ok, err = send_alert(
            {
                "kind": f"关注·{event.kind}",
                "title": deal.title,
                "price_cents": event.price_cents,
                "url": deal.url,
            }
        )
        if ok:
            event.sent_at = now
            event.send_error = ""
            sent += 1
        else:
            event.send_error = err or "发送失败"
            failed += 1
        session.add(event)
    session.commit()
    return {"sent": sent, "failed": failed}
