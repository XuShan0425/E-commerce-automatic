"""采集任务调度器 — APScheduler 定时触发数据采集."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from App.core.config import settings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()

COLLECTION_INTERVAL_MINUTES: int = 30  # 默认每30分钟采集一次


class CollectionScheduler:
    """管理定时采集任务的启动/停止/状态查询。"""

    def __init__(self, db_session_factory: callable) -> None:
        self._db_factory = db_session_factory
        self._job_id: str | None = None
        self._last_result: dict | None = None

    async def _collection_job(self) -> None:
        """定时任务回调。"""
        from App.services.cookie_manager import CookieManager
        from App.services.data_collector import collect_ad_data
        from App.services.alert_service import raise_alert

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


# ── 全局实例 ────────────────────────────────────
_collection_scheduler: CollectionScheduler | None = None


def get_scheduler() -> CollectionScheduler | None:
    return _collection_scheduler


def init_scheduler(db_session_factory: callable) -> CollectionScheduler:
    global _collection_scheduler
    _collection_scheduler = CollectionScheduler(db_session_factory)
    return _collection_scheduler
