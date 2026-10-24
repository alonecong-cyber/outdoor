"""匹配器：款号、颜色、尺码全部一致才允许自动合并。

评分仍为款号0.6 + 颜色0.25 + 尺码0.15；明确冲突直接拒绝，缺规格永远转人工。
候选应先由调用方按已识别品牌隔离，避免不同品牌共用款号时误匹配。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models import RawListing
from app.normalize.extract import (
    ExtractedFeatures,
    extract_features,
    normalize_color,
    normalize_size,
)

REVIEW_THRESHOLD = 0.85


@dataclass
class VariantInfo:
    """候选 Variant 的轻量投影（避免匹配层直接依赖 SQLModel 对象）。"""

    variant_id: int
    style_number: str
    color: str
    size: str


@dataclass
class MatchResult:
    best_variant_id: int | None
    confidence: float
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_review(self) -> bool:
        return self.best_variant_id is None or self.confidence < REVIEW_THRESHOLD


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def color_confidence(listing_color: str, variant_color: str) -> float:
    """仅规范化后完全同色才得1分；子串、模糊相似不能证明同一个颜色 SKU。"""
    a, b = normalize_color(listing_color), normalize_color(variant_color)
    return 1.0 if a and a == b else 0.0


def score_variant(
    feats: ExtractedFeatures, variant: VariantInfo, title: str = ""
) -> tuple[float, list[str]]:
    """返回(置信度, 理由)。明确不同的规格得0分；规格缺失的分数不达自动接受门槛。"""
    style = feats.style_number.strip().upper()
    candidate_style = variant.style_number.strip().upper()
    color, candidate_color = normalize_color(feats.color), normalize_color(variant.color)
    size, candidate_size = normalize_size(feats.size), normalize_size(variant.size)

    for label, actual, candidate in (
        ("款号", style, candidate_style),
        ("颜色", color, candidate_color),
        ("尺码", size, candidate_size),
    ):
        if actual and candidate and actual != candidate:
            return 0.0, [f"{label}不匹配 {actual}≠{candidate}，拒绝合并"]

    score = 0.0
    reasons: list[str] = []
    if style and style == candidate_style:
        score += 0.6
        reasons.append(f"款号命中 {candidate_style}")
    if color and color == candidate_color:
        score += 0.25
        reasons.append(f"颜色匹配 {color}")
    if size and size == candidate_size:
        score += 0.15
        reasons.append(f"尺码匹配 {size}")

    # 标题相似仅供人工审核排序，不能补足缺失的款号或规格。
    if not style and title:
        sim = _similarity(title, f"{variant.style_number} {variant.color} {variant.size}")
        if sim > 0.9:
            score += 0.6 * sim
            reasons.append(f"标题相似度兜底 {sim:.2f}")

    if not all((style, candidate_style, color, candidate_color, size, candidate_size)):
        reasons.append("款号/颜色/尺码不完整，需人工核验")
        score = min(score, REVIEW_THRESHOLD - 0.0001)

    return min(score, 1.0), reasons


def match_variant(
    feats: ExtractedFeatures,
    variants: list[VariantInfo],
    *,
    title: str = "",
) -> MatchResult:
    """在同品牌候选里找最佳匹配。明确规格冲突不会成为建议 Variant。"""
    best: tuple[float, VariantInfo, list[str]] | None = None
    for v in variants:
        score, reasons = score_variant(feats, v, title=title)
        if best is None or score > best[0]:
            best = (score, v, reasons)
    if best is None:
        return MatchResult(None, 0.0, ["无候选，转人工"])
    if best[0] <= 0:
        return MatchResult(None, 0.0, best[2] or ["零分，转人工"])
    return MatchResult(best[1].variant_id, round(best[0], 4), best[2])


def match_raw_listing(
    raw: RawListing,
    variants: list[VariantInfo],
    *,
    brand_slug: str = "",
) -> tuple[ExtractedFeatures, MatchResult]:
    """RawListing → (规范化特征, 匹配结果)。

    自动关联须满足 not result.needs_review。无同规格候选时，调用方仅可在品牌已确认、
    款号/颜色/尺码均非空且款式已唯一确定后，按(style_id, feats.color, feats.size)
    get/create Variant；缺规格不能借用相似候选或创建空规格 Variant。
    """
    feats = extract_features(
        raw.title,
        brand_slug=brand_slug,
        style_hint=raw.style_number_hint or "",
        color_hint=raw.color_hint or "",
        size_hint=raw.size_hint or "",
    )
    result = match_variant(feats, variants, title=raw.title)
    return feats, result
