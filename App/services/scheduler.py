"""采集任务 & 报告调度器 — APScheduler 定时触发。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from App.core.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

scheduler = AsyncIOScheduler()

COLLECTION_INTERVAL_MINUTES: int = 30  # 默认每30分钟采集一次


# ── 报告调度数据结构 ─────────────────────────────


@dataclass
class ReportSchedule:
    """一条报告定时生成配置。"""

    job_id: str
    report_type: str  # "roi_negative" | "campaign_close" | "scheduled"
    sku_id: str
    cron_expr: str  # e.g. "0 8 * * *" (every day at 8am)
    output_format: str = "pdf"  # "pdf" | "csv"
    channels: list[str] = field(default_factory=list)
    title: str = ""
    enabled: bool = True
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "report_type": self.report_type,
            "sku_id": self.sku_id,
            "cron_expr": self.cron_expr,
            "output_format": self.output_format,
            "channels": list(self.channels),
            "title": self.title,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


# ── 采集调度器 ──────────────────────────────────


class CollectionScheduler:
    """管理定时采集任务的启动/停止/状态查询。"""

    def __init__(self, db_session_factory: callable) -> None:
        self._db_factory = db_session_factory
        self._job_id: str | None = None
        self._last_result: dict | None = None

    async def _collection_job(self) -> None:
        """定时任务回调。"""
        from App.services.alert_service import raise_alert
        from App.services.cookie_manager import CookieManager
        from App.services.data_collector import collect_ad_data

        async with self._db_factory() as db:
            cookie_mgr = CookieManager(db)
            try:
                result = await collect_ad_data(db, cookie_mgr, headless=True)
                self._last_result = result

                if result.get("status") == "error":
                    error_code = (result.get("error") or {}).get("code", "UNKNOWN")
                    error_msg = (result.get("error") or {}).get("message", "未知错误")
                    if error_code == "COOKIE_MISSING":
                        await raise_alert(
                            db,
                            "collection_skipped",
                            f"采集跳过: {error_msg}",
                            severity="warning",
                        )
                    elif error_code == "GLOBAL_STOP":
                        logger.info("采集跳过: 全局停止已启用")
                    else:
                        await raise_alert(
                            db,
                            "collection_error",
                            f"数据采集失败: {error_msg}",
                            severity="warning",
                        )
                else:
                    logger.info(
                        "采集完成: %d 条广告数据, %d 条价格数据, 耗时 %.1f 秒",
                        result.get("ad_count", 0),
                        result.get("price_count", 0),
                        result.get("duration_seconds", 0),
                    )
            except Exception as exc:
                self._last_result = {"success": False, "error": str(exc)}
                await raise_alert(
                    db,
                    "collection_crash",
                    f"采集任务崩溃: {exc}",
                    severity="critical",
                )

    def start(self, interval_minutes: int = COLLECTION_INTERVAL_MINUTES) -> None:
        """启动定时采集。"""
        if self._job_id is not None:
            return  # 已经在运行

        self._job_id = f"collection_{id(self)}"
        scheduler.add_job(
            self._collection_job,
            trigger=IntervalTrigger(minutes=interval_minutes),
            id=self._job_id,
            name="数据采集",
            replace_existing=True,
            misfire_grace_time=60,
        )
        if not scheduler.running:
            scheduler.start()
        logger.info("定时采集已启动: 每 %d 分钟执行一次", interval_minutes)

    def stop(self) -> None:
        """停止定时采集。"""
        if self._job_id is not None:
            scheduler.remove_job(self._job_id)
            self._job_id = None
        if scheduler.running:
            scheduler.shutdown(wait=False)
        logger.info("定时采集已停止")

    @property
    def last_result(self) -> dict | None:
        return self._last_result

    @property
    def is_running(self) -> bool:
        return self._job_id is not None


# ── 报告调度器 ──────────────────────────────────


def _parse_cron(cron_expr: str) -> CronTrigger:
    """将 cron 表达式解析为 APScheduler CronTrigger。

    支持标准 5 字段格式: minute hour day month day_of_week
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        msg = f"Invalid cron expression: {cron_expr!r} (expected 5 fields)"
        raise ValueError(msg)

    minute, hour, day, month, day_of_week = parts
    return CronTrigger(
        minute=minute,
        hour=hour,
        day=day,
        month=month,
        day_of_week=day_of_week,
        timezone=UTC,
    )


