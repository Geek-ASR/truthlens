"""Structured logging with redaction of secret-shaped fields
(see docs/SECURITY.md §1)."""
import logging
import re

import structlog

_SECRET_KEY_PATTERN = re.compile(r"(token|secret|key|password)$", re.IGNORECASE)
_REDACTED = "***REDACTED***"


def _redact_processor(_logger, _method_name, event_dict):
    for k in list(event_dict.keys()):
        if _SECRET_KEY_PATTERN.search(k):
            event_dict[k] = _REDACTED
    return event_dict


def configure_logging(debug: bool = True) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=logging.DEBUG if debug else logging.INFO,
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            _redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if debug else logging.INFO
        ),
        logger_factory=structlog.PrintLoggerFactory(),
    )


def get_logger(name: str):
    return structlog.get_logger(name)
