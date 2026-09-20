from __future__ import annotations

import sys
from pathlib import Path


APP_NAME = "Batch Watermark Tool Pro"
APP_VERSION = "5.0.0-alpha.1"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def resource_path(relative: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))
    return base / relative


def app_data_dir() -> Path:
    base = Path.home() / ".batch_watermark_tool_v5"
    base.mkdir(parents=True, exist_ok=True)
    return base

