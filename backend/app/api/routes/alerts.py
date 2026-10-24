"""提醒订阅与事件 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session, select

from app.alerts import send_alert
from app.api.deps import get_db
from app.models import AlertEvent, AlertSubscription, Variant
from app.util import dump_json, load_json

router = APIRouter(prefix="/alerts", tags=["alerts"])


class SubscriptionIn(BaseModel):
    variant_id: int
    target_price_cents: int = 0
    kinds: list[str] = ["price_below"]
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
    subs = db.exec(select(AlertSubscription)).all()  # type: ignore[call-overload]
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
    db.delete(sub)
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
    unsent: bool = False, limit: int = 50, db: Session = Depends(get_db)
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
    payload = load_json(event.payload_json, {})
    ok, err = send_alert(payload, destination=sub.destination if sub else "")
    if ok:
        event.sent_at = event.sent_at or event.created_at
        event.send_error = None
    else:
        event.send_error = err
    db.add(event)
    db.commit()
    return {"ok": ok, "error": err}
