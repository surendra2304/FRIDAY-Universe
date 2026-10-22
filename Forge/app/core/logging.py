"""
Structured and timestamped logging configuration for FORGE.
"""

import logging
import sys


def setup_logging(debug: bool = True) -> None:
    """Configure structured, timestamped logging for Forge."""
    level = logging.DEBUG if debug else logging.INFO
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [forge]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Silence overly verbose third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def get_logger(name: str) -> logging.Logger:
    """Retrieve a configured logger."""
    return logging.getLogger(f"forge.{name}")
