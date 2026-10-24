"""SKU 归一化测试：特征提取 + Variant 匹配。"""

from __future__ import annotations

import pytest

from app.models import RawListing
from app.normalize.extract import (
    extract_color,
    extract_features,
    extract_size,
    extract_style_number,
)
from app.normalize.matcher import (
    REVIEW_THRESHOLD,
    VariantInfo,
    match_raw_listing,
    match_variant,
)

JD_TITLE = "始祖鸟 Arc'teryx Beta LT 夹克 男款 27910 黑色 M 码"


class TestExtractStyle:
    def test_arcteryx_five_digits(self):
        assert extract_style_number(JD_TITLE, "arcteryx") == "27910"

    def test_tnf_prefix_code(self):
        assert (
            extract_style_number("The North Face 1996 复刻羽绒服 NF0A3VU7 男款", "tnf")
            == "NF0A3VU7"
        )

    def test_patagonia_with_suffix(self):
        assert extract_style_number("Patagonia Retro-X 28425 抓绒", "patagonia") == "28425"

    def test_hint_wins(self):
        assert extract_style_number("不明型号的鸟", "arcteryx", style_hint="27910") == "27910"

    def test_no_match_returns_empty(self):
        assert extract_style_number("始祖鸟某件没有款号的衣服", "arcteryx") == ""


class TestExtractColor:
    def test_chinese_color(self):
        assert extract_color(JD_TITLE) == "黑色"

    def test_long_english_term_first(self):
        # 长词优先：Forest Green 不能被截成 green
        assert extract_color("Arc'teryx Beta LT Jacket Forest Green") == "forest green"

    def test_hint_priority(self):
        assert extract_color("颜色不明", color_hint="Solitude") == "Solitude"  # hint 原样透传

    @pytest.mark.parametrize(
        ("title", "expected"),
        [
            ("27910 Black Heather M", "black heather"),
            ("27910 Light Grey M", "light grey"),
            ("27910 Navy Blue M", "navy blue"),
            ("27910 深蓝 M", "深蓝"),
            ("27910黑色M码", "黑色"),
            ("27910 Blackbird M", ""),
            ("27910 Lightweight M", ""),
        ],
    )
    def test_compound_color_and_word_boundaries(self, title: str, expected: str):
        assert extract_color(title) == expected


class TestExtractSize:
    def test_letter_size(self):
        assert extract_size(JD_TITLE) == "M"

    def test_us_shoe_size(self):
        assert extract_size("TNF Hedgehog US 9 中帮徒步鞋") == "US9"

    def test_cn_size(self):
        assert extract_size("优衣库摇粒绒 175/96A") == "175/96A"

    def test_none(self):
        assert extract_size("无尺码信息") == ""


class TestExtractFeatures:
    def test_full_pipeline(self):
        f = extract_features(
            JD_TITLE,
            brand_slug="arcteryx",
            style_hint="27910",
            color_hint="Black",
            size_hint="M",
        )
        assert f.style_number == "27910"
        assert f.color == "black"  # 结构化特征用于跨渠道同规格归一化
        assert f.size == "M"
        assert f.brand_slug == "arcteryx"

    @pytest.mark.parametrize(
        ("color", "size", "expected_color", "expected_size"),
        [
            ("黑色", "2xl", "black", "XXL"),
            ("Gray", "US 9", "grey", "US9"),
            ("藏青", "3XL", "navy", "XXXL"),
        ],
    )
    def test_color_and_size_aliases_are_canonical(
        self, color: str, size: str, expected_color: str, expected_size: str
    ):
        feats = extract_features("27910", color_hint=color, size_hint=size)
        assert feats.color == expected_color
        assert feats.size == expected_size


