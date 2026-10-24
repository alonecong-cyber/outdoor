"""normalize 包：特征提取 + Variant 匹配。"""

from app.normalize.extract import (
    ExtractedFeatures,
    extract_color,
    extract_features,
    extract_size,
    extract_style_number,
)
from app.normalize.matcher import (
    REVIEW_THRESHOLD,
    MatchResult,
    VariantInfo,
    match_raw_listing,
    match_variant,
)

__all__ = [
    "ExtractedFeatures",
    "MatchResult",
    "REVIEW_THRESHOLD",
    "VariantInfo",
    "extract_color",
    "extract_features",
    "extract_size",
    "extract_style_number",
    "match_raw_listing",
    "match_variant",
]
