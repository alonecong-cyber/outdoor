"""匹配器：提取特征 → 已知 Variant（款号+颜色+尺码），低置信度转人工。

置信度构成（PRD §6，<0.85 转人工）：
- 款号精确命中 +0.6；
- 颜色匹配 +0.25（编辑距离相似度 ≥0.8 按比例折算）；
- 尺码精确匹配 +0.15；
- 款号未命中但标题相似度 >0.9：0.6×标题相似度（词典优先、相似度兜底）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from difflib import SequenceMatcher

from app.models import RawListing
from app.normalize.extract import ExtractedFeatures, extract_features

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
    """颜色置信度：完全一致 1.0；包含关系 0.9；相似度 ≥0.8 折算；否则 0。"""
    if not listing_color or not variant_color:
        return 0.0
    a, b = listing_color.lower().strip(), variant_color.lower().strip()
    if a == b:
        return 1.0
    if a in b or b in a:
        return 0.9
    sim = _similarity(a, b)
    return sim if sim >= 0.8 else 0.0


def score_variant(
    feats: ExtractedFeatures, variant: VariantInfo, title: str = ""
) -> tuple[float, list[str]]:
    """给单个 Variant 打分，返回 (置信度, 理由)。"""
    reasons: list[str] = []
    score = 0.0

    if feats.style_number and feats.style_number == variant.style_number.upper():
        score += 0.6
        reasons.append(f"款号命中 {variant.style_number}")
    elif feats.style_number:
        return 0.0, [f"款号不匹配 {feats.style_number}≠{variant.style_number}"]

    c_conf = color_confidence(feats.color, variant.color)
    if c_conf > 0:
        score += 0.25 * c_conf
        reasons.append(f"颜色匹配 {feats.color}≈{variant.color}({c_conf:.2f})")

    if feats.size and feats.size.upper() == variant.size.upper():
        score += 0.15
        reasons.append(f"尺码匹配 {variant.size}")
    elif feats.size and variant.size:
        reasons.append(f"尺码不匹配 {feats.size}≠{variant.size}")

    # 款号缺失时标题相似度兜底（仍要过 0.85 门槛几乎不可能，转人工合理）
    if not feats.style_number and title:
        sim = _similarity(title, f"{variant.style_number} {variant.color} {variant.size}")
        if sim > 0.9:
            score += 0.6 * sim
            reasons.append(f"标题相似度兜底 {sim:.2f}")

    return min(score, 1.0), reasons


def match_variant(
    feats: ExtractedFeatures,
    variants: list[VariantInfo],
    *,
    title: str = "",
) -> MatchResult:
    """在候选 Variant 里找最佳匹配。无候选或全零分 → best=None 转人工。"""
    best: tuple[float, VariantInfo, list[str]] | None = None
    for v in variants:
        score, reasons = score_variant(feats, v, title=title)
        if best is None or score > best[0]:
            best = (score, v, reasons)
    if best is None or best[0] <= 0:
        return MatchResult(None, 0.0, ["无候选/零分，转人工"])
    return MatchResult(best[1].variant_id, round(best[0], 4), best[2])


def match_raw_listing(
    raw: RawListing,
    variants: list[VariantInfo],
    *,
    brand_slug: str = "",
) -> tuple[ExtractedFeatures, MatchResult]:
    """RawListing → (特征, 匹配结果)。存储层据此直接落 variant_id 或 MatchCandidate。"""
    feats = extract_features(
        raw.title,
        brand_slug=brand_slug,
        style_hint=raw.style_number_hint or "",
        color_hint=raw.color_hint or "",
        size_hint=raw.size_hint or "",
    )
    result = match_variant(feats, variants, title=raw.title)
    return feats, result
