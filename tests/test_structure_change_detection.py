"""单元测试: 结构变更检测 (TASK-028-3)."""

from __future__ import annotations

from App.services.api_interceptor import (
    AdDataInterceptor,
    CollectedAdData,
    CollectedPriceData,
)


def _make_interceptor(
    total_responses: int = 0,
    ad_api_responses: int = 0,
    responses_without_match: int = 0,
    ad_count: int = 0,
    price_count: int = 0,
) -> AdDataInterceptor:
    """创建一个预设好拦截结果的拦截器实例。"""
    interceptor = AdDataInterceptor()
    interceptor.result.total_responses = total_responses
    interceptor.result.ad_api_responses = ad_api_responses
    interceptor.result.responses_without_match = responses_without_match

    for i in range(ad_count):
        interceptor.result.ad_data.append(
            CollectedAdData(sku_id=f"sku_{i}", impressions=100, clicks=5)
        )
    for i in range(price_count):
        interceptor.result.price_data.append(
            CollectedPriceData(sku_id=f"sku_{i}", current_price=10.0)
        )
    return interceptor


# ── 场景 1: 正常采集 (应返回 detected=False) ─────


def test_normal_no_change():
    """10 个 API 响应全部匹配成功 → 检测结果正常。"""
    interceptor = _make_interceptor(
        total_responses=30,
        ad_api_responses=10,
        responses_without_match=0,
        ad_count=5,
        price_count=3,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is False
    assert report["confidence"] == 0.0
    assert report["reason"] == "结构正常"


def test_normal_partial_misses():
    """10 个 API 响应中 2 个未匹配 (80% 匹配率) → 低于检测阈值。"""
    interceptor = _make_interceptor(
        total_responses=30,
        ad_api_responses=10,
        responses_without_match=2,
        ad_count=5,
        price_count=3,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is False


# ── 场景 2: 零 API 响应 (URL 模式全部失效) ────────


def test_zero_api_responses():
    """有总响应但无 API 响应 → URL 模式可能已变更。"""
    interceptor = _make_interceptor(
        total_responses=15,
        ad_api_responses=0,
        responses_without_match=0,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is True
    assert report["confidence"] >= 0.8
    assert "URL 模式" in report["reason"] or "URL" in report["reason"]


def test_no_responses_at_all():
    """完全没有响应 → 没有依据判断结构变更。"""
    interceptor = _make_interceptor(
        total_responses=0,
        ad_api_responses=0,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is False


# ── 场景 3: 全部未命中 (字段名已变更) ──────────────


def test_all_api_responses_no_match():
    """5 个 API 响应全部无法提取数据 → 字段格式已变更。"""
    interceptor = _make_interceptor(
        total_responses=20,
        ad_api_responses=5,
        responses_without_match=5,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is True
    assert report["confidence"] >= 0.8
    assert "均无法提取" in report["reason"]


# ── 场景 4: 高比例未命中 (渐进式改版) ─────────────


def test_high_miss_rate():
    """8 个 API 响应中 6 个未匹配 (25% 匹配率) → 中等置信度检测。"""
    interceptor = _make_interceptor(
        total_responses=30,
        ad_api_responses=8,
        responses_without_match=6,
        ad_count=2,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is True
    assert report["confidence"] == 0.75
    assert "匹配率" in report["reason"]


def test_moderate_miss_rate():
    """10 个 API 响应中 5 个未匹配 (50% 匹配率) → 低置信度预警。"""
    interceptor = _make_interceptor(
        total_responses=40,
        ad_api_responses=10,
        responses_without_match=5,
        ad_count=5,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is True
    assert report["confidence"] == 0.5
    assert "建议关注" in report["reason"]


# ── 场景 5: 边界条件 ─────────────────────────────


def test_few_api_responses_no_flag():
    """API 响应太少 (< 4) 且部分匹配 → 不触发检测。"""
    interceptor = _make_interceptor(
        total_responses=5,
        ad_api_responses=2,
        responses_without_match=1,
        ad_count=1,
    )
    report = interceptor.detect_structure_change()
    assert report["detected"] is False


def test_total_api_zero_match_zero():
    """全零初始状态 → 无结构变更。"""
    interceptor = _make_interceptor()
    report = interceptor.detect_structure_change()
    assert report["detected"] is False


def test_metrics_always_present():
    """检测报告始终包含 metrics 字典。"""
    interceptor = _make_interceptor(
        total_responses=20,
        ad_api_responses=5,
        responses_without_match=5,
    )
    report = interceptor.detect_structure_change()
    assert "metrics" in report
    metrics = report["metrics"]
    assert "total_api_responses" in metrics
    assert "total_ad_records" in metrics
    assert "total_price_records" in metrics
    assert "responses_without_match" in metrics
