"""调度：采集入库 + 快照 + 告警评估 + 待发事件发送（APScheduler，SQLite jobstore）。

- collect_and_store：采集器 → Listing upsert → 变化才写快照 → 评估告警；
- send_pending_alerts：把未发送事件真正推出去（telegram/wecom/smtp）；
- build_scheduler：测试可注入 job 函数与 session 工厂；缺凭据的采集源跳过不炸。
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime

from sqlmodel import Session, select

from app.alerts import evaluate_listing, send_alert
from app.config import get_settings
from app.db import get_engine
from app.models import AlertEvent, AlertSubscription, RawListing
from app.storage import add_price_snapshot, save_raw_listing
from app.util import load_json, utc_now

CollectorFactory = Callable[[], object]


class IngestResult:
    def __init__(self) -> None:
        self.saved = 0
        self.new_snapshots = 0
        self.alerts: list[AlertEvent] = []
        self.errors: list[str] = []

    def as_dict(self) -> dict:
        return {
            "saved": self.saved,
            "new_snapshots": self.new_snapshots,
            "alerts": len(self.alerts),
            "errors": self.errors,
        }


def collect_and_store(
    session: Session,
    raws: Iterable[RawListing],
    *,
    channel_id: int,
) -> IngestResult:
    """把一批 RawListing 落库并评估告警。单个失败不拖垮整批。"""
    result = IngestResult()
    for raw in raws:
        try:
            listing, _created = save_raw_listing(
                session, raw=raw, channel_id=channel_id, variant_id=None
            )
            result.saved += 1
            snap = add_price_snapshot(
                session,
                listing_id=listing.id,
                price_cents=raw.price_cents,
                currency=raw.currency,
                in_stock=raw.in_stock,
                ts=raw.collected_at or None,
            )
            if snap is not None:
                result.new_snapshots += 1
                result.alerts.extend(
                    evaluate_listing(session, listing, raw.price_cents, current_ts=snap.ts)
                )
        except Exception as e:  # noqa: BLE001 - 单条失败记录后继续
            session.rollback()
            result.errors.append(f"{raw.external_id}: {e}")
    session.commit()
    return result


def run_collection(
    session: Session,
    *,
    source: str,
    keywords: str,
    channel_id: int,
    collector_factory: CollectorFactory | None = None,
    collect_kwargs: dict | None = None,
) -> dict:
    """执行一次采集。collector_factory 可注入（测试/未来扩展），source 仅为标识。"""
    if collector_factory is None:
        from app.collectors import AvantLinkCollector, JDUnionCollector, TaobaoKeCollector

        factories: dict[str, CollectorFactory] = {
            "jd_union": JDUnionCollector,
            "tbk": TaobaoKeCollector,
            "avantlink": AvantLinkCollector,
        }
        factory = factories.get(source)
        if factory is None:
            return {"ok": False, "error": f"未知采集源: {source}"}
        collector_factory = factory

    try:
        collector = collector_factory()
        raws = collector.collect(keywords) if source != "avantlink" else collector.collect(keywords)
    except PermissionError as e:
        return {"ok": False, "error": f"凭据缺失: {e}"}
    except Exception as e:  # noqa: BLE001 - 采集失败返回错误而不是炸调度器
        return {"ok": False, "error": f"采集失败: {e}"}

    raws = list(raws)
    result = collect_and_store(session, raws, channel_id=channel_id)
    out = {"ok": not result.errors, **result.as_dict(), "count": len(raws)}
    return out


def send_pending_alerts(session: Session, *, now: datetime | None = None) -> dict:
    """发送所有未发送事件。成功记 sent_at，失败记 send_error（下次再试）。"""
    now = now or utc_now()
    events = session.exec(
        select(AlertEvent).where(AlertEvent.sent_at.is_(None))  # type: ignore[union-attr]
    ).all()  # type: ignore[call-overload]
    sent, failed = 0, 0
    for event in events:
        sub = session.get(AlertSubscription, event.subscription_id)
        destination = sub.destination if sub else ""
        payload = load_json(event.payload_json, {})
        ok, err = send_alert(payload, destination=destination)
        if ok:
            event.sent_at = now
            event.send_error = None
            sent += 1
        else:
            event.send_error = err
            failed += 1
        session.add(event)
    session.commit()
    return {"sent": sent, "failed": failed}


def _default_session() -> Session:
    return Session(get_engine())


def build_scheduler(
    *,
    session_factory: Callable[[], Session] = _default_session,
    collect_specs: list[dict] | None = None,
    collect_interval_minutes: int = 30,
    alert_interval_seconds: int = 300,
    start_now: bool = True,
):
    """组装 APScheduler（SQLite jobstore）。生产由 main.py 启动，测试注入假 job。"""
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.background import BackgroundScheduler

    s = get_settings()
    jobstores = {"default": SQLAlchemyJobStore(url=s.sqlite_url)}
    scheduler = BackgroundScheduler(jobstores=jobstores, timezone="UTC")

    specs = collect_specs or []

    def _collect_job() -> None:
        with session_factory() as session:
            for spec in specs:
                run_collection(session, **spec)

    def _alert_job() -> None:
        with session_factory() as session:
            send_pending_alerts(session)

    scheduler.add_job(
        _collect_job,
        "interval",
        minutes=collect_interval_minutes,
        id="collect",
        replace_existing=True,
    )
    scheduler.add_job(
        _alert_job,
        "interval",
        seconds=alert_interval_seconds,
        id="send_alerts",
        replace_existing=True,
    )
    if start_now:
        scheduler.start()
    return scheduler
