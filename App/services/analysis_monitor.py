"""分析管线监控服务 — 跟踪分析运行状态、成功/失败计数、耗时统计。

使用内存数据结构，无需数据库表。重启后重置。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class SkuMetrics:
    """单个 SKU 的分析指标。"""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_duration_ms: float = 0
    last_run_at: str | None = None
    last_error: str | None = None
    last_decision_type: str | None = None


@dataclass
class PipelineMetrics:
    """分析管线全局指标。"""
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    ai_calls: int = 0
    ai_failures: int = 0
    boundary_passed: int = 0
    boundary_blocked: int = 0
    total_duration_ms: float = 0
    avg_duration_ms: float = 0
    last_run_at: str | None = None
    last_run_sku: str | None = None
    last_error: str | None = None
    is_healthy: bool = True
    skus: dict[str, SkuMetrics] = field(default_factory=lambda: defaultdict(SkuMetrics))
    recent_runs: list[dict[str, Any]] = field(default_factory=list)
    started_at: str = field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )

    def record_run(
        self,
        sku_id: str,
        duration_ms: float,
        success: bool,
        decision_type: str | None = None,
        boundary_passed: bool | None = None,
        error: str | None = None,
        used_ai: bool = False,
    ) -> None:
        """记录一次分析运行。"""
        now = datetime.now(UTC).isoformat()

        # 全局指标
        self.total_runs += 1
        self.total_duration_ms += duration_ms
        self.avg_duration_ms = self.total_duration_ms / self.total_runs
        self.last_run_at = now
        self.last_run_sku = sku_id

        if success:
            self.successful_runs += 1
        else:
            self.failed_runs += 1
            self.last_error = error
            self.is_healthy = False

        if used_ai:
            self.ai_calls += 1
            if not success and error:
                self.ai_failures += 1

        if boundary_passed is True:
            self.boundary_passed += 1
        elif boundary_passed is False:
            self.boundary_blocked += 1

        # SKU 级指标
        sku_m = self.skus[sku_id]
        sku_m.total_runs += 1
        sku_m.total_duration_ms += duration_ms
        sku_m.last_run_at = now

        if success:
            sku_m.successful_runs += 1
        else:
            sku_m.failed_runs += 1
            sku_m.last_error = error

        if decision_type:
            sku_m.last_decision_type = decision_type

        # 保留最近 100 条记录
        self.recent_runs.append({
            "sku_id": sku_id,
            "timestamp": now,
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "decision_type": decision_type,
            "boundary_passed": boundary_passed,
            "error": error,
        })
        if len(self.recent_runs) > 100:
            self.recent_runs.pop(0)

    def get_sku_summaries(self) -> list[dict[str, Any]]:
        """获取所有 SKU 的指标摘要。"""
        return [
            {
                "sku_id": sku_id,
                "total_runs": m.total_runs,
                "successful_runs": m.successful_runs,
                "failed_runs": m.failed_runs,
                "avg_duration_ms": (
                    round(m.total_duration_ms / m.total_runs, 1)
                    if m.total_runs > 0
                    else 0
                ),
                "last_run_at": m.last_run_at,
                "last_error": m.last_error,
                "last_decision_type": m.last_decision_type,
            }
            for sku_id, m in sorted(self.skus.items())
        ]

    def to_dict(self) -> dict[str, Any]:
        """转 dict，用于 API 响应。"""
        return {
            "started_at": self.started_at,
            "uptime_seconds": round(
                (
                    datetime.now(UTC)
                    - datetime.fromisoformat(self.started_at)
                ).total_seconds()
            ),
            "is_healthy": self.is_healthy,
            "total_runs": self.total_runs,
            "successful_runs": self.successful_runs,
            "failed_runs": self.failed_runs,
            "success_rate": (
                round(self.successful_runs / self.total_runs * 100, 1)
                if self.total_runs > 0
                else 100.0
            ),
            "ai_calls": self.ai_calls,
            "ai_failures": self.ai_failures,
            "boundary_passed": self.boundary_passed,
            "boundary_blocked": self.boundary_blocked,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "avg_duration_ms": round(self.avg_duration_ms, 1),
            "last_run_at": self.last_run_at,
            "last_run_sku": self.last_run_sku,
            "last_error": self.last_error,
            "sku_count": len(self.skus),
        }


# 全局单例
_metrics = PipelineMetrics()


def get_metrics() -> PipelineMetrics:
    """获取全局分析管线监控指标。"""
    return _metrics


def reset_metrics() -> None:
    """重置监控指标（调试/测试用）。"""
    global _metrics
    _metrics = PipelineMetrics()
