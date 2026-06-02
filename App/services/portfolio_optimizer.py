"""投资组合优化器 — 跨 SKU 预算重新分配.

根据各 SKU 的 ROI、毛利率、盈亏平衡花费等绩效指标,
在遵守单 SKU 不超过总预算 20% 的约束下, 对广告预算进行跨商品优化分配.

Usage:
    optimizer = PortfolioOptimizer()
    result = optimizer.optimize(analysis_results)
"""

from __future__ import annotations

import math
from typing import Any

from App.core.logging import get_logger

logger = get_logger(__name__)

# ── 默认参数 ──────────────────────────────────────────────────
_DEFAULT_MAX_SKU_PCT = 0.20        # 单 SKU 占总预算最高比例
_DEFAULT_MIN_SKU_PCT = 0.01        # 单 SKU 最低保留比例
_DEFAULT_TOTAL_BUDGET_MULT = 1.0   # 总预算 = 当前总花费 × 倍数


# ── 绩效评分权重 ──────────────────────────────────────────────
_WEIGHT_ROI = 0.50
_WEIGHT_MARGIN = 0.30
_WEIGHT_CONVERSION = 0.20


class PortfolioOptimizer:
    """跨 SKU 预算重新分配优化器.

    接收分析管线输出的所有 SKU 分析结果, 计算最优预算分配方案,
    确保不违反单 SKU 上限约束并返回可执行的 reallocation 建议.
    """

    def __init__(
        self,
        max_sku_pct: float = _DEFAULT_MAX_SKU_PCT,
        min_sku_pct: float = _DEFAULT_MIN_SKU_PCT,
        total_budget_mult: float = _DEFAULT_TOTAL_BUDGET_MULT,
    ) -> None:
        self.max_sku_pct = max_sku_pct
        self.min_sku_pct = min_sku_pct
        self.total_budget_mult = total_budget_mult

    # ── public API ───────────────────────────────────────────

    def optimize(
        self,
        sku_analyses: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """执行跨 SKU 预算重新分配优化.

        Args:
            sku_analyses:
                ``analyze_all_skus()`` 返回的 ``results`` 列表.
                每个元素需包含 ``sku_id``, ``profit``, ``decision``.

        Returns:
            组合优化推荐 dict, 包含:
            - ``status``: "success" | "no_data" | "no_valid_skus"
            - ``total_budget``: 优化后的总预算
            - ``total_current_budget``: 当前总预算
            - ``allocations``: 各 SKU 分配明细
            - ``reallocations``: 变动建议列表
            - ``reasoning``: 中文决策理由
        """
        if not sku_analyses:
            logger.info("组合优化: 无可用的 SKU 分析数据")
            return self._empty_result("no_data", "没有可用的 SKU 数据")

        # 1. 提取有效 SKU 并计算绩效评分
        valid_skus = self._extract_valid_skus(sku_analyses)

        if not valid_skus:
            logger.info("组合优化: 无有效 SKU")
            return self._empty_result("no_valid_skus", "没有有效的 SKU 分析数据")

        # 2. 计算总预算
        total_current_budget = sum(s["current_budget"] for s in valid_skus)
        total_budget = max(total_current_budget * self.total_budget_mult, 1.0)

        # 3. 计算原始权重分配
        total_score = sum(s["score"] for s in valid_skus)

        raw_allocations: list[dict[str, Any]] = []
        for sku in valid_skus:
            if total_score > 0:
                raw_pct = sku["score"] / total_score
            else:
                raw_pct = 1.0 / len(valid_skus)
            raw_budget = total_budget * raw_pct

            raw_allocations.append({
                "sku_id": sku["sku_id"],
                "score": round(sku["score"], 4),
                "raw_pct": round(raw_pct, 4),
                "raw_budget": round(raw_budget, 2),
                "current_budget": round(sku["current_budget"], 2),
                "current_roi": round(sku["current_roi"], 4),
                "gross_margin": round(sku["gross_margin"], 4),
                "breakeven_ad_spend": round(sku["breakeven_ad_spend"], 2),
            })

        # 4. 应用 20% 上限约束, 超额部分重新分配
        constrained = self._apply_max_constraint(raw_allocations, total_budget)

        # 5. 生成 reallocation 建议
        reallocations = self._generate_reallocations(constrained)

        # 6. 获取 unallocated (由 _apply_max_constraint 设置)
        unallocated = getattr(self, "_last_unallocated", 0.0)

        # 7. 生成中文 reasoning
        reasoning = self._generate_reasoning(constrained, total_budget, total_current_budget, unallocated)

        result: dict[str, Any] = {
            "status": "success",
            "total_budget": round(total_budget, 2),
            "total_current_budget": round(total_current_budget, 2),
            "unallocated_budget": unallocated,
            "constraints": {
                "max_sku_pct": self.max_sku_pct,
                "min_sku_pct": self.min_sku_pct,
            },
            "allocations": constrained,
            "reallocations": reallocations,
            "reasoning": reasoning,
            "sku_count": len(constrained),
        }

        logger.info(
            "组合优化完成: %d SKU, 总预算 $%.2f, reallocation %d 项",
            result["sku_count"], result["total_budget"], len(reallocations),
        )
        return result

    # ── 内部方法 ─────────────────────────────────────────────

    @staticmethod
    def _compute_score(
        current_roi: float,
        gross_margin: float,
        breakeven_ad_spend: float,
    ) -> float:
        """计算单个 SKU 的绩效评分 (加权综合).

        Scoring 公式:
        - ROI 评分: min(roi / 3.0, 1.0)  (ROI >= 3 满分)
        - Margin 评分: max(margin, 0)      (毛利率为负则 0)
        - Breakeven 评分: min(breakeven / 10, 1.0) (预算规模因子)
        """
        roi_score = min(current_roi / 3.0, 1.0) if current_roi > 0 else 0.0
        margin_score = max(gross_margin, 0.0)
        breakeven_score = min(breakeven_ad_spend / 10.0, 1.0) if breakeven_ad_spend > 0 else 0.1

        score = (
            _WEIGHT_ROI * roi_score
            + _WEIGHT_MARGIN * margin_score
            + _WEIGHT_CONVERSION * breakeven_score
        )
        return max(score, 0.01)  # 保证最低分 > 0, 避免完全饿死

    def _extract_valid_skus(
        self,
        sku_analyses: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """从分析结果中提取有效 SKU 并计算评分.

        只保留 ``success=True`` 且有 profit 数据的 SKU.
        """
        valid: list[dict[str, Any]] = []

        for analysis in sku_analyses:
            if not analysis.get("success"):
                continue

            profit = analysis.get("profit")
            if not profit:
                continue

            sku_id = analysis.get("sku_id", "unknown")
            decision = analysis.get("decision") or {}
            action = decision.get("action") or {}

            # 当前预算优先从 decision.action.current_value 提取,
            # 不可用时以 breakeven_ad_spend 作为代理值
            current_budget = action.get("current_value")
            if current_budget is None or not isinstance(current_budget, (int, float)):
                current_budget = float(profit.get("breakeven_ad_spend", 0))

            current_roi = float(profit.get("current_roi", 0))
            gross_margin = float(profit.get("gross_margin", 0))
            breakeven_ad_spend = float(profit.get("breakeven_ad_spend", 0))

            score = self._compute_score(current_roi, gross_margin, breakeven_ad_spend)

            valid.append({
                "sku_id": sku_id,
                "score": score,
                "current_budget": current_budget,
                "current_roi": current_roi,
                "gross_margin": gross_margin,
                "breakeven_ad_spend": breakeven_ad_spend,
            })

        return valid

    def _apply_max_constraint(
        self,
        allocations: list[dict[str, Any]],
        total_budget: float,
    ) -> list[dict[str, Any]]:
        """对分配结果应用单 SKU 上限约束.

        迭代过程:
        1. 将所有超限 SKU 固定在 max_sku_pct
        2. 剩余预算按评分比例重新分配给未超限 SKU
        3. 当所有 SKU 均触及上限时, 多余预算标记为 unallocated

        当约束数学上无法完全分配 (例如 3 个 SKU 各限 20%, 最多用 60%),
        剩余预算以 ``unallocated`` 字段返回.
        """
        if total_budget <= 0 or not allocations:
            return allocations

        constrained = [dict(a) for a in allocations]

        max_budget = total_budget * self.max_sku_pct
        min_budget = total_budget * self.min_sku_pct

        # 迭代修剪 (最多 10 轮收敛)
        for _iteration in range(10):
            capped_skus = [a for a in constrained if a["raw_budget"] > max_budget]
            if not capped_skus:
                break

            # 固定超限 SKU 到上限
            for a in capped_skus:
                a["raw_budget"] = max_budget

            # 计算剩余预算
            used_budget = sum(a["raw_budget"] for a in constrained)
            remaining = total_budget - used_budget

            if remaining <= 0.01:
                break

            # 未超限 SKU 按评分比例获得剩余预算
            uncapped = [a for a in constrained if a["raw_budget"] < max_budget]
            if not uncapped:
                # 所有 SKU 均已达上限, 剩余预算无法分配
                break

            uncapped_score = sum(a["score"] for a in uncapped) or 1.0

            for a in uncapped:
                extra = remaining * (a["score"] / uncapped_score)
                a["raw_budget"] += extra

        # 计算未分配预算
        allocated_budget = sum(a["raw_budget"] for a in constrained)
        unallocated = round(max(total_budget - allocated_budget, 0.0), 2)

        # 应用最低预算约束
        for a in constrained:
            if a["raw_budget"] < min_budget and len(constrained) > 1:
                a["raw_budget"] = min_budget

        # 最终归一化 — 仅当未分配接近于 0 时微调
        if unallocated <= 0.01:
            re_allocated = sum(a["raw_budget"] for a in constrained)
            if re_allocated > 0 and abs(re_allocated - total_budget) > 0.01:
                scale = total_budget / re_allocated
                for a in constrained:
                    a["raw_budget"] = round(a["raw_budget"] * scale, 2)

        for a in constrained:
            a["raw_budget"] = round(a["raw_budget"], 2)

        # 重组为最终格式
        result: list[dict[str, Any]] = []
        for a in constrained:
            pct = a["raw_budget"] / total_budget if total_budget > 0 else 0.0
            result.append({
                "sku_id": a["sku_id"],
                "score": a["score"],
                "current_budget": a["current_budget"],
                "recommended_budget": a["raw_budget"],
                "pct_of_total": round(pct, 4),
                "change": round(a["raw_budget"] - a["current_budget"], 2),
                "current_roi": a["current_roi"],
                "gross_margin": a["gross_margin"],
                "breakeven_ad_spend": a["breakeven_ad_spend"],
            })

        # 将 unallocated 注入到结果对象上供外部读取
        self._last_unallocated = unallocated

        return result

    @staticmethod
    def _generate_reallocations(
        allocations: list[dict[str, Any]],
    ) -> list[dict[str, str | float]]:
        """生成变动建议列表 (仅包含预算需要调整的 SKU)."""
        reallocations: list[dict[str, str | float]] = []

        for a in allocations:
            change = a["change"]
            if abs(change) < 0.01:
                continue

            action_type = "increase" if change > 0 else "decrease"
            reason_parts: list[str] = []

            roi = a["current_roi"]
            margin = a["gross_margin"]

            if action_type == "increase":
                if roi > 2.0:
                    reason_parts.append("ROI 表现优秀")
                elif roi > 1.0:
                    reason_parts.append("ROI 为正且有提升空间")
                else:
                    reason_parts.append("预算基础较低, 需保障最低投放")
                if margin > 0.3:
                    reason_parts.append("毛利率健康")
            else:
                if roi < 1.0:
                    reason_parts.append("ROI 偏低")
                elif roi < 1.5:
                    reason_parts.append("ROI 表现一般")
                else:
                    reason_parts.append("已达到 20% 上限, 超额部分重新分配")
                if margin < 0.1:
                    reason_parts.append("毛利率偏低")
                reason_parts.append("调减预算用于再分配")

            reallocations.append({
                "sku_id": a["sku_id"],
                "action": action_type,
                "current_budget": a["current_budget"],
                "recommended_budget": a["recommended_budget"],
                "change": a["change"],
                "reason": "，".join(reason_parts),
            })

        return reallocations

    @staticmethod
    def _generate_reasoning(
        allocations: list[dict[str, Any]],
        total_budget: float,
        total_current_budget: float,
        unallocated: float = 0.0,
    ) -> str:
        """生成中文决策理由."""
        n = len(allocations)
        increases = sum(1 for a in allocations if a["change"] > 0)
        decreases = sum(1 for a in allocations if a["change"] < 0)
        unchanged = sum(1 for a in allocations if abs(a["change"]) < 0.01)

        parts = [
            f"对 {n} 个 SKU 完成预算优化分配",
            f"总预算 ${total_budget:.2f}",
        ]

        if increases > 0:
            parts.append(f"调增 {increases} 个 SKU")
        if decreases > 0:
            parts.append(f"调减 {decreases} 个 SKU")
        if unchanged > 0:
            parts.append(f"维持 {unchanged} 个 SKU 不变")

        parts.append(
            f"单 SKU 上限约束为 {_DEFAULT_MAX_SKU_PCT:.0%}"
        )

        # 检查是否有 SKU 触及上限
        capped = [a for a in allocations if a["pct_of_total"] >= _DEFAULT_MAX_SKU_PCT - 0.001]
        if capped:
            capped_count = len(capped)
            capped_ids = ", ".join(a["sku_id"] for a in capped)
            parts.append(f"{capped_count} 个 SKU 触及上限 ({capped_ids})")

        if unallocated > 0.01:
            parts.append(f"约束限制导致 ${unallocated:.2f} 未能分配")

        return "，".join(parts)

    @staticmethod
    def _empty_result(
        status: str,
        reasoning: str,
    ) -> dict[str, Any]:
        """返回空结果."""
        return {
            "status": status,
            "total_budget": 0.0,
            "total_current_budget": 0.0,
            "unallocated_budget": 0.0,
            "constraints": {
                "max_sku_pct": _DEFAULT_MAX_SKU_PCT,
                "min_sku_pct": _DEFAULT_MIN_SKU_PCT,
            },
            "allocations": [],
            "reallocations": [],
            "reasoning": reasoning,
            "sku_count": 0,
        }


def portfolio_optimizer_smoke_test() -> dict[str, Any]:
    """快速冒烟测试: 验证模块导入和核心逻辑可正常运行 (无需 DB).

    Returns:
        {"passed": bool, "details": dict}
    """
    details: dict[str, Any] = {}

    # 1. 实例化
    try:
        optimizer = PortfolioOptimizer()
        details["instantiate"] = True
    except Exception as exc:
        details["instantiate"] = f"FAILED: {exc}"

    # 2. 空输入
    try:
        result = optimizer.optimize([])
        details["empty_input"] = result["status"]
    except Exception as exc:
        details["empty_input"] = f"FAILED: {exc}"

    # 3. 模拟 4 SKU 数据
    mock_analyses = [
        {
            "sku_id": "SKU-001",
            "success": True,
            "profit": {
                "current_roi": 3.5,
                "gross_margin": 0.40,
                "breakeven_ad_spend": 5.0,
            },
            "decision": {
                "action": {
                    "field": "daily_budget",
                    "current_value": 10.0,
                },
            },
        },
        {
            "sku_id": "SKU-002",
            "success": True,
            "profit": {
                "current_roi": 1.2,
                "gross_margin": 0.15,
                "breakeven_ad_spend": 3.0,
            },
            "decision": {
                "action": {
                    "field": "daily_budget",
                    "current_value": 8.0,
                },
            },
        },
        {
            "sku_id": "SKU-003",
            "success": True,
            "profit": {
                "current_roi": 0.8,
                "gross_margin": 0.05,
                "breakeven_ad_spend": 2.0,
            },
            "decision": {
                "action": {
                    "field": "daily_budget",
                    "current_value": 5.0,
                },
            },
        },
        {
            "sku_id": "SKU-004",
            "success": True,
            "profit": {
                "current_roi": 0.3,
                "gross_margin": 0.02,
                "breakeven_ad_spend": 1.5,
            },
            "decision": {
                "action": {
                    "field": "daily_budget",
                    "current_value": 3.0,
                },
            },
        },
    ]

    try:
        result = optimizer.optimize(mock_analyses)
        details["mock_4_skus_status"] = result["status"]
        details["mock_4_skus_count"] = result["sku_count"]
        details["mock_4_skus_budget"] = result["total_budget"]
        details["mock_4_skus_reallocations"] = len(result["reallocations"])
    except Exception as exc:
        details["mock_4_skus"] = f"FAILED: {exc}"

    # 4. 验证 20% 上限约束
    if result.get("allocations"):
        max_pct = max(a["pct_of_total"] for a in result["allocations"])
        details["max_pct_observed"] = max_pct
        details["max_pct_constraint_ok"] = max_pct <= _DEFAULT_MAX_SKU_PCT + 0.001
    else:
        details["max_pct_observed"] = "N/A"
        details["max_pct_constraint_ok"] = False

    # 5. 验证输出非空
    has_recommendations = (
        result.get("status") == "success"
        and len(result.get("allocations", [])) > 0
    )
    details["has_non_empty_recommendations"] = has_recommendations

    all_ok = (
        details.get("instantiate") is True
        and details.get("empty_input") == "no_data"
        and details.get("mock_4_skus_status") == "success"
        and isinstance(details.get("mock_4_skus_count"), int)
        and details.get("mock_4_skus_count") > 0
        and isinstance(details.get("mock_4_skus_budget"), (int, float))
        and details.get("mock_4_skus_budget", 0) > 0
        and details.get("max_pct_constraint_ok") is True
        and details.get("has_non_empty_recommendations") is True
    )
    logger.info(
        "portfolio_optimizer_smoke_test: %s — %s",
        "PASSED" if all_ok else "FAILED",
        details,
    )
    return {"passed": all_ok, "details": details}
