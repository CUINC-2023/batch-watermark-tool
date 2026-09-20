from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from models.settings import ImageItem, PipelineSettings
from services.exporter import ExportService, ExportSummary


class ExportWorker(QObject):
    progress = Signal(int, int, str)
    finished = Signal(object)
    failed = Signal(str)

    def __init__(self, items: list[ImageItem], settings: PipelineSettings) -> None:
        super().__init__()
        self.items = items
        self.settings = settings
        self.cancel_event = Event()

    @Slot()
    def run(self) -> None:
        try:
            summary = ExportService().export(
                self.items,
                self.settings,
                cancel_event=self.cancel_event,
                progress=lambda done, total, message: self.progress.emit(done, total, message),
            )
            self.finished.emit(summary)
        except Exception as exc:
            self.failed.emit(str(exc))

    @Slot()
    def cancel(self) -> None:
        self.cancel_event.set()

