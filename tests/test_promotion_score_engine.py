"""Tests for promotion_score_engine.py — 推广评分计算."""
from __future__ import annotations

from App.services.promotion_score_engine import (
    _estimate_category_match,
    _estimate_ctr_factor,
    _estimate_title_match,
    calculate_score,
    get_level_for_score,
)


class TestCategoryMatch:
    def test_electronics_keyword_matches_electronics_category(self):
        score = _estimate_category_match("electronics", "bluetooth speaker")
        assert score > 0.5

    def test_generic_keyword_lower_match(self):
        score = _estimate_category_match("clothing", "usb cable")
        assert score < 0.7

    def test_none_category_gets_default(self):
        score = _estimate_category_match(None, "anything")
        assert score == 0.5

    def test_category_in_keyword_gets_bonus(self):
        """phone in 'phone accessories' adds word-in-category bonus."""
        score = _estimate_category_match("phones and accessories", "phone case")
        assert score > 0.6


class TestTitleMatch:
    def test_exact_match(self):
        score = _estimate_title_match("Bluetooth Wireless Headphone", "wireless headphone")
        assert score > 0.7

    def test_partial_match(self):
        score = _estimate_title_match("Bluetooth Wireless Headphone", "bluetooth headphone")
        assert 0.5 <= score <= 1.0

    def test_no_match(self):
        score = _estimate_title_match("Summer Dress", "bluetooth speaker")
        assert score < 0.5

    def test_partial_word_match(self):
        score = _estimate_title_match("USB C Charger Cable", "charger cable")
        assert 0.5 <= score <= 1.0

    def test_empty_title_returns_zero(self):
        score = _estimate_title_match(None, "keyword")
        assert score == 0.0


class TestCtrFactor:
    def test_high_ctr_returns_1(self):
        assert _estimate_ctr_factor(0.08) == 1.0

    def test_medium_ctr_returns_0_8(self):
        assert _estimate_ctr_factor(0.02) == 0.8

    def test_low_ctr_returns_0_2(self):
        assert _estimate_ctr_factor(0.001) == 0.2

    def test_none_ctr_returns_0_5(self):
        assert _estimate_ctr_factor(None) == 0.5


class TestCalculateScore:
    def test_five_star_all_high(self):
        score = calculate_score(0.95, 0.90, 0.85, has_penalty=False)
        assert score == 5

    def test_four_star(self):
        score = calculate_score(0.75, 0.70, 0.65, has_penalty=False)
        assert score == 4

    def test_three_star(self):
        score = calculate_score(0.55, 0.50, 0.45, has_penalty=False)
        assert score == 3

    def test_two_star(self):
        score = calculate_score(0.35, 0.30, 0.25, has_penalty=False)
        assert score == 2

    def test_one_star(self):
        score = calculate_score(0.1, 0.1, 0.1, has_penalty=False)
        assert score == 1

    def test_penalty_heavy_discount(self):
        score_without = calculate_score(0.80, 0.80, 0.80, has_penalty=False)
        score_with = calculate_score(0.80, 0.80, 0.80, has_penalty=True)
        assert score_with <= score_without


class TestGetLevelForScore:
    def test_all_levels(self):
        assert get_level_for_score(5) == "五星"
        assert get_level_for_score(4) == "四星"
        assert get_level_for_score(3) == "三星"
        assert get_level_for_score(2) == "二星"
        assert get_level_for_score(1) == "一星"
