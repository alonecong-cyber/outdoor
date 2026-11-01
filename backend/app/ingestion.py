"""采集商品的严格身份匹配。线报聚合目录不是已确认的渠道SKU。"""

from __future__ import annotations

import re

from sqlmodel import Session, select

from app.models import Brand, MatchCandidate, RawListing, Style, Variant
from app.normalize.brands import brand_display, detect_brand
from app.normalize.extract import extract_features
from app.normalize.matcher import VariantInfo, match_raw_listing
from app.storage import get_or_create_brand, get_or_create_style, get_or_create_variant
from app.util import dump_json, load_json

_VARIANT_SUFFIX_RE = re.compile(r",\s*[^,]+,\s*Size\s+\S+\s*$")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
# 款式名匹配只忽略所有格残留与品牌词，性别词（men/women）保留以免误并。
_NAME_STOP_TOKENS = {"s"}


def style_display_name(title: str) -> str:
    """去掉变体标题末尾的「, 颜色, Size 尺码」后缀，得到款式名。"""
    return _VARIANT_SUFFIX_RE.sub("", title).strip()


def _name_tokens(text: str, brand_tokens: set[str]) -> set[str]:
    tokens = set(_TOKEN_RE.findall(text.lower()))
    return tokens - brand_tokens - _NAME_STOP_TOKENS


def _color_key(color: str) -> str:
    """颜色比对键：小写、折叠空白、斜杠两侧去空格（electra / soulsonic ≡ electra/soulsonic）。"""
    return re.sub(r"\s*/\s*", "/", " ".join(color.lower().split()))


def _match_by_style_name(session: Session, raw: RawListing, slug: str, features) -> int | None:
    """零售商无原厂款号时，按「品牌+款式名 token 集合精确相等」唯一确定款式。

    仅当恰好一个同品牌款式名与标题 token 集合完全一致（多一个少一个都拒绝，
    "Beta AR" 不会并进 "Beta AR StormHood"），再按颜色+尺码找或建 Variant。
    """
    brand = session.exec(select(Brand).where(Brand.slug == slug)).first()
    if brand is None:
        return None
    brand_tokens = set(_TOKEN_RE.findall(f"{raw.brand_hint} {brand.name}".lower()))
    listing_tokens = _name_tokens(raw.title, brand_tokens)
    if not listing_tokens:
        return None
    styles = session.exec(select(Style).where(Style.brand_id == brand.id)).all()
    matched = [s for s in styles if s.name and _name_tokens(s.name, brand_tokens) == listing_tokens]
    if len(matched) != 1:
        return None
    style = matched[0]
    if not (features.color and features.size):
        return None
    from app.normalize.extract import normalize_size

    rows = session.exec(
        select(Variant).where(Variant.style_id == style.id)  # type: ignore[arg-type]
    ).all()
    for v in rows:
        if _color_key(v.color) == _color_key(features.color) and normalize_size(
            v.size
        ) == normalize_size(features.size):
            return v.id
    variant = get_or_create_variant(session, style.id, features.color, features.size)
    return variant.id


def resolve_variant(session: Session, raw: RawListing, *, auto_only: bool = False) -> int | None:
    """品牌隔离、完整规格才能自动关联；不完整输入去重进入审核。

    auto_only=True（零售商目录采集）：只做自动匹配，不能唯一确定时直接
    返回 None，不进人工审核队列——大目录会把队列刷爆。
    """
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
    if slug and not features.style_number and features.color and features.size:
        named = _match_by_style_name(session, raw, slug, features)
        if named is not None:
            return named
        if auto_only:
            return None
    if slug and features.style_number and features.color and features.size and not auto_only:
        name, name_cn = brand_display(slug)
        brand = get_or_create_brand(session, slug, name, name_cn=name_cn)
        style = get_or_create_style(
            session, brand.id, features.style_number, name=style_display_name(raw.title)
        )
        # 首次出现的完整规格可以建档，但仍先比较已有canonical候选避免中英颜色重复。
        variant = get_or_create_variant(session, style.id, features.color, features.size)
        return variant.id
    if auto_only:
        return None
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
