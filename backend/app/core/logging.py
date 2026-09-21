"""Structured logging and security sanitization for AlgoTrade."""

import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

SENSITIVE_KEYS = {"authorization", "api_key", "jev_api_key", "password", "token", "secret"}


def sanitize_dict(d: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively redacts sensitive keys from log dictionaries."""
    sanitized = {}
    for k, v in d.items():
        if any(s in k.lower() for s in SENSITIVE_KEYS):
            sanitized[k] = "[REDACTED]"
        elif isinstance(v, dict):
            sanitized[k] = sanitize_dict(v)
        else:
            sanitized[k] = v
    return sanitized


class StructuredLogFormatter(logging.Formatter):
    """Formats log records as structured text with correlation and context metadata."""

    def format(self, record: logging.LogRecord) -> str:
        base_time = datetime.now(timezone.utc).isoformat()
        component = getattr(record, "component", record.name)
        event = getattr(record, "event", record.funcName)
        request_id = getattr(record, "request_id", "-")
        session_id = getattr(record, "session_id", "-")
        experiment_id = getattr(record, "experiment_id", "-")

        meta = []
        if request_id != "-":
            meta.append(f"req={request_id}")
        if session_id != "-":
            meta.append(f"session={session_id}")
        if experiment_id != "-":
            meta.append(f"exp={experiment_id}")

        meta_str = f" [{', '.join(meta)}]" if meta else ""
        return f"{base_time} [{record.levelname:<5}] [{component}] {record.getMessage()}{meta_str}"


def setup_logging(log_level: str = "INFO") -> None:
    """Configures root application logger."""
    level = getattr(logging, log_level.upper(), logging.INFO)
    root = logging.getLogger("algotrade")
    root.setLevel(level)

    # Clear existing handlers
    if root.handlers:
        root.handlers.clear()

    handler = logging.StreamHandler()
    handler.setFormatter(StructuredLogFormatter())
    root.addHandler(handler)
