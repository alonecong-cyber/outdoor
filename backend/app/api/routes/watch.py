"""关注列表 API：创建/编辑/暂停关注，手动检查，命中记录。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.deps import get_db
from app.models import Deal, ProductWatch, WatchAlert
from app.util import dump_json, load_json
from app.watch import check_all_watches

router = APIRouter(prefix="/watch", tags=["watch"])


class WatchIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    keywords: list[str] = []
    must_words: list[str] = []
    exclude_words: list[str] = []
    target_price: float = Field(default=0, ge=0)  # 元；0 = 不设
    currency: str = "CNY"
    qty: int = Field(default=1, ge=1, le=50)
    platforms: list[str] = []


class WatchOut(BaseModel):
    id: int
    name: str
    keywords: list[str]
    must_words: list[str]
    exclude_words: list[str]
    target_price_cents: int
    currency: str
    qty: int
    platforms: list[str]
    active: bool
    last_checked_at: str | None
    last_result: str
    created_at: str | None


def _out(w: ProductWatch) -> WatchOut:
    return WatchOut(
        id=w.id,  # type: ignore[arg-type]
        name=w.name,
        keywords=load_json(w.keywords_json, []),
        must_words=load_json(w.must_words_json, []),
        exclude_words=load_json(w.exclude_words_json, []),
        target_price_cents=w.target_price_cents,
        currency=w.currency,
        qty=w.qty,
        platforms=load_json(w.platforms_json, []),
        active=w.active,
        last_checked_at=w.last_checked_at.isoformat() if w.last_checked_at else None,
        last_result=w.last_result,
        created_at=w.created_at.isoformat() if w.created_at else None,
    )


def _apply(w: ProductWatch, body: WatchIn) -> None:
    w.name = body.name.strip()
    w.keywords_json = dump_json(body.keywords)
    w.must_words_json = dump_json(body.must_words)
    w.exclude_words_json = dump_json(body.exclude_words)
    w.target_price_cents = int(round(body.target_price * 100))
    w.currency = body.currency or "CNY"
    w.qty = body.qty
    w.platforms_json = dump_json(body.platforms)


@router.get("", response_model=list[WatchOut])
def list_watches(db: Session = Depends(get_db)) -> list[WatchOut]:
    watches = db.exec(select(ProductWatch).order_by(ProductWatch.id.desc())).all()
    return [_out(w) for w in watches]


@router.post("", response_model=WatchOut)
def create_watch(body: WatchIn, db: Session = Depends(get_db)) -> WatchOut:
    w = ProductWatch(active=True)
    _apply(w, body)
    db.add(w)
    db.commit()
    db.refresh(w)
    return _out(w)


@router.put("/{watch_id}", response_model=WatchOut)
def update_watch(watch_id: int, body: WatchIn, db: Session = Depends(get_db)) -> WatchOut:
    w = db.get(ProductWatch, watch_id)
    if w is None:
        raise HTTPException(404, "关注不存在")
    _apply(w, body)
    db.add(w)
    db.commit()
    db.refresh(w)
    return _out(w)


@router.post("/{watch_id}/active")
def set_active(watch_id: int, active: bool, db: Session = Depends(get_db)) -> dict:
    w = db.get(ProductWatch, watch_id)
    if w is None:
        raise HTTPException(404, "关注不存在")
    w.active = active
    db.add(w)
    db.commit()
    return {"ok": True, "active": active}


@router.delete("/{watch_id}", status_code=204)
def delete_watch(watch_id: int, db: Session = Depends(get_db)) -> None:
    w = db.get(ProductWatch, watch_id)
    if w is None:
        raise HTTPException(404, "关注不存在")
    db.delete(w)
    db.commit()


@router.post("/check")
def check_now(db: Session = Depends(get_db)) -> dict:
    """立即检查全部关注（只匹配站内已有线报，不发外部请求）。"""
    return check_all_watches(db)


@router.get("/{watch_id}/alerts")
def watch_alerts(watch_id: int, db: Session = Depends(get_db)) -> list[dict]:
    if db.get(ProductWatch, watch_id) is None:
        raise HTTPException(404, "关注不存在")
    rows = (
        db.exec(
            select(WatchAlert)
            .where(WatchAlert.watch_id == watch_id)
            .order_by(WatchAlert.created_at.desc())  # type: ignore[union-attr]
            .limit(50)
        )
        .all()  # type: ignore[call-overload]
    )
    deals = {d.id: d for d in db.exec(select(Deal)).all()}
    out = []
    for a in rows:
        deal = deals.get(a.deal_id)
        out.append(
            {
                "id": a.id,
                "kind": a.kind,
                "price_cents": a.price_cents,
                "reason": a.reason,
                "deal_title": deal.title if deal else "",
                "deal_url": deal.url if deal else "",
                "channel": deal.channel if deal else "",
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "sent_at": a.sent_at.isoformat() if a.sent_at else None,
                "send_error": a.send_error,
            }
        )
    return out
