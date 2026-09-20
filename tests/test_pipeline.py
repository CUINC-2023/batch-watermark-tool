from __future__ import annotations

from pathlib import Path

from PIL import Image

from core.pipeline import ImagePipeline, SourceMetadata
from models.settings import PipelineSettings, ResizeMode, WatermarkMode


def test_crop_and_percent_resize() -> None:
    settings = PipelineSettings()
    settings.crop.enabled = True
    settings.crop.left, settings.crop.top = 0.25, 0.25
    settings.crop.right, settings.crop.bottom = 0.75, 0.75
    settings.export.profiles[0].resize.mode = ResizeMode.PERCENT
    settings.export.profiles[0].resize.percent = 50
    result = ImagePipeline().process(Image.new("RGB", (400, 200)), settings)
    assert result.size == (100, 50)


def test_logo_free_and_tile_use_same_pipeline(tmp_path: Path) -> None:
    logo_path = tmp_path / "logo.png"
    Image.new("RGBA", (20, 10), (255, 0, 0, 255)).save(logo_path)
    settings = PipelineSettings()
    settings.logo.enabled = True
    settings.logo.path = str(logo_path)
    settings.logo.mode = WatermarkMode.FREE
    free = ImagePipeline().process(Image.new("RGBA", (200, 100), "white"), settings)
    settings.logo.mode = WatermarkMode.TILE
    tiled = ImagePipeline().process(Image.new("RGBA", (200, 100), "white"), settings)
    assert free.getbbox() == tiled.getbbox() == (0, 0, 200, 100)
    assert free.tobytes() != tiled.tobytes()


def test_jpeg_and_webp_encoding() -> None:
    pipeline = ImagePipeline()
    settings = PipelineSettings()
    image = Image.new("RGBA", (120, 80), (10, 20, 30, 180))
    profile = settings.export.profiles[0]
    profile.format = "JPEG"
    assert pipeline.encode(image, profile, SourceMetadata()).startswith(b"\xff\xd8")
    profile.format = "WEBP"
    assert pipeline.encode(image, profile, SourceMetadata())[8:12] == b"WEBP"


def test_settings_round_trip() -> None:
    settings = PipelineSettings()
    settings.logo.mode = WatermarkMode.TILE
    settings.export.profiles[0].resize.mode = ResizeMode.LONG_EDGE
    restored = PipelineSettings.from_dict(settings.to_dict())
    assert restored.logo.mode == WatermarkMode.TILE
    assert restored.export.profiles[0].resize.mode == ResizeMode.LONG_EDGE

