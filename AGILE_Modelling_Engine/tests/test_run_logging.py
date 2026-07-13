"""Timestamp-format contract for portfolio-runner console logging."""

from datetime import datetime, timedelta, timezone
from io import StringIO

from portfolio_simulations._run_logging import (
    format_run_log_line,
    log_to_console,
)


FIXED_LOCAL_TIME = datetime(
    2026,
    7,
    13,
    14,
    5,
    6,
    tzinfo=timezone(timedelta(hours=2)),
)


def test_format_run_log_line_contains_date_time_level_and_message():
    assert format_run_log_line(
        "Worker completed",
        level="warning",
        timestamp=FIXED_LOCAL_TIME,
    ) == "2026-07-13 14:05:06 | WARNING | Worker completed"


def test_log_to_console_uses_same_format_and_terminates_the_line():
    stream = StringIO()

    log_to_console(
        "Run started",
        stream=stream,
        timestamp=FIXED_LOCAL_TIME,
    )

    assert stream.getvalue() == "2026-07-13 14:05:06 | INFO | Run started\n"
