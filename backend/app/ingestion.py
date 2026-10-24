"""采集商品的严格身份匹配。线报聚合目录不是已确认的渠道SKU。"""

from __future__ import annotations

from sqlmodel import Session, select

from app.models import Brand, MatchCandidate, RawListing, Style, Variant
from app.normalize.brands import brand_display, detect_brand
from app.normalize.extract import extract_features
from app.normalize.matcher import VariantInfo, match_raw_listing
from app.storage import get_or_create_brand, get_or_create_style, get_or_create_variant
from app.util import dump_json, load_json


def resolve_variant(session: Session, raw: RawListing) -> int | None:
    """品牌隔离、完整规格才能自动关联；不完整输入去重进入审核。"""
    slug = detect_brand(f"{raw.brand_hint} {raw.title}")
    if not slug:
        brand = session.exec(select(Brand).where(Brand.slug == raw.brand_hint)).first()
        slug = brand.slug if brand else ""
    features = extract_features(
        raw.title,
        brand_slug=slug,
        style_hint=raw.style_number_hint,
        color_hint=raw.color_hint,
        size_hint=raw.size_hint,
    )
    rows = (
        session.exec(
            select(Variant, Style)
            .join(Style, Variant.style_id == Style.id)
            .join(Brand, Style.brand_id == Brand.id)
            .where(Brand.slug == slug)
        ).all()
        if slug
        else []
    )
    from app.offers import HASH_STYLE

    candidates = [
        VariantInfo(v.id, s.style_number, v.color, v.size)
        for v, s in rows
        if not HASH_STYLE.fullmatch(s.style_number)
    ]
    features, match = match_raw_listing(raw, candidates, brand_slug=slug)
    if slug and not match.needs_review:
        return match.best_variant_id
    if slug and features.style_number and features.color and features.size:
        name, name_cn = brand_display(slug)
        brand = get_or_create_brand(session, slug, name, name_cn=name_cn)
        style = get_or_create_style(session, brand.id, features.style_number, name=raw.title)
        # 首次出现的完整规格可以建档，但仍先比较已有canonical候选避免中英颜色重复。
        variant = get_or_create_variant(session, style.id, features.color, features.size)
        return variant.id
    key = (raw.source, raw.channel_slug, raw.external_id)
    pending = session.exec(select(MatchCandidate).where(MatchCandidate.status == "pending")).all()
    candidate = None
    for item in pending:
        payload = load_json(item.payload_json, {})
        if (payload.get("source"), payload.get("channel_slug"), payload.get("external_id")) == key:
            candidate = item
            break
    reasons = match.reasons + ["品牌、款号、颜色、尺码必须全部确认后才参与同规格比价"]
    if candidate is None:
        candidate = MatchCandidate(payload_json=raw.model_dump_json(), confidence=match.confidence)
    candidate.payload_json = raw.model_dump_json()
    candidate.suggested_variant_id = match.best_variant_id
    candidate.confidence = match.confidence
    candidate.reasons_json = dump_json(reasons)
    session.add(candidate)
    session.flush()
    return None
