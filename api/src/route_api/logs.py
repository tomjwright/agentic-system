"""Structured logs: one JSON object per line. Never pass queries, coordinates or tokens."""

import json
import logging

logger = logging.getLogger("route_api")


def log_event(event: str, **fields: str | int | float) -> None:
    logger.info(json.dumps({"event": event, **fields}))


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
