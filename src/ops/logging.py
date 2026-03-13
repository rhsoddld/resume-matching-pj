"""Structured JSON logging using structlog with request_id context propagation.

Usage:
    from ops.logging import get_logger, configure_logging

    configure_logging(log_level="INFO")
    logger = get_logger(__name__)
    logger.info("candidate_indexed", candidate_id="abc123", latency_ms=42)
"""
from __future__ import annotations

import logging
import sys
from contextvars import ContextVar

import structlog

# Context variable shared with RequestIdMiddleware
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def _add_request_id(
    logger: logging.Logger,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict,
) -> dict:
    """structlog processor: inject request_id from context."""
    event_dict["request_id"] = request_id_ctx.get("-")
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output.  Call once at app startup."""

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_request_id,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger for the given module name."""
    return structlog.get_logger(name)
