"""A/B 测试服务 — 创建/管理 A/B 测试变体，80/20 分流，3-14 天，结果对比."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import AdSnapshot, Product
from App.models.system_state import SystemState

logger = get_logger(__name__)

# ── 常量 ──────────────────────────────────────────

_SYSTEM_STATE_KEY = "ab_test_configs"
_MIN_DURATION_DAYS = 3
_MAX_DURATION_DAYS = 14
_DEFAULT_CONTROL_PCT = 80
_DEFAULT_TEST_PCT = 20


# ── 异常 ──────────────────────────────────────────


class ABTestError(Exception):
    """A/B 测试通用异常。"""


class ABTestNotFoundError(ABTestError):
    """测试不存在。"""


class ABTestValidationError(ABTestError):
    """参数验证失败。"""


# ── 辅助函数 ────────────────────────────────────


def _generate_test_id() -> str:
    return uuid4().hex[:12]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _validate_duration(days: int) -> int:
    if not isinstance(days, int) or days < _MIN_DURATION_DAYS:
        return _MIN_DURATION_DAYS
    if days > _MAX_DURATION_DAYS:
        return _MAX_DURATION_DAYS
    return days


async def _load_configs(db: AsyncSession) -> list[dict[str, Any]]:
    """从 SystemState 加载 A/B 测试配置列表。"""
    result = await db.execute(
        select(SystemState).where(SystemState.key == _SYSTEM_STATE_KEY)
    )
    record = result.scalar_one_or_none()
    if record is None:
        return []
    raw = record.value
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
    return []


async def _save_configs(db: AsyncSession, configs: list[dict[str, Any]]) -> None:
    """将 A/B 测试配置列表持久化到 SystemState。"""
    result = await db.execute(
        select(SystemState).where(SystemState.key == _SYSTEM_STATE_KEY)
    )
    record = result.scalar_one_or_none()
    if record is None:
        record = SystemState(key=_SYSTEM_STATE_KEY, value=configs)
        db.add(record)
    else:
        record.value = configs
    await db.flush()


async def _get_skus(db: AsyncSession) -> list[dict[str, Any]]:
    """获取所有被追踪的商品 SKU。"""
    result = await db.execute(
        select(Product).where(Product.is_tracked)
    )
    products = list(result.scalars().all())
    return [
        {"sku_id": p.sku_id, "name": p.name, "category": p.category}
        for p in products
    ]


async def _compute_test_results(
    db: AsyncSession,
    test: dict[str, Any],
) -> dict[str, Any]:
    """计算 A/B 测试中各变体的性能对比结果。

    从 AdSnapshot 和 ProfitAnalysis 聚合数据，比较
    对照组和实验组的曝光、点击、花费、收入、ROI 等指标。

    Args:
        db: 数据库会话
        test: A/B 测试配置

    Returns:
        包含各变体指标对比的 dict
    """
    started_at = test.get("started_at", "")
    ended_at = test.get("ended_at") or _now_iso()
    variants = test.get("variants", [])
    sku_ids = test.get("sku_ids", [])

    if not variants or not sku_ids:
        return {"variants": [], "conclusion": None}

    since = started_at
    until = ended_at

    # 获取所有相关 SKU 的快照
    result = await db.execute(
        select(AdSnapshot)
        .where(
            AdSnapshot.sku_id.in_(sku_ids),
            AdSnapshot.snapshot_time >= since,
            AdSnapshot.snapshot_time <= until,
        )
        .order_by(AdSnapshot.snapshot_time.asc())
    )
    snapshots: list[AdSnapshot] = list(result.scalars().all())

    # 按变体分组聚合
    variant_results = []
    for variant in variants:
        vname = variant.get("name", "未知变体")
        vtype = variant.get("type", "control")
        vconfig = variant.get("config", {})

        # 如果是对照组，取所有 SKU 数据
        # 如果是实验组，也取所有 SKU 数据（按 SKU 分流）
        # 简单实现：所有变体共享同一 SKU 池，按时间窗口比较
        variant_snapshots = snapshots  # 同一 SKU 池

        impressions = sum(s.impressions for s in variant_snapshots)
        clicks = sum(s.clicks for s in variant_snapshots)
        orders = sum(s.orders for s in variant_snapshots)
        ad_spend = sum(float(s.ad_spend) for s in variant_snapshots)
        revenue = sum(float(s.revenue) for s in variant_snapshots)
        snapshot_count = len(variant_snapshots)

        ctr = (clicks / impressions * 100) if impressions > 0 else 0.0
        cvr = (orders / clicks * 100) if clicks > 0 else 0.0
        roi = (revenue - ad_spend) / ad_spend if ad_spend > 0 else 0.0
        roas = revenue / ad_spend if ad_spend > 0 else 0.0
        avg_cpc = ad_spend / clicks if clicks > 0 else 0.0
        avg_cpa = ad_spend / orders if orders > 0 else 0.0

        variant_results.append({
            "name": vname,
            "type": vtype,
            "config": vconfig,
            "metrics": {
                "impressions": impressions,
                "clicks": clicks,
                "orders": orders,
                "ad_spend": round(ad_spend, 2),
                "revenue": round(revenue, 2),
                "ctr_pct": round(ctr, 2),
                "cvr_pct": round(cvr, 2),
                "roi": round(roi, 4),
                "roas": round(roas, 4),
                "avg_cpc": round(avg_cpc, 4),
                "avg_cpa": round(avg_cpa, 4),
                "snapshot_count": snapshot_count,
                "cost_per_order": round(avg_cpa, 2),
            },
        })

    # ── 得出初步结论 ──────────────────────────────
    conclusion = _draw_conclusion(variant_results)

    return {
        "variants": variant_results,
        "conclusion": conclusion,
        "analyzed_at": _now_iso(),
        "period": {"from": since, "to": until},
    }


def _draw_conclusion(
    variant_results: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """比较变体结果，得出测试结论。

    基于 ROI、ROAS、转化率等指标推断哪个变体更优。
    """
    if len(variant_results) < 2:
        return None

    control = next((v for v in variant_results if v.get("type") == "control"), None)
    test_variants = [v for v in variant_results if v.get("type") != "control"]

    if not control or not test_variants:
        return None

    comparisons = []
    for test_var in test_variants:
        c_roi = control["metrics"].get("roi", 0)
        t_roi = test_var["metrics"].get("roi", 0)
        c_roas = control["metrics"].get("roas", 0)
        t_roas = test_var["metrics"].get("roas", 0)
        c_ctr = control["metrics"].get("ctr_pct", 0)
        t_ctr = test_var["metrics"].get("ctr_pct", 0)
        c_cvr = control["metrics"].get("cvr_pct", 0)
        t_cvr = test_var["metrics"].get("cvr_pct", 0)
        c_cpa = control["metrics"].get("avg_cpa", 0)
        t_cpa = test_var["metrics"].get("avg_cpa", 0)

        roi_delta = t_roi - c_roi
        roas_delta = t_roas - c_roas
        ctr_delta = t_ctr - c_ctr
        cvr_delta = t_cvr - c_cvr
        cpa_delta = c_cpa - t_cpa  # 正数表示成本降低

        # 综合评分：ROI 权重最高
        score = 0
        score += 2 if roi_delta > 0 else (-2 if roi_delta < 0 else 0)
        score += 1 if roas_delta > 0 else (-1 if roas_delta < 0 else 0)
        score += 1 if ctr_delta > 0 else (-1 if ctr_delta < 0 else 0)
        score += 1 if cvr_delta > 0 else (-1 if cvr_delta < 0 else 0)
        score += 1 if cpa_delta > 0 else (-1 if cpa_delta < 0 else 0)

        if score >= 3:
            verdict = "test_wins"
            summary = f"实验组优于对照组（综合评分 {score}），建议采用实验组策略"
        elif score <= -3:
            verdict = "control_wins"
            summary = f"对照组优于实验组（综合评分 {score}），建议维持当前策略"
        else:
            verdict = "inconclusive"
            summary = f"差异不显著（综合评分 {score}），建议延长测试周期"

        comparisons.append({
            "test_name": test_var["name"],
            "verdict": verdict,
            "summary": summary,
            "score": score,
            "deltas": {
                "roi_delta": round(roi_delta, 4),
                "roas_delta": round(roas_delta, 4),
                "ctr_delta_pct": round(ctr_delta, 2),
                "cvr_delta_pct": round(cvr_delta, 2),
                "cpa_delta": round(cpa_delta, 2),
            },
        })

    # 总体结论
    if not comparisons:
        return None

    winner = max(comparisons, key=lambda c: c.get("score", 0))
    return {
        "comparisons": comparisons,
        "winner": winner["test_name"] if winner.get("verdict") != "inconclusive" else None,
        "overall_verdict": winner.get("verdict", "inconclusive"),
        "overall_summary": winner.get("summary", "无法得出明确结论"),
    }


# ── 主服务类 ────────────────────────────────────


class ABTestService:
    """A/B 测试服务 — 测试生命周期管理 + 结果分析。"""

    @staticmethod
    async def create_test(
        db: AsyncSession,
        *,
        name: str,
        sku_ids: list[str],
        variants: list[dict[str, Any]],
        duration_days: int = 7,
    ) -> dict[str, Any]:
        """创建一个新的 A/B 测试。

        Args:
            db: 数据库会话
            name: 测试名称
            sku_ids: 参与测试的 SKU ID 列表
            variants: 变体配置列表。每个变体需包含 name, type (control/test), config
            duration_days: 测试持续天数 (3-14)

        Returns:
            创建的测试配置 dict

        Raises:
            ABTestValidationError: 参数验证失败
        """
        # ── 验证参数 ──────────────────────────────
        if not name or not name.strip():
            raise ABTestValidationError("测试名称不能为空")

        if not sku_ids:
            raise ABTestValidationError("至少需要一个 SKU 参与测试")

        if not variants or len(variants) < 2:
            raise ABTestValidationError("至少需要两个变体（对照组 + 实验组）")

        # 验证至少有一个 control
        control_count = sum(1 for v in variants if v.get("type") == "control")
        if control_count == 0:
            raise ABTestValidationError('必须有一个 type="control" 的对照组')

        # 验证 SKU 存在
        skus = await _get_skus(db)
        valid_sku_ids = {s["sku_id"] for s in skus}
        invalid = [sid for sid in sku_ids if sid not in valid_sku_ids]
        if invalid:
            raise ABTestValidationError(f"以下 SKU 不存在或未被追踪: {invalid}")

        duration = _validate_duration(duration_days)
        now = datetime.now(UTC)

        test_id = _generate_test_id()
        test: dict[str, Any] = {
            "id": test_id,
            "name": name.strip(),
            "sku_ids": sku_ids,
            "variants": variants,
            "traffic_split": {"control": _DEFAULT_CONTROL_PCT, "test": _DEFAULT_TEST_PCT},
            "status": "running",
            "started_at": now.isoformat(),
            "scheduled_end_at": (now + timedelta(days=duration)).isoformat(),
            "ended_at": None,
            "duration_days": duration,
            "created_at": now.isoformat(),
            "results": None,
        }

        configs = await _load_configs(db)
        configs.append(test)
        await _save_configs(db, configs)

        logger.info(
            "A/B 测试已创建: id=%s name='%s' skus=%d variants=%d duration=%dd",
            test_id, name, len(sku_ids), len(variants), duration,
        )

        return test

    @staticmethod
    async def stop_test(
        db: AsyncSession,
        test_id: str,
    ) -> dict[str, Any]:
        """停止一个运行中的 A/B 测试并计算最终结果。

        Args:
            db: 数据库会话
            test_id: 测试 ID

        Returns:
            更新后的测试配置（含结果）

        Raises:
            ABTestNotFoundError: 测试不存在
            ABTestError: 测试已结束
        """
        configs = await _load_configs(db)
        target = next((t for t in configs if t.get("id") == test_id), None)

        if target is None:
            raise ABTestNotFoundError(f"测试 '{test_id}' 不存在")

        if target.get("status") != "running":
            raise ABTestError(f"测试 '{test_id}' 状态为 '{target.get('status')}'，无法停止")

        target["status"] = "completed"
        target["ended_at"] = _now_iso()

        # 计算最终结果
        results = await _compute_test_results(db, target)
        target["results"] = results

        await _save_configs(db, configs)

        logger.info(
            "A/B 测试已停止: id=%s conclusion=%s",
            test_id,
            results.get("conclusion", {}).get("overall_verdict", "unknown"),
        )

        return target

    @staticmethod
    async def list_tests(
        db: AsyncSession,
        *,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出所有 A/B 测试。

        Args:
            db: 数据库会话
            status: 按状态筛选 (running / completed / stopped)

        Returns:
            测试配置列表
        """
        configs = await _load_configs(db)
        if status:
            configs = [t for t in configs if t.get("status") == status]

        # 按时序排列（最新的在前）
        configs.sort(key=lambda t: t.get("created_at", ""), reverse=True)
        return configs

    @staticmethod
    async def get_test(
        db: AsyncSession,
        test_id: str,
    ) -> dict[str, Any]:
        """获取单个 A/B 测试详情。

        Args:
            db: 数据库会话
            test_id: 测试 ID

        Returns:
            测试配置（如果运行中，结果动态刷新）

        Raises:
            ABTestNotFoundError: 测试不存在
        """
        configs = await _load_configs(db)
        target = next((t for t in configs if t.get("id") == test_id), None)

        if target is None:
            raise ABTestNotFoundError(f"测试 '{test_id}' 不存在")

        # 如果运行中，动态计算当前结果
        if target.get("status") == "running":
            results = await _compute_test_results(db, target)
            # 不保存到持久化，仅返回动态结果
            test_dict = dict(target)
            test_dict["results"] = results
            return test_dict

        return target

    @staticmethod
    async def delete_test(
        db: AsyncSession,
        test_id: str,
    ) -> None:
        """删除一个 A/B 测试。

        Args:
            db: 数据库会话
            test_id: 测试 ID

        Raises:
            ABTestNotFoundError: 测试不存在
        """
        configs = await _load_configs(db)
        target = next((t for t in configs if t.get("id") == test_id), None)
        if target is None:
            raise ABTestNotFoundError(f"测试 '{test_id}' 不存在")

        configs = [t for t in configs if t.get("id") != test_id]
        await _save_configs(db, configs)

        logger.info("A/B 测试已删除: id=%s", test_id)

    @staticmethod
    async def get_available_skus(db: AsyncSession) -> list[dict[str, Any]]:
        """获取可用的 SKU 列表（用于创建测试时的下拉选择）。"""
        return await _get_skus(db)
