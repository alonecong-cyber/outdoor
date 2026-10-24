"""提醒订阅与事件 API。"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.alerts import send_alert
from app.api.deps import get_db
from app.models import AlertEvent, AlertSubscription, Variant
from app.util import dump_json, load_json

router = APIRouter(prefix="/alerts", tags=["alerts"])


class SubscriptionIn(BaseModel):
    variant_id: int
    target_price_cents: int = Field(default=0, ge=0)
    kinds: list[Literal["price_below", "new_low", "restock"]] = ["price_below"]
    destination: str = ""


class SubscriptionOut(BaseModel):
    id: int
    variant_id: int
    target_price_cents: int
    kinds: list[str]
    destination: str


@router.post("/subscriptions", response_model=SubscriptionOut)
def create_subscription(body: SubscriptionIn, db: Session = Depends(get_db)) -> SubscriptionOut:
    if db.get(Variant, body.variant_id) is None:
        raise HTTPException(404, "variant 不存在")
    from app.offers import channel_quotes, current_cny_quotes

    channels = channel_quotes(db, body.variant_id)
    eligible = current_cny_quotes(channels)
    if set(body.kinds) == {"restock"}:
        eligible = [
            row
            for row in channels
            if row["price_status"] == "verified"
            and row["currency"] == "CNY"
            and row["in_stock"] is not None
        ]
    if not eligible:
        raise HTTPException(409, "该规格暂无有效的人民币渠道报价，暂不能创建到手价提醒")
    if not body.kinds:
        raise HTTPException(422, "至少选择一种提醒类型")
    if "price_below" in body.kinds and body.target_price_cents <= 0:
        raise HTTPException(422, "目标到手价必须大于0")
    sub = AlertSubscription(
        variant_id=body.variant_id,
        target_price_cents=body.target_price_cents,
        kinds_json=dump_json(body.kinds),
        destination=body.destination,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return SubscriptionOut(
        id=sub.id,
        variant_id=sub.variant_id,
        target_price_cents=sub.target_price_cents,
        kinds=load_json(sub.kinds_json, []),
        destination=sub.destination or "",
    )


@router.get("/subscriptions", response_model=list[SubscriptionOut])
def list_subscriptions(db: Session = Depends(get_db)) -> list[SubscriptionOut]:
    subs = db.exec(select(AlertSubscription).where(AlertSubscription.active)).all()
    return [
        SubscriptionOut(
            id=s.id,
            variant_id=s.variant_id,
            target_price_cents=s.target_price_cents,
            kinds=load_json(s.kinds_json, []),
            destination=s.destination or "",
        )
        for s in subs
    ]


@router.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: int, db: Session = Depends(get_db)) -> None:
    sub = db.get(AlertSubscription, sub_id)
    if sub is None:
        raise HTTPException(404, "订阅不存在")
    sub.active = False
    db.add(sub)
    db.commit()


class EventOut(BaseModel):
    id: int
    subscription_id: int
    variant_id: int
    kind: str
    payload: dict
    sent_at: str | None
    send_error: str | None


@router.get("/events", response_model=list[EventOut])
def list_events(
    unsent: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[EventOut]:
    stmt = select(AlertEvent).order_by(AlertEvent.created_at.desc()).limit(limit)  # type: ignore[union-attr]
    if unsent:
        stmt = stmt.where(AlertEvent.sent_at.is_(None))  # type: ignore[union-attr]
    events = db.exec(stmt).all()  # type: ignore[call-overload]
    return [
        EventOut(
            id=e.id,
            subscription_id=e.subscription_id,
            variant_id=e.variant_id,
            kind=e.kind,
            payload=load_json(e.payload_json, {}),
            sent_at=e.sent_at.isoformat() if e.sent_at else None,
            send_error=e.send_error,
        )
        for e in events
    ]


@router.post("/events/{event_id}/send")
def resend_event(event_id: int, db: Session = Depends(get_db)) -> dict:
    """手动重发一条事件（渠道兜底顺序：telegram → wecom → smtp）。"""
    event = db.get(AlertEvent, event_id)
    if event is None:
        raise HTTPException(404, "事件不存在")
    sub = db.get(AlertSubscription, event.subscription_id)
    if sub is None or not sub.active:
        raise HTTPException(409, "订阅已取消，不能继续发送通知")
    from app.alerts.history import validate_alert_event
    from app.util import utc_now

    payload, reason = validate_alert_event(db, event)
    if payload is None:
        raise HTTPException(409, reason)
    ok, err = send_alert(payload, destination=sub.destination)
    if ok:
        event.sent_at = utc_now()
        event.send_error = ""
    else:
        event.send_error = err or "发送失败"
    db.add(event)
    db.commit()
    return {"ok": ok, "error": err}
