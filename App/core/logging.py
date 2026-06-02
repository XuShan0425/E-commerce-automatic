"""结构化日志系统 — 统一应用日志输出为 JSON 格式。

用法:
    from App.core.logging import get_logger

    logger = get_logger(__name__)
    logger.info("collection_complete", extra={"sku_count": 42, "duration_ms": 1230})

输出格式 (JSON 行):
    {"timestamp": "2026-05-31T10:00:00.000Z", "level": "INFO", "logger": "data_collector",
     "event": "collection_complete", "sku_count": 42, "duration_ms": 1230}
"""

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any


LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z",
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }

        if record.exc_info and record.exc_info[1]:
            payload["exception"] = str(record.exc_info[1])

        for key, value in getattr(record, "extra_fields", {}).items():
            payload[key] = value

        return json.dumps(payload, ensure_ascii=False, default=str)


class StructuredLogger(logging.Logger):
    def info(self, msg: str, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._log_with_extra(logging.INFO, msg, extra, **kwargs)

    def warn(self, msg: str, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._log_with_extra(logging.WARNING, msg, extra, **kwargs)

    def error(self, msg: str, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._log_with_extra(logging.ERROR, msg, extra, **kwargs)

    def debug(self, msg: str, extra: dict[str, Any] | None = None, **kwargs: Any) -> None:
        self._log_with_extra(logging.DEBUG, msg, extra, **kwargs)

    def _log_with_extra(self, level: int, msg: str, extra: dict[str, Any] | None, **kwargs: Any) -> None:
        record = logging.LogRecord(
            name=self.name,
            level=level,
            pathname="",
            lineno=0,
            msg=msg,
            args=(),
            exc_info=kwargs.pop("exc_info", None),
        )
        record.extra_fields = extra or {}
        for k, v in (kwargs or {}).items():
            record.extra_fields[k] = v
        self.handle(record)


def _init_logging() -> None:
    logging.setLoggerClass(StructuredLogger)
    root = logging.getLogger()

    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    root.setLevel(LOG_LEVELS.get(level_name, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root.handlers.clear()
    root.addHandler(handler)


def get_logger(name: str) -> StructuredLogger:
    if not logging.getLoggerClass() or logging.getLoggerClass() is logging.Logger:
        _init_logging()
    logger = logging.getLogger(name)
    if not isinstance(logger, StructuredLogger):
        return logger  # type: ignore[return-value]
    return logger


def bind_logger(logger: logging.Logger, **context: Any) -> logging.Logger:
    """Return a child logger with extra context fields permanently attached.

    Usage:
        logger = get_logger(__name__)
        logger = bind_logger(logger, sku_id="12345", source="manual")
        logger.info("processing")  # includes sku_id and source in JSON output
    """
    if isinstance(logger, StructuredLogger):
        logger = logging.getLogger(f"{logger.name}.{id(context)}")
        logger.extra_fields = context  # type: ignore[attr-defined]
        logger.setLevel(logging.INFO)
        parent_handlers = logging.getLogger(logger.name.rsplit(".", 1)[0]).handlers
        for h in parent_handlers:
            logger.addHandler(h)
    return logger
