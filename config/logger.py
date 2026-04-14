"""
Centralized logging configuration for the Behavior Intelligence Engine.

Usage:
    from config.logger import get_logger
    logger = get_logger(__name__)
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

from config.settings import cfg


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    logger = logging.getLogger(name)

    if logger.handlers:
        # Already configured – return existing instance
        return logger

    logger.setLevel(getattr(logging, cfg.log_level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (rotating, max 10 MB, keep 5 backups)
    log_dir = os.path.dirname(cfg.log_file)
    try:
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
        fh = RotatingFileHandler(
            cfg.log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except (OSError, PermissionError):
        # Gracefully degrade to console-only logging if log file is unavailable
        pass

    logger.propagate = False
    return logger
