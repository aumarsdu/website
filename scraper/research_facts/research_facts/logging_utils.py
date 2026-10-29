"""Structured logging for pipeline stages and per-record outcomes."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

LOGGER_NAME = "research_facts"

# Event names reused by the pipeline so logs can be grepped or counted.
EV_RUN_START = "run_start"
EV_RUN_END = "run_end"
EV_INPUT_READ = "input_read"
EV_DOCUMENT = "document_loaded"
EV_ERROR = "error"


class JsonFormatter(logging.Formatter):
    """One JSON object per line: stable keys, greppable, machine-countable."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", "log"),
            "message": record.getMessage(),
        }
        extra = getattr(record, "payload", None)
        if isinstance(extra, dict):
            for key, value in extra.items():
                if key not in payload:
                    payload[key] = value
        if record.exc_info:
            payload["error_type"] = record.exc_info[0].__name__ if record.exc_info[0] else None
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def configure_logging(verbose: bool = False, stream: Any = None) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    logger.handlers.clear()
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER_NAME)


def log_event(logger: logging.Logger, event: str, message: str, **payload: Any) -> None:
    """Emit a structured event. ``payload`` keys are added as top-level fields."""
    safe = {key: value for key, value in payload.items() if value is not None}
    logger.info(message, extra={"event": event, "payload": safe})
