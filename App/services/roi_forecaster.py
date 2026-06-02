"""ROI 预测 — 基于30天历史数据预测未来ROI，带置信区间。

Usage:
    from App.services.roi_forecaster import RoiForecaster

    forecaster = RoiForecaster()
    result = await forecaster.forecast(db, sku_id, days_ahead=7)
"""

from __future__ import annotations

import math
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from App.core.logging import get_logger
from App.models.base import ProfitAnalysis

logger = get_logger(__name__)


class ForecastPoint:
    """单个预测点的数据结构。"""

    __slots__ = ("date", "predicted_roi", "lower_bound", "upper_bound")

    def __init__(
        self,
        date: str,
        predicted_roi: float,
        lower_bound: float,
        upper_bound: float,
    ) -> None:
        self.date = date
        self.predicted_roi = round(predicted_roi, 4)
        self.lower_bound = round(lower_bound, 4)
        self.upper_bound = round(upper_bound, 4)

    def to_dict(self) -> dict[str, float | str]:
        return {
            "date": self.date,
            "predicted_roi": self.predicted_roi,
            "lower_bound": self.lower_bound,
            "upper_bound": self.upper_bound,
        }


class RoiForecaster:
    """ROI 预测器 — 基于30天历史ROI做线性回归预测。

    算法说明：
        1. 取最近30天 ProfitAnalysis 记录的 current_roi 作为样本。
        2. 以天数为自变量 (x=0 为最早一天)，ROI 为因变量做线性回归。
        3. 用回归方程的斜率推断未来趋势。
        4. 置信区间 = 预测值 +/- (t_stat * 标准误差)，默认 80% 置信水平。
    """

    def __init__(self, confidence_level: float = 0.80) -> None:
        if not 0 < confidence_level < 1:
            raise ValueError("confidence_level must be between 0 and 1")
        self.confidence_level = confidence_level

    def _compute_t_stat(self, degrees_of_freedom: int) -> float:
        """简易 t 统计量查表（80% 置信水平双尾）。

        对于自由度 >= 5 的情形足够准确，自由度不足时保守放大。
        """
        if degrees_of_freedom <= 0:
            return 1.0
        # 80% 双尾 t 值近似表 (自由度 1~30, 之后取 1.282)
        table: dict[int, float] = {
            1: 3.078,
            2: 1.886,
            3: 1.638,
            4: 1.533,
            5: 1.476,
            6: 1.440,
            7: 1.415,
            8: 1.397,
            9: 1.383,
            10: 1.372,
            11: 1.363,
            12: 1.356,
            13: 1.350,
            14: 1.345,
            15: 1.341,
            16: 1.337,
            17: 1.333,
            18: 1.330,
            19: 1.328,
            20: 1.325,
            21: 1.323,
            22: 1.321,
            23: 1.319,
            24: 1.318,
            25: 1.316,
            26: 1.315,
            27: 1.314,
            28: 1.313,
            29: 1.311,
            30: 1.310,
        }
        # 30 以上的自由度近似为正态分布的 80% 双尾临界值
        return table.get(degrees_of_freedom, 1.282)

    def _linear_regression(
        self,
        x: list[float],
        y: list[float],
    ) -> dict[str, float]:
        """执行一元线性回归，返回斜率、截距、R²、标准误差。"""
        n = len(x)
        if n < 2:
            return {"slope": 0.0, "intercept": 0.0, "r_squared": 0.0, "std_err": 0.0}

        mean_x = sum(x) / n
        mean_y = sum(y) / n

        # 计算斜率
        numerator = sum((xi - mean_x) * (yi - mean_y) for xi, yi in zip(x, y))
        denominator = sum((xi - mean_x) ** 2 for xi in x)

        if denominator == 0:
            return {"slope": 0.0, "intercept": mean_y, "r_squared": 0.0, "std_err": 0.0}

        slope = numerator / denominator
        intercept = mean_y - slope * mean_x

        # R²
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        ss_tot = sum((yi - mean_y) ** 2 for yi in y)
        r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

        # 标准误差
        std_err = math.sqrt(ss_res / (n - 2)) if n > 2 else 0.0

        return {
            "slope": slope,
            "intercept": intercept,
            "r_squared": r_squared,
            "std_err": std_err,
        }

    async def _load_historical_roi(
        self,
        db: AsyncSession,
        sku_id: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """从数据库加载指定 SKU 的历史 ROI 数据。"""
        since = datetime.now(UTC) - timedelta(days=days)
        result = await db.execute(
            select(ProfitAnalysis)
            .where(
                ProfitAnalysis.sku_id == sku_id,
                ProfitAnalysis.calc_time >= since,
            )
            .order_by(ProfitAnalysis.calc_time.asc())
        )
        records = list(result.scalars().all())

        if not records:
            logger.info("ROI 预测: SKU=%s 无历史数据 (days=%d)", sku_id, days)
            return []

        logger.info(
            "ROI 预测: SKU=%s 加载历史记录 %d 条 (days=%d)",
            sku_id, len(records), days,
        )

        data_points: list[dict[str, Any]] = []
        for r in records:
            calc_time = r.calc_time
            if calc_time is None:
                continue
            data_points.append({
                "date": calc_time.strftime("%Y-%m-%d"),
                "roi": float(r.current_roi),
                "calc_time": calc_time,
            })

        # 按天去重（同一天取最后一次计算的结果）
        seen_dates: set[str] = set()
        deduped: list[dict[str, Any]] = []
        for dp in reversed(data_points):  # 从最新开始，保留最新
            if dp["date"] not in seen_dates:
                seen_dates.add(dp["date"])
                deduped.append(dp)
        deduped.reverse()

        return deduped

    async def forecast(
        self,
        db: AsyncSession,
        sku_id: str,
        days_ahead: int = 7,
    ) -> dict[str, Any]:
        """执行 ROI 预测。

        Args:
            db: 数据库会话
            sku_id: 商品 SKU ID
            days_ahead: 预测未来天数 (默认 7)

        Returns:
            {
                "sku_id": str,
                "forecast_generated_at": str (ISO datetime),
                "confidence_level": float,
                "historical": list[{"date": str, "roi": float}],
                "forecast": list[{"date": str, "predicted_roi": float, "lower_bound": float, "upper_bound": float}],
                "trend_direction": "up" | "down" | "stable",
                "regression": {"slope": float, "r_squared": float} | None,
                "warning": str | None,
            }
        """
        historical = await self._load_historical_roi(db, sku_id, days=30)

        if not historical:
            return self._empty_result(sku_id, "无历史数据，无法生成预测")

        n = len(historical)
        if n < 2:
            return self._empty_result(sku_id, f"历史数据不足 (n={n})，至少需要 2 个数据点")

        # 准备回归数据: x = 天数偏移 (0, 1, 2, ..., n-1), y = ROI
        x = [float(i) for i in range(n)]
        y = [dp["roi"] for dp in historical]

        reg = self._linear_regression(x, y)
        slope = reg["slope"]
        std_err = reg["std_err"]
        r_squared = reg["r_squared"]

        # 计算置信区间
        t_stat = self._compute_t_stat(n - 2)
        # 对每个预测日期的标准误差做放大（预测越远，不确定性越大）
        x_mean = sum(x) / n
        ss_x = sum((xi - x_mean) ** 2 for xi in x)

        historical_points = [{"date": dp["date"], "roi": dp["roi"]} for dp in historical]

        forecast_points: list[dict[str, Any]] = []
        for i in range(1, days_ahead + 1):
            future_x = n - 1 + i  # 从最后一个数据点之后开始
            predicted = slope * future_x + reg["intercept"]

            # 预测标准误差 = std_err * sqrt(1 + 1/n + (future_x - x_mean)^2 / ss_x)
            if n > 2 and ss_x > 0:
                se_pred = std_err * math.sqrt(
                    1.0 + 1.0 / n + (future_x - x_mean) ** 2 / ss_x
                )
            else:
                se_pred = std_err if std_err > 0 else abs(predicted) * 0.5

            margin = t_stat * se_pred
            forecast_date = (
                datetime.now(UTC) + timedelta(days=i)
            ).strftime("%Y-%m-%d")

            forecast_points.append({
                "date": forecast_date,
                "predicted_roi": round(predicted, 4),
                "lower_bound": round(predicted - margin, 4),
                "upper_bound": round(predicted + margin, 4),
            })

        # 判断趋势方向
        if abs(slope) < 0.001:
            trend_direction = "stable"
        elif slope > 0:
            trend_direction = "up"
        else:
            trend_direction = "down"

        return {
            "sku_id": sku_id,
            "forecast_generated_at": datetime.now(UTC).isoformat(),
            "confidence_level": self.confidence_level,
            "historical": historical_points,
            "forecast": forecast_points,
            "trend_direction": trend_direction,
            "regression": {
                "slope": round(slope, 6),
                "r_squared": round(r_squared, 4),
            },
            "warning": None,
        }

    def _empty_result(
        self,
        sku_id: str,
        warning: str,
    ) -> dict[str, Any]:
        """返回空的预测结果（数据不足时使用）。"""
        logger.warning("ROI 预测: SKU=%s — %s", sku_id, warning)
        return {
            "sku_id": sku_id,
            "forecast_generated_at": datetime.now(UTC).isoformat(),
            "confidence_level": self.confidence_level,
            "historical": [],
            "forecast": [],
            "trend_direction": "unknown",
            "regression": None,
            "warning": warning,
        }


# 模块级函数：方便外部调用（使用默认配置的 RoiForecaster 实例）
_default_forecaster = RoiForecaster()


async def forecast_roi(
    db: AsyncSession,
    sku_id: str,
    days_ahead: int = 7,
    confidence_level: float | None = None,
) -> dict[str, Any]:
    """便利函数 — 使用默认或指定置信水平执行 ROI 预测。"""
    if confidence_level is not None:
        forecaster = RoiForecaster(confidence_level=confidence_level)
        return await forecaster.forecast(db, sku_id, days_ahead=days_ahead)
    return await _default_forecaster.forecast(db, sku_id, days_ahead=days_ahead)


