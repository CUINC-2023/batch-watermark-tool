from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from threading import Event
from typing import Callable, Iterable

from core.pipeline import ImagePipeline, extension_for
from models.settings import ImageItem, OutputLocation, PipelineSettings


@dataclass(slots=True)
class ExportFailure:
    source: Path
    message: str


@dataclass(slots=True)
class ExportSummary:
    completed: int
    total: int
    outputs: list[Path]
    failures: list[ExportFailure]
    cancelled: bool = False


ProgressCallback = Callable[[int, int, str], None]


class ExportService:
    def __init__(self, pipeline: ImagePipeline | None = None) -> None:
        self.pipeline = pipeline or ImagePipeline()

    def export(
        self,
        items: Iterable[ImageItem],
        settings: PipelineSettings,
        cancel_event: Event | None = None,
        progress: ProgressCallback | None = None,
    ) -> ExportSummary:
        queue = [(item, profile) for item in items for profile in settings.export.profiles if profile.enabled]
        total = len(queue)
        completed = 0
        outputs: list[Path] = []
        failures: list[ExportFailure] = []
        for index, (item, profile) in enumerate(queue, settings.export.start_index):
            if cancel_event and cancel_event.is_set():
                return ExportSummary(completed, total, outputs, failures, cancelled=True)
            try:
                loaded = self.pipeline.load(item.path)
                processed = self.pipeline.process(loaded.image, settings, profile=profile)
                payload = self.pipeline.encode(
                    processed,
                    profile,
                    loaded.metadata,
                    preserve_exif=settings.export.preserve_exif,
                    preserve_icc=settings.export.preserve_icc,
                )
                destination = self._destination(item, profile.name, index, settings, profile.suffix)
                destination = destination.with_suffix(extension_for(profile.format))
                if destination.resolve() == item.path.resolve():
                    raise ValueError("輸出路徑不可覆蓋原圖")
                destination.parent.mkdir(parents=True, exist_ok=True)
                temporary = destination.with_name(f".{destination.name}.tmp")
                temporary.write_bytes(payload)
                os.replace(temporary, destination)
                outputs.append(destination)
                completed += 1
                if progress:
                    progress(completed, total, destination.name)
            except Exception as exc:  # keep batch processing the remaining files
                failures.append(ExportFailure(item.path, str(exc)))
                if progress:
                    progress(completed, total, f"錯誤：{item.display_name}")
        return ExportSummary(completed, total, outputs, failures)

    @staticmethod
    def _destination(
        item: ImageItem,
        profile_name: str,
        index: int,
        settings: PipelineSettings,
        suffix: str,
    ) -> Path:
        export = settings.export
        if export.location == OutputLocation.SOURCE_PROCESSED:
            base = item.path.parent / export.processed_folder_name
        else:
            if not export.output_dir:
                raise ValueError("請先指定輸出資料夾")
            base = Path(export.output_dir)
            if export.preserve_structure:
                base = base / item.relative_parent
        if len([profile for profile in export.profiles if profile.enabled]) > 1:
            base = base / profile_name
        filename = export.filename_template.format(
            stem=item.path.stem,
            suffix=suffix,
            index=index,
            profile=profile_name,
        )
        return base / filename

