"""采集、到手价历史与提醒调度。持久化任务使用模块函数，重启可恢复。"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

from app.alerts import evaluate_listing, send_alert
from app.config import get_settings
from app.db import get_engine
from app.models import AlertEvent, AlertSubscription, Channel, Listing, RawListing
from app.storage import add_price_snapshot, last_snapshot, save_raw_listing, sync_listing_coupons
from app.util import to_naive_utc, utc_now

logger = logging.getLogger(__name__)
CollectorFactory = Callable[[], object]
_SESSION_FACTORIES: dict[str, Callable[[], Session]] = {}


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
    session: Session, raws: Iterable[RawListing], *, channel_id: int
) -> IngestResult:
    """严格匹配→专属券→到手价→变化快照→每轮评估；单条用保存点隔离。"""
    from app.ingestion import resolve_variant
    from app.offers import listing_fresh
    from app.pricing.quotes import quote_listing
    from app.storage import get_or_create_channel

    result = IngestResult()
    for raw in raws:
        try:
            with session.begin_nested():
                target_channel = session.get(Channel, channel_id)
                if raw.source == "avantlink" and raw.merchant:
                    target_channel = get_or_create_channel(
                        session,
                        raw.channel_slug,
                        kind="avantlink",
                        name=raw.merchant,
                        currency=raw.currency,
                        country="US",
                    )
                if target_channel is None:
                    raise ValueError("采集渠道不存在")
                if not target_channel.active:
                    raise ValueError("采集渠道已停用")
                variant_id = resolve_variant(session, raw)
                listing, _ = save_raw_listing(
                    session, raw=raw, channel_id=target_channel.id, variant_id=variant_id
                )
                previous = last_snapshot(session, listing.id)
                sync_listing_coupons(session, listing, raw.coupons)
                ts = to_naive_utc(raw.collected_at)
                quote = quote_listing(session, listing, base_price_cents=raw.price_cents, now=ts)
                snap = add_price_snapshot(
                    session,
                    listing_id=listing.id,
                    price_cents=raw.price_cents,
                    currency=raw.currency,
                    in_stock=raw.in_stock,
                    stock_verified=raw.stock_verified,
                    ts=ts,
                    paid_now_cents=quote.paid_now_cents,
                    rebate_cents=quote.rebate_cents,
                    effective_cents=quote.effective_cents,
                )
                alerts = []
                if (
                    raw.stock_verified
                    and raw.in_stock
                    and raw.currency == "CNY"
                    and listing_fresh(listing)
                ):
                    alerts = evaluate_listing(
                        session,
                        listing,
                        quote.effective_cents,
                        current_ts=ts,
                        previous_in_stock=(
                            previous.in_stock if previous and previous.stock_verified else None
                        ),
                    )
            result.saved += 1
            result.new_snapshots += int(snap is not None)
            result.alerts.extend(alerts)
        except Exception as exc:  # 单条回滚不会撤销同批成功商品
            result.errors.append(f"{raw.external_id}: {exc}")
    session.commit()
    return result


def run_collection(
    session: Session,
    *,
    source: str,
    keywords: str,
    channel_id: int | None = None,
    collector_factory: CollectorFactory | None = None,
    collect_kwargs: dict | None = None,
) -> dict:
    from app.collectors import AvantLinkCollector, JDUnionCollector, TaobaoKeCollector
    from app.storage import get_or_create_channel

    factories = {
        "jd_union": JDUnionCollector,
        "tbk": TaobaoKeCollector,
        "avantlink": AvantLinkCollector,
    }
    factory = collector_factory or factories.get(source)
    if factory is None:
        return {"ok": False, "error": f"未知采集源: {source}"}
    collector = None
    try:
        collector = factory()
        # 生成器错误也必须属于采集失败，不能在try外延迟触发。
        raws = list(collector.collect(keywords, **(collect_kwargs or {})))
    except Exception as exc:
        logger.warning("采集源 %s 失败: %s", source, exc)
        return {"ok": False, "error": f"采集失败: {exc}"}
    finally:
        close = getattr(collector, "close", None)
        if close:
            close()
    if channel_id is None:
        slug, name = {
            "jd_union": ("jd", "京东"),
            "tbk": ("taobao", "淘宝"),
            "avantlink": ("avantlink", "AvantLink"),
        }[source]
        channel = get_or_create_channel(
            session,
            slug,
            kind=source,
            name=name,
            currency="USD" if source == "avantlink" else "CNY",
            country="US" if source == "avantlink" else "CN",
        )
        channel_id = channel.id
    result = collect_and_store(session, raws, channel_id=channel_id)
    return {"ok": not result.errors, **result.as_dict(), "count": len(raws)}


def refresh_quotes(session: Session) -> dict:
    """无新标价时也重算有效优惠，捕捉券变化并评估新增订阅。"""
    from app.offers import listing_fresh
    from app.pricing.quotes import quote_listing

    evaluated = snapshots = 0
    for listing in session.exec(select(Listing).where(Listing.active)).all():
        snap = last_snapshot(session, listing.id)
        channel = session.get(Channel, listing.channel_id)
        if (
            not snap
            or not snap.stock_verified
            or not snap.in_stock
            or not channel
            or not channel.active
        ):
            continue
        if snap.currency != "CNY" or not listing_fresh(listing):
            continue
        now = utc_now()
        quote = quote_listing(session, listing, now=now)
        changed = add_price_snapshot(
            session,
            listing_id=listing.id,
            price_cents=snap.price_cents,
            currency=snap.currency,
            in_stock=snap.in_stock,
            ts=now,
            paid_now_cents=quote.paid_now_cents,
            rebate_cents=quote.rebate_cents,
            effective_cents=quote.effective_cents,
        )
        evaluate_listing(session, listing, quote.effective_cents, now=now, current_ts=now)
        evaluated += 1
        snapshots += int(changed is not None)
    session.commit()
    return {"evaluated": evaluated, "snapshots": snapshots}


def send_pending_alerts(session: Session, *, now: datetime | None = None) -> dict:
    """仅发送仍有效订阅的未发送事件；业务通知须显式启用。"""
    now = now or utc_now()
    events = session.exec(select(AlertEvent).where(AlertEvent.sent_at.is_(None))).all()
    from app.alerts.history import validate_alert_event

    sent = failed = skipped = 0
    for event in events:
        sub = session.get(AlertSubscription, event.subscription_id)
        payload, reason = validate_alert_event(session, event, now=now)
        if payload is None:
            event.send_error = reason
            session.add(event)
            skipped += 1
            continue
        ok, err = send_alert(payload, destination=sub.destination)
        if ok:
            event.sent_at = now
            event.send_error = ""
            sent += 1
        else:
            event.send_error = err or "发送失败"
            failed += 1
        session.add(event)
    session.commit()
    return {"sent": sent, "failed": failed, "skipped": skipped}


def ingest_smzdm_deals(
    session: Session,
    *,
    max_details: int = 20,
    collector_factory: Callable[[], object] | None = None,
) -> dict:
    from app.collectors.smzdm import SmzdmFeedCollector, parse_deal_page
    from app.deals import ingest_deals, known_source_ids, max_source_id, reports_due_for_recheck

    factory = collector_factory or (lambda: SmzdmFeedCollector(max_details_per_run=max_details))
    collector = factory()
    try:
        drafts = []
        # 限额内分配少量旧详情复核，旧优惠离开分类页后也不会永久跳过。
        fetch_page = getattr(collector, "fetch_page", None)
        if fetch_page:
            for deal in reports_due_for_recheck(session, limit=min(2, max_details)):
                try:
                    drafts.append(parse_deal_page(fetch_page(deal.url), deal.url))
                except Exception as exc:
                    logger.warning("线报复核失败 %s: %s", deal.source_id, exc)
        remaining = max_details - len(drafts)
        collect = getattr(collector, "collect_categories", None)
        if remaining and collect is not None:
            exclude = known_source_ids(session, fresh_only=True) | {d.source_id for d in drafts}
            drafts.extend(collect(exclude_ids=exclude, limit=remaining))
        elif remaining:
            drafts.extend(collector.collect(max_source_id(session), limit=remaining))
    except Exception as exc:
        logger.warning("线报采集失败: %s", exc)
        return {"ok": False, "error": f"线报采集失败: {exc}"}
    finally:
        close = getattr(collector, "close", None)
        if close:
            close()
    result = ingest_deals(session, drafts)
    return {"ok": not result["errors"], **result}


def configured_collection_specs() -> list[dict]:
    settings = get_settings()
    if settings.collection_specs:
        return settings.collection_specs
    sources = []
    if settings.jd_union_app_key and settings.jd_union_secret_key:
        sources.append("jd_union")
    if settings.taobao_app_key and settings.taobao_app_secret and settings.taobao_pid:
        sources.append("tbk")
    if settings.avantlink_affiliate_id and settings.avantlink_website_id:
        sources.append("avantlink")
    return [
        {"source": source, "keywords": word}
        for source in sources
        for word in settings.collection_keywords
    ]


def _default_session() -> Session:
    return Session(get_engine())


def _job_session(db_path: str, runtime_key: str) -> Session:
    factory = _SESSION_FACTORIES.get(runtime_key)
    return factory() if factory else Session(get_engine(Path(db_path)))


def collection_job(db_path: str, runtime_key: str = "", specs: list[dict] | None = None) -> None:
    with _job_session(db_path, runtime_key) as session:
        for spec in specs if specs is not None else configured_collection_specs():
            result = run_collection(session, **spec)
            if not result.get("ok"):
                logger.warning("渠道更新失败: %s", result)


def alert_job(db_path: str, runtime_key: str = "") -> None:
    with _job_session(db_path, runtime_key) as session:
        refresh_quotes(session)
        if get_settings().notifications_enabled:
            send_pending_alerts(session)


def deals_job(db_path: str, runtime_key: str = "") -> None:
    with _job_session(db_path, runtime_key) as session:
        result = ingest_smzdm_deals(session, max_details=get_settings().ingest_deals_max_details)
        if not result.get("ok"):
            logger.warning("线报更新失败: %s", result)


def build_scheduler(
    *,
    session_factory: Callable[[], Session] = _default_session,
    collect_specs: list[dict] | None = None,
    collect_interval_minutes: int = 30,
    alert_interval_seconds: int = 300,
    ingest_deals_interval_minutes: int = 30,
    start_now: bool = True,
):
    from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
    from apscheduler.schedulers.background import BackgroundScheduler

    settings = get_settings()
    runtime_key = ""
    if session_factory is not _default_session:
        runtime_key = uuid4().hex
        _SESSION_FACTORIES[runtime_key] = session_factory
    scheduler = BackgroundScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=settings.sqlite_url)},
        timezone="UTC",
        job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120},
    )
    shared = {"db_path": str(settings.db_path), "runtime_key": runtime_key}
    scheduler.add_job(
        collection_job,
        "interval",
        minutes=collect_interval_minutes,
        kwargs={**shared, "specs": collect_specs},
        id="collect",
        replace_existing=True,
    )
    scheduler.add_job(
        alert_job,
        "interval",
        seconds=alert_interval_seconds,
        kwargs=shared,
        id="send_alerts",
        replace_existing=True,
    )
    scheduler.add_job(
        deals_job,
        "interval",
        minutes=ingest_deals_interval_minutes,
        kwargs=shared,
        id="ingest_deals",
        replace_existing=True,
    )
    if start_now:
        scheduler.start()
    return scheduler
