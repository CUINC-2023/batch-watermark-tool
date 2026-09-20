from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from utils.paths import app_data_dir


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("batch_watermark_tool")
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        app_data_dir() / "error.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    return logger

