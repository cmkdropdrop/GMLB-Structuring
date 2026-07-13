"""Shared timestamp formatting for portfolio-runner console messages."""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Optional, TextIO


RUN_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def format_run_log_line(
    message: object,
    *,
    level: str = "INFO",
    timestamp: Optional[datetime] = None,
) -> str:
    """Return one runner log line with a local date-and-time prefix."""
    effective_timestamp = (
        datetime.now().astimezone() if timestamp is None else timestamp
    )
    return (
        f"{effective_timestamp.strftime(RUN_LOG_DATE_FORMAT)} | "
        f"{str(level).upper()} | {message}"
    )


def log_to_console(
    message: object,
    *,
    level: str = "INFO",
    stream: Optional[TextIO] = None,
    timestamp: Optional[datetime] = None,
) -> None:
    """Write one immediately flushed, timestamped runner message."""
    print(
        format_run_log_line(message, level=level, timestamp=timestamp),
        file=sys.stdout if stream is None else stream,
        flush=True,
    )


__all__ = [
    "RUN_LOG_DATE_FORMAT",
    "format_run_log_line",
    "log_to_console",
]
