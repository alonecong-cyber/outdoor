"""线报落库与商品目录自动生长（Deal → Variant）。

- save_deal：按 (source, source_id) 幂等；content_hash 相同视为重复线报跳过；
- grow_variant：标题 → 品牌词典 → 款号/颜色/尺码提取 → 新建或关联 Variant；
  品牌识别不出就留在未匹配（matched_variant_id = NULL），绝不猜；
  品牌命中但标题无款号时，用「标题核心词哈希」当聚合键——同款重复线报
  标题一致即聚到同一 Variant，不同款标题不同自然分开；
- 商品目录由此从线报流里长出来，不预置任何单品。
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from sqlalchemy import func
from sqlmodel import Session, select

from app.models import Brand, Deal, DealDraft, Style, Variant
from app.normalize.brands import brand_display, clean_style_name, detect_brand
from app.normalize.extract import extract_features
from app.storage import get_or_create_brand, get_or_create_style, get_or_create_variant
from app.util import dump_json, to_naive_utc, utc_now

# 线报标题常见的营销前缀，剥掉后再做核心词
_TITLE_PREFIX_RE = re.compile(r"^(88VIP|今日必买|移动端|小编推荐|值友专享)[:：]\s*")


def content_hash(draft: DealDraft) -> str:
    raw = draft.model_dump(exclude={"checked_at"}, mode="json")
    return hashlib.sha256(dump_json(raw).encode("utf-8")).hexdigest()[:16]


def grow_variant(session: Session, title: str) -> int | None:
    """线报标题 → Variant（新建或关联已有）。品牌识别不出返回 None。"""
    slug = detect_brand(title)
    if not slug:
        return None
    name, name_cn = brand_display(slug)
    core_title = _TITLE_PREFIX_RE.sub("", title).strip()
    feats = extract_features(core_title, brand_slug=slug)
    if feats.style_number:
        style_number = feats.style_number
        style_name = clean_style_name(core_title, (name, name_cn)) or f"{name} {style_number}"
    else:
        # 无款号：标题核心词哈希当聚合键，同款重复线报聚到同一 Variant
        core = clean_style_name(core_title, (name, name_cn))
        style_number = "T" + hashlib.sha1(core.encode("utf-8")).hexdigest()[:7].upper()
        style_name = core or f"{name} {style_number}"
    brand = get_or_create_brand(session, slug, name, name_cn=name_cn)
    style = get_or_create_style(session, brand.id, style_number, name=style_name)
    variant = get_or_create_variant(
        session, style.id, feats.color or "-", feats.size or "-"
    )
    return variant.id


def save_deal(
    session: Session, draft: DealDraft, *, grow_catalog: bool = True
) -> tuple[Deal, bool]:
    """DealDraft → Deal upsert。返回 (deal, created)；重复内容返回 created=False。"""
    h = content_hash(draft)
    deal = session.exec(
        select(Deal).filter_by(source=draft.source, source_id=draft.source_id)
    ).first()
    checked_at = to_naive_utc(draft.checked_at) if draft.checked_at else utc_now()
    if deal is not None:
        if deal.content_hash == h:
            deal.last_checked_at = checked_at
            session.add(deal)
            session.flush()
            return deal, False
        deal.title = draft.title
        deal.price_cents = draft.price_cents
        deal.currency = draft.currency
        deal.channel = draft.channel
        deal.image = draft.image
        deal.url = draft.url or deal.url
        deal.tags_json = dump_json(draft.tags)
        deal.summary = draft.summary or deal.summary
        if draft.published_at:
            deal.published_at = draft.published_at
        created = False
    else:
        deal = Deal(
            source=draft.source,
            source_id=draft.source_id,
            url=draft.url,
            title=draft.title,
            summary=draft.summary,
            price_cents=draft.price_cents,
            currency=draft.currency,
            channel=draft.channel,
            image=draft.image,
            tags_json=dump_json(draft.tags),
            published_at=draft.published_at,
        )
        created = True
    deal.content_hash = h
    deal.last_checked_at = checked_at
    deal.expires_at = to_naive_utc(draft.expires_at) if draft.expires_at else None
    deal.expired = draft.expired
    if grow_catalog:
        variant_id = grow_variant(session, deal.title)
        deal.matched_variant_id = variant_id
    session.add(deal)
    session.flush()
    return deal, created


def max_source_id(session: Session, source: str = "smzdm") -> int:
    """已入库线报的最大 source_id（整数），增量发现的起点。"""
    rows = session.exec(
        select(Deal.source_id).where(Deal.source == source)  # type: ignore[call-overload]
    ).all()
    ids = [int(r) for r in rows if r.isdigit()]
    return max(ids, default=0)


def known_source_ids(
    session: Session, source: str = "smzdm", *, fresh_only: bool = False
) -> set[str]:
    """仅跳过复核期内的ID；旧内容仍可更新失效、价格与优惠条件。"""
    from datetime import timedelta

    from app.config import get_settings

    stmt = select(Deal).where(Deal.source == source)
    if fresh_only:
        cutoff = utc_now() - timedelta(hours=get_settings().deal_recheck_hours)
        stmt = stmt.where(Deal.last_checked_at.is_not(None), Deal.last_checked_at >= cutoff)
    return {deal.source_id for deal in session.exec(stmt).all()}


def reports_due_for_recheck(session: Session, *, limit: int = 2) -> list[Deal]:
    from datetime import timedelta

    from sqlalchemy import or_

    from app.config import get_settings

    cutoff = utc_now() - timedelta(hours=get_settings().deal_recheck_hours)
    # 最近两周的线报有限轮询；更旧内容统一标注历史参考，不无限抓取。
    recent = utc_now() - timedelta(days=14)
    rows = session.exec(
        select(Deal).where(
            Deal.source == "smzdm", Deal.created_at >= recent, Deal.url != "",
            or_(Deal.last_checked_at.is_(None), Deal.last_checked_at < cutoff),
        ).order_by(Deal.last_checked_at, Deal.id).limit(limit)
    ).all()
    return list(rows)


def ingest_deals(
    session: Session, drafts: Iterable[DealDraft], *, grow_catalog: bool = True
) -> dict:
    """批量落库。单条失败回滚记录，不拖垮整批。"""
    saved = created = matched = 0
    errors: list[str] = []
    for d in drafts:
        try:
            with session.begin_nested():
                deal, c = save_deal(session, d, grow_catalog=grow_catalog)
                is_matched = deal.matched_variant_id is not None
            saved += 1
            created += int(c)
            matched += int(is_matched)
        except Exception as e:  # noqa: BLE001 - 单条失败继续
            errors.append(f"{d.source_id}: {e}")
    session.commit()
    return {"saved": saved, "created": created, "matched": matched, "errors": errors}


def list_deals(session: Session, *, limit: int = 50, offset: int = 0) -> list[Deal]:
    """线报流：新→旧（published_at 缺失用 created_at 兜底）。"""
    key = func.coalesce(Deal.published_at, Deal.created_at)
    rows = session.exec(
        select(Deal)
        .order_by(key.desc())  # type: ignore[arg-type]
        .offset(offset)
        .limit(limit)
    ).all()
    return list(rows)


def variant_context(session: Session, variant_ids: set[int]) -> dict[int, dict]:
    """批量取 variant 的品牌/款式信息，供线报卡片展示。"""
    ctx: dict[int, dict] = {}
    if not variant_ids:
        return ctx
    rows = session.exec(
        select(Variant, Style, Brand)
        .join(Style, Variant.style_id == Style.id)  # type: ignore[arg-type]
        .join(Brand, Style.brand_id == Brand.id)  # type: ignore[arg-type]
        .where(Variant.id.in_(variant_ids))  # type: ignore[union-attr]
    ).all()
    for variant, style, brand in rows:
        ctx[variant.id] = {
            "variant_id": variant.id,
            "brand_slug": brand.slug,
            "brand_name": brand.name_cn or brand.name,
            "style_number": style.style_number,
            "style_name": style.name,
            "color": variant.color,
            "size": variant.size,
        }
    return ctx
