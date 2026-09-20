from __future__ import annotations

from pathlib import Path

from PIL import Image

from models.settings import OutputLocation, PipelineSettings
from services.exporter import ExportService
from services.importer import discover_images


def test_folder_import_and_structure_preservation(tmp_path: Path) -> None:
    source = tmp_path / "source" / "nested"
    source.mkdir(parents=True)
    Image.new("RGB", (64, 64), "blue").save(source / "photo.jpg")
    (source / "ignore.txt").write_text("x")
    items = discover_images([tmp_path / "source"])
    assert len(items) == 1
    settings = PipelineSettings()
    settings.export.output_dir = str(tmp_path / "output")
    settings.export.location = OutputLocation.CUSTOM
    summary = ExportService().export(items, settings)
    assert summary.completed == 1
    assert (tmp_path / "output" / "nested" / "photo.jpg").is_file()


def test_source_processed_folder(tmp_path: Path) -> None:
    source = tmp_path / "photo.png"
    Image.new("RGBA", (32, 32), "red").save(source)
    items = discover_images([source])
    settings = PipelineSettings()
    settings.export.location = OutputLocation.SOURCE_PROCESSED
    settings.export.profiles[0].format = "PNG"
    summary = ExportService().export(items, settings)
    assert summary.completed == 1
    assert (tmp_path / "加工後" / "photo.png").is_file()

