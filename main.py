from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PIL import Image

from core.pipeline import ImagePipeline, SourceMetadata
from models.settings import PipelineSettings
from utils.paths import APP_NAME, APP_VERSION


def smoke_test() -> int:
    try:
        settings = PipelineSettings()
        settings.crop.enabled = True
        settings.crop.left, settings.crop.top, settings.crop.right, settings.crop.bottom = 0.1, 0.1, 0.9, 0.9
        settings.export.profiles[0].format = "WEBP"
        source = Image.new("RGB", (640, 480), "#0F766E")
        pipeline = ImagePipeline()
        output = pipeline.process(source, settings)
        payload = pipeline.encode(output, settings.export.profiles[0], SourceMetadata())
        report = {"success": bool(payload), "version": APP_VERSION, "size": output.size, "format": "WEBP"}
        report_path = os.environ.get("WATERMARK_SMOKE_REPORT")
        if report_path: Path(report_path).write_text(json.dumps(report), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}), file=sys.stderr)
        return 1


def main() -> int:
    if "--smoke-test" in sys.argv:
        return smoke_test()
    from PySide6.QtWidgets import QApplication
    from ui.main_window import MainWindow
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION)
    window = MainWindow(); window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
