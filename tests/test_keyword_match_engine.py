"""Tests for keyword_match_engine.py — 关键词适配度."""
from __future__ import annotations

from App.services.keyword_match_engine import (
    _compute_semantic_similarity,
    classify_keyword_type,
)


class TestSemanticSimilarity:
    def test_exact_match_max_score(self):
        score = _compute_semantic_similarity("Bluetooth Headphone", "bluetooth headphone")
        assert score == 100.0

    def test_partial_word_match(self):
        score = _compute_semantic_similarity("Wireless Bluetooth Headphone", "bluetooth headphone")
        assert score > 50.0

    def test_no_match_low_score(self):
        score = _compute_semantic_similarity("Summer Dress", "bluetooth speaker")
        assert score < 30.0

    def test_preposition_penalty(self):
        """介词改变语义时扣分."""
        score1 = _compute_semantic_similarity("Phone Case", "phone case")
        score2 = _compute_semantic_similarity("Phone Case", "phone no case")
        assert score2 <= score1

    def test_empty_title_zero(self):
        score = _compute_semantic_similarity("", "keyword")
        assert score == 0.0

    def test_empty_keyword_zero(self):
        score = _compute_semantic_similarity("Title", "")
        assert score == 0.0


class TestClassifyKeywordType:
    def test_hot_keyword(self):
        assert classify_keyword_type("phone", search_volume=15000) == "hot"

    def test_high_conversion(self):
        assert classify_keyword_type("converting", conversion_rate=0.08) == "high_conversion"

    def test_low_cost(self):
        assert classify_keyword_type("cheap", avg_cpc=0.3, search_volume=2000) == "low_cost"

    def test_pickup_keyword(self):
        assert classify_keyword_type("trending", search_volume=3000, avg_cpc=0.6) == "pickup"

    def test_no_data_returns_other(self):
        assert classify_keyword_type("generic") == "other"
