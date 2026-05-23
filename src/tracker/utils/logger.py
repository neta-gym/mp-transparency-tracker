"""Rich-based and JSON structured logging."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone

from rich.console import Console
from rich.logging import RichHandler
from rich.theme import Theme

custom_theme = Theme({
    "info": "cyan",
    "warning": "yellow",
    "error": "bold red",
    "success": "bold green",
    "agent": "bold magenta",
})

console = Console(theme=custom_theme)

# Check LOG_FORMAT env var: "json" for structured output, "rich" (default) for human-friendly
_LOG_FORMAT = os.environ.get("LOG_FORMAT", "rich").lower()


class JsonFormatter(logging.Formatter):
    """Output log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "module": record.module,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = str(record.exc_info[1])
        return json.dumps(log_entry, default=str)


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Create a logger — Rich-formatted (default) or JSON structured."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        if _LOG_FORMAT == "json":
            handler = logging.StreamHandler()
            handler.setFormatter(JsonFormatter())
        else:
            handler = RichHandler(
                console=console,
                show_time=True,
                show_path=False,
                markup=True,
                rich_tracebacks=True,
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    return logger