class ReportScheduler:
    """管理定时报告生成任务的启动/停止/状态查询。"""

    def __init__(self) -> None:
        self._schedules: dict[str, ReportSchedule] = {}

    def add_job(self, schedule: ReportSchedule) -> None:
        """添加一个定时报告生成任务。

        Args:
            schedule: 报告调度配置
        """
        if schedule.job_id in self._schedules:
            logger.warning("Report schedule %s already exists, replacing", schedule.job_id)

        schedule.created_at = datetime.now(UTC).isoformat()

        async def _job_func() -> None:
            await self._execute_report(schedule)

        try:
            trigger = _parse_cron(schedule.cron_expr)
            scheduler.add_job(
                _job_func,
                trigger=trigger,
                id=schedule.job_id,
                name=f"Report:{schedule.title or schedule.report_type}",
                replace_existing=True,
                misfire_grace_time=300,
            )
            self._schedules[schedule.job_id] = schedule
            logger.info(
                "Report schedule added: job_id=%s cron=%s type=%s sku=%s",
                schedule.job_id,
                schedule.cron_expr,
                schedule.report_type,
                schedule.sku_id,
            )
        except Exception as exc:
            logger.error("Failed to add report schedule %s: %s", schedule.job_id, exc)
            raise

    def remove_job(self, job_id: str) -> bool:
        """移除一个定时报告生成任务。"""
        if job_id not in self._schedules:
            logger.warning("Report schedule %s not found", job_id)
            return False
        try:
            scheduler.remove_job(job_id)
        except Exception as exc:
            logger.warning("Error removing job %s from scheduler: %s", job_id, exc)
        del self._schedules[job_id]
        logger.info("Report schedule removed: %s", job_id)
        return True

    def list_jobs(self) -> list[dict[str, Any]]:
        """列出所有定时报告配置。"""
        return [s.to_dict() for s in self._schedules.values()]

    def get_job(self, job_id: str) -> dict[str, Any] | None:
        """获取单个调度配置。"""
        s = self._schedules.get(job_id)
        return s.to_dict() if s else None

    async def _execute_report(self, schedule: ReportSchedule) -> None:
        """执行报告生成并投递。"""
        from App.core.database import async_session_factory
        from App.services.notification.dispatcher import NotificationDispatcher
        from App.services.report_generator import get_report_generator

        logger.info(
            "Executing scheduled report: job_id=%s sku=%s",
            schedule.job_id,
            schedule.sku_id,
        )

        generator = get_report_generator()
        dispatcher = NotificationDispatcher()

        try:
            async with async_session_factory() as db:

                # 获取或生成报告数据
                report_data: dict[str, Any] = {
                    "sku_id": schedule.sku_id,
                    "report_type": schedule.report_type,
                    "title": schedule.title or f"Scheduled Report - {schedule.sku_id}",
                    "product_name": schedule.sku_id,
                    "generated_at": datetime.now(UTC).isoformat(),
                    "summary": {},
                }

                # 如果有关联的 report_service 数据，加载它
                try:
                    from App.services.report_service import list_reports

                    reports = await list_reports(
                        db,
                        sku_id=schedule.sku_id,
                        report_type=schedule.report_type,
                        limit=1,
                    )
                    if reports:
                        report_data["content"] = reports[0].content
                        report_data.update(reports[0].content)
                except Exception as exc:
                    logger.warning("Could not load existing report data: %s", exc)

                # 生成文件
                filepath = generator.generate(
                    report_data,
                    output_format=schedule.output_format,
                )

                # 投递
                if schedule.channels:
                    await generator.deliver(
                        report_data,
                        dispatcher,
                        output_format=schedule.output_format,
                        channels=schedule.channels,
                    )
                else:
                    await generator.deliver(
                        report_data,
                        dispatcher,
                        output_format=schedule.output_format,
                    )

                logger.info(
                    "Scheduled report completed: %s -> %s",
                    schedule.job_id,
                    filepath.name,
                )

        except Exception as exc:
            logger.error(
                "Scheduled report failed: job_id=%s error=%s",
                schedule.job_id,
                exc,
            )


# ── 全局实例 ────────────────────────────────────
_collection_scheduler: CollectionScheduler | None = None
_report_scheduler: ReportScheduler | None = None


def get_scheduler() -> CollectionScheduler | None:
    return _collection_scheduler


def get_report_scheduler() -> ReportScheduler | None:
    return _report_scheduler


def init_scheduler(db_session_factory: callable) -> CollectionScheduler:
    global _collection_scheduler
    _collection_scheduler = CollectionScheduler(db_session_factory)
    return _collection_scheduler


def init_report_scheduler() -> ReportScheduler:
    global _report_scheduler
    _report_scheduler = ReportScheduler()
    return _report_scheduler
