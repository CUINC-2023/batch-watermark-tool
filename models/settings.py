from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class ResizeMode(StrEnum):
    ORIGINAL = "original"
    PERCENT = "percent"
    LONG_EDGE = "long_edge"


class WatermarkMode(StrEnum):
    GRID = "grid"
    FREE = "free"
    TILE = "tile"


class OutputLocation(StrEnum):
    CUSTOM = "custom"
    SOURCE_PROCESSED = "source_processed"


@dataclass(slots=True)
class CropSettings:
    enabled: bool = False
    # Normalized coordinates make preview and export resolution-independent.
    left: float = 0.0
    top: float = 0.0
    right: float = 1.0
    bottom: float = 1.0

    def normalized_box(self) -> tuple[float, float, float, float]:
        left = min(max(self.left, 0.0), 0.99)
        top = min(max(self.top, 0.0), 0.99)
        right = min(max(self.right, left + 0.01), 1.0)
        bottom = min(max(self.bottom, top + 0.01), 1.0)
        return left, top, right, bottom


@dataclass(slots=True)
class ResizeSettings:
    mode: ResizeMode = ResizeMode.ORIGINAL
    percent: int = 100
    long_edge: int = 2048


@dataclass(slots=True)
class LogoSettings:
    enabled: bool = False
    path: str = ""
    mode: WatermarkMode = WatermarkMode.GRID
    grid_position: str = "bottom-right"
    x: float = 0.9
    y: float = 0.9
    scale: float = 0.2
    rotation: float = 0.0
    opacity: float = 0.85
    margin: int = 24
    tile_gap: int = 48


@dataclass(slots=True)
class TextSettings:
    enabled: bool = False
    text: str = ""
    font_path: str = ""
    font_size: int = 42
    color: str = "#FFFFFF"
    opacity: float = 0.85
    position: str = "bottom-left"
    margin: int = 24


@dataclass(slots=True)
class OutputProfile:
    name: str = "主要輸出"
    enabled: bool = True
    resize: ResizeSettings = field(default_factory=ResizeSettings)
    format: str = "JPEG"
    quality: int = 92
    max_kb: int = 0
    suffix: str = ""


@dataclass(slots=True)
class ExportSettings:
    location: OutputLocation = OutputLocation.CUSTOM
    output_dir: str = ""
    preserve_structure: bool = True
    processed_folder_name: str = "加工後"
    filename_template: str = "{stem}{suffix}"
    start_index: int = 1
    preserve_exif: bool = True
    preserve_icc: bool = True
    profiles: list[OutputProfile] = field(default_factory=lambda: [OutputProfile()])


@dataclass(slots=True)
class PipelineSettings:
    crop: CropSettings = field(default_factory=CropSettings)
    logo: LogoSettings = field(default_factory=LogoSettings)
    text: TextSettings = field(default_factory=TextSettings)
    export: ExportSettings = field(default_factory=ExportSettings)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @staticmethod
    def _enum(enum_type: type[StrEnum], value: Any, default: StrEnum) -> StrEnum:
        try:
            return enum_type(value)
        except (ValueError, TypeError):
            return default

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "PipelineSettings":
        crop = CropSettings(**raw.get("crop", {}))
        logo_raw = raw.get("logo", {}).copy()
        logo_raw["mode"] = cls._enum(WatermarkMode, logo_raw.get("mode"), WatermarkMode.GRID)
        logo = LogoSettings(**logo_raw)
        text = TextSettings(**raw.get("text", {}))
        export_raw = raw.get("export", {}).copy()
        export_raw["location"] = cls._enum(
            OutputLocation, export_raw.get("location"), OutputLocation.CUSTOM
        )
        profiles = []
        for item in export_raw.pop("profiles", []) or [{}]:
            item = item.copy()
            resize_raw = item.pop("resize", {})
            resize_raw["mode"] = cls._enum(
                ResizeMode, resize_raw.get("mode"), ResizeMode.ORIGINAL
            )
            profiles.append(OutputProfile(resize=ResizeSettings(**resize_raw), **item))
        return cls(
            crop=crop,
            logo=logo,
            text=text,
            export=ExportSettings(profiles=profiles, **export_raw),
        )


@dataclass(slots=True)
class ImageItem:
    path: Path
    source_root: Path | None = None

    @property
    def display_name(self) -> str:
        return self.path.name

    @property
    def relative_parent(self) -> Path:
        if not self.source_root:
            return Path()
        try:
            return self.path.parent.relative_to(self.source_root)
        except ValueError:
            return Path()

