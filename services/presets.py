from __future__ import annotations

import json
from pathlib import Path

from models.settings import PipelineSettings
from utils.paths import app_data_dir


class PresetService:
    def __init__(self, directory: Path | None = None) -> None:
        self.directory = directory or app_data_dir() / "presets"
        self.directory.mkdir(parents=True, exist_ok=True)

    def list_names(self) -> list[str]:
        return sorted(path.stem for path in self.directory.glob("*.json"))

    def save(self, name: str, settings: PipelineSettings) -> Path:
        safe_name = "".join(char for char in name.strip() if char not in '<>:"/\\|?*') or "未命名"
        target = self.directory / f"{safe_name}.json"
        target.write_text(json.dumps(settings.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        return target

    def load(self, name: str) -> PipelineSettings:
        raw = json.loads((self.directory / f"{name}.json").read_text(encoding="utf-8"))
        return PipelineSettings.from_dict(raw)

