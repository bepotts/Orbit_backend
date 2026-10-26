"""Consistent console and JSON logging for application and third-party events."""

import logging
import sys

import structlog
from structlog.typing import Processor

from orbit_backend.utils.enums import Environment


def configure_logging(
    environment: Environment,
    level: str = "INFO",
) -> None:
    """Configure stdout logging, using JSON in production and readable development logs."""
    shared: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    renderer: Processor
    if environment is Environment.PRODUCTION:
        renderer = structlog.processors.JSONRenderer()
        shared.append(structlog.processors.format_exc_info)
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty())

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                renderer,
            ],
        )
    )
    root = logging.getLogger()
    # Replace only our handler so repeated factories preserve host/test handlers.
    for existing in root.handlers[:]:
        if existing.get_name() == "orbit":
            root.removeHandler(existing)
            existing.close()
    handler.set_name("orbit")
    root.addHandler(handler)
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(logging.NOTSET)
    # HTTP middleware already emits bounded, redacted access events. Uvicorn's
    # access message includes the raw query string, so suppress that duplicate.
    logging.getLogger("uvicorn.access").disabled = True
    # HTTP client INFO messages include complete URLs and may expose query secrets.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)
