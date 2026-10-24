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
        assert extract_style_number(
            "The North Face 1996 复刻羽绒服 NF0A3VU7 男款", "tnf"
        ) == "NF0A3VU7"

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
        assert f.color == "Black"  # hint 原样透传
        assert f.size == "M"
        assert f.brand_slug == "arcteryx"


class TestMatchVariant:
    def test_exact_match_confident(self):
        feats = extract_features(JD_TITLE, brand_slug="arcteryx", style_hint="27910")
        variants = [VariantInfo(1, "27910", "Black", "M"), VariantInfo(2, "27910", "Red", "L")]
        r = match_variant(feats, variants)
        # 手算：款号 0.6 + 颜色 black≈黑色?（中文→英文无词典时置信度低）+ 尺码 M 0.15
        assert r.best_variant_id == 1
        assert r.confidence >= 0.6 + 0.15

    def test_english_color_full_score(self):
        feats = extract_features(
            "Arc'teryx Beta LT 27910 Black M", brand_slug="arcteryx", style_hint="27910"
        )
        variants = [VariantInfo(1, "27910", "Black", "M")]
        r = match_variant(feats, variants)
        assert r.best_variant_id == 1
        assert r.confidence == 1.0  # 0.6 + 0.25 + 0.15
        assert not r.needs_review

    def test_size_mismatch_still_auto_above_threshold(self):
        # 手算：0.6 + 0.25（颜色完全一致）= 0.85，恰好不 < 0.85 → 自动接受（边界）
        feats = extract_features(
            "Arc'teryx Beta LT 27910 Black M", brand_slug="arcteryx", style_hint="27910"
        )
        variants = [VariantInfo(1, "27910", "Black", "L")]
        r = match_variant(feats, variants)
        assert r.confidence == pytest.approx(0.85)
        assert not r.needs_review

    def test_style_mismatch_scores_zero(self):
        feats = extract_features(
            "TNF 1996 复刻 NF0A3VU7", brand_slug="tnf", style_hint="NF0A3VU7"
        )
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