class TestMatchVariant:
    def test_exact_match_confident(self):
        feats = extract_features(JD_TITLE, brand_slug="arcteryx", style_hint="27910")
        variants = [VariantInfo(1, "27910", "Black", "M"), VariantInfo(2, "27910", "Red", "L")]
        r = match_variant(feats, variants)
        # 手算：款号 0.6 + 黑色=black 0.25 + 尺码 M 0.15 = 1.0。
        assert r.best_variant_id == 1
        assert r.confidence == 1.0
        assert not r.needs_review

    def test_english_color_full_score(self):
        feats = extract_features(
            "Arc'teryx Beta LT 27910 Black M", brand_slug="arcteryx", style_hint="27910"
        )
        variants = [VariantInfo(1, "27910", "Black", "M")]
        r = match_variant(feats, variants)
        assert r.best_variant_id == 1
        assert r.confidence == 1.0  # 0.6 + 0.25 + 0.15
        assert not r.needs_review

    def test_size_mismatch_is_hard_rejection(self):
        # 款号+颜色虽有 0.85 分，M 和 L 属于不同 SKU，必须拒绝。
        feats = extract_features(
            "Arc'teryx Beta LT 27910 Black M", brand_slug="arcteryx", style_hint="27910"
        )
        variants = [VariantInfo(1, "27910", "Black", "L")]
        r = match_variant(feats, variants)
        assert r.best_variant_id is None
        assert r.confidence == 0.0
        assert r.needs_review

    @pytest.mark.parametrize("listing_color", ["Red", "Black Heather", "Blue"])
    def test_color_mismatch_is_hard_rejection(self, listing_color: str):
        feats = extract_features(
            "27910 M", style_hint="27910", color_hint=listing_color, size_hint="M"
        )
        r = match_variant(feats, [VariantInfo(1, "27910", "Black", "M")])
        assert r.best_variant_id is None
        assert r.confidence == 0.0
        assert r.needs_review

    @pytest.mark.parametrize(
        ("title_color", "variant_color"),
        [("Black Heather", "Black"), ("Light Grey", "Grey"), ("Navy Blue", "Blue")],
    )
    def test_compound_title_color_cannot_merge_with_base_color(
        self, title_color: str, variant_color: str
    ):
        feats = extract_features(f"27910 {title_color} M")
        result = match_variant(feats, [VariantInfo(1, "27910", variant_color, "M")])
        assert result.best_variant_id is None
        assert result.confidence == 0.0
        assert result.needs_review

    @pytest.mark.parametrize(
        ("color", "size", "variant_color", "variant_size"),
        [
            ("Black", "", "Black", "M"),
            ("", "M", "Black", "M"),
            ("Black", "M", "Black", ""),
            ("Black", "M", "", "M"),
        ],
    )
    def test_missing_spec_never_auto_merges(
        self, color: str, size: str, variant_color: str, variant_size: str
    ):
        feats = extract_features("27910", style_hint="27910", color_hint=color, size_hint=size)
        r = match_variant(feats, [VariantInfo(1, "27910", variant_color, variant_size)])
        assert r.needs_review
        assert r.confidence < REVIEW_THRESHOLD

    def test_conflicting_candidate_cannot_hide_matching_variant(self):
        feats = extract_features("27910 Black M", style_hint="27910")
        variants = [VariantInfo(1, "27910", "Black", "L"), VariantInfo(2, "27910", "Black", "M")]
        r = match_variant(feats, variants)
        assert r.best_variant_id == 2
        assert r.confidence == 1.0
        assert not r.needs_review

    def test_style_mismatch_scores_zero(self):
        feats = extract_features("TNF 1996 复刻 NF0A3VU7", brand_slug="tnf", style_hint="NF0A3VU7")
        variants = [VariantInfo(1, "27910", "Black", "M")]
        r = match_variant(feats, variants)
        assert r.best_variant_id is None
        assert r.needs_review  # 款号对不上 → 转人工

    def test_review_threshold_value(self):
        assert REVIEW_THRESHOLD == 0.85


class TestMatchRawListing:
    def test_jd_style_listing(self):
        raw = RawListing(
            source="jd_union",
            channel_slug="jd",
            external_id="100012345",
            title=JD_TITLE,
            price_cents=399800,
            style_number_hint="27910",
            color_hint="Black",
            size_hint="M",
        )
        variants = [VariantInfo(7, "27910", "Black", "M")]
        feats, r = match_raw_listing(raw, variants, brand_slug="arcteryx")
        assert r.best_variant_id == 7
        assert r.confidence == 1.0
