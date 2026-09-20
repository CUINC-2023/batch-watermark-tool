from __future__ import annotations

import copy
import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QThread, QTimer
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QMainWindow,
    QMessageBox, QProgressBar, QPushButton, QSplitter, QToolBar, QVBoxLayout, QWidget,
)

from core.pipeline import ImagePipeline
from models.settings import ImageItem, PipelineSettings
from services.error_log import configure_logging
from services.importer import discover_images
from ui.preview_widget import PreviewWidget
from ui.settings_panel import SettingsPanel
from utils.paths import APP_NAME, APP_VERSION, SUPPORTED_EXTENSIONS, resource_path
from workers.export_worker import ExportWorker


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.logger = configure_logging()
        self.settings = PipelineSettings()
        self.pipeline = ImagePipeline()
        self.items: list[ImageItem] = []
        self.current_source = None
        self.show_original = False
        self.worker: ExportWorker | None = None
        self.worker_thread: QThread | None = None
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1440, 880)
        self.setAcceptDrops(True)
        self._build_toolbar()
        self._build_content()
        self._apply_theme()
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(120)
        self.preview_timer.timeout.connect(self.refresh_preview)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("主要工具")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(18, 18))
        self.addToolBar(toolbar)
        actions = [
            ("匯入圖片", self.import_files), ("匯入資料夾", self.import_folder),
            ("移除選取", self.remove_selected), ("清空", self.clear_items),
        ]
        for label, slot in actions:
            action = QAction(label, self); action.triggered.connect(slot); toolbar.addAction(action)
        toolbar.addSeparator()
        self.compare_action = QAction("顯示原圖", self); self.compare_action.setCheckable(True); self.compare_action.toggled.connect(self.toggle_compare); toolbar.addAction(self.compare_action)
        toolbar.addSeparator()
        about = QAction("關於", self); about.triggered.connect(self.show_about); toolbar.addAction(about)

    def _build_content(self) -> None:
        central = QWidget(); outer = QVBoxLayout(central); outer.setContentsMargins(0,0,0,0); outer.setSpacing(0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.thumbnail_list = QListWidget(); self.thumbnail_list.setMinimumWidth(210); self.thumbnail_list.setMaximumWidth(320); self.thumbnail_list.setIconSize(QSize(84,84)); self.thumbnail_list.currentRowChanged.connect(self.select_image)
        self.preview = PreviewWidget(); self.preview.crop_changed.connect(self.update_crop)
        self.settings_panel = SettingsPanel(self.settings); self.settings_panel.settings_changed.connect(self.schedule_preview); self.settings_panel.crop_visibility_changed.connect(self.schedule_preview)
        splitter.addWidget(self.thumbnail_list); splitter.addWidget(self.preview); splitter.addWidget(self.settings_panel)
        splitter.setStretchFactor(0, 0); splitter.setStretchFactor(1, 1); splitter.setStretchFactor(2, 0); splitter.setSizes([240, 850, 350])
        outer.addWidget(splitter, 1)
        bottom = QWidget(); bottom.setObjectName("bottomBar"); layout = QHBoxLayout(bottom); layout.setContentsMargins(16,10,16,10)
        self.status_label = QLabel("尚未匯入圖片")
        self.progress = QProgressBar(); self.progress.setMinimumWidth(260); self.progress.setVisible(False)
        self.cancel_button = QPushButton("取消"); self.cancel_button.setVisible(False); self.cancel_button.clicked.connect(self.cancel_export)
        self.export_button = QPushButton("開始批次導出"); self.export_button.setObjectName("primaryButton"); self.export_button.clicked.connect(self.start_export)
        brand = QLabel("由 CUverse 製作"); brand.setObjectName("brandLabel")
        layout.addWidget(self.status_label, 1); layout.addWidget(self.progress); layout.addWidget(self.cancel_button); layout.addWidget(brand); layout.addWidget(self.export_button)
        outer.addWidget(bottom)
        self.setCentralWidget(central)

    def _apply_theme(self) -> None:
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #F8FAFC; color: #0F172A; font-size: 13px; }
            QToolBar { background: #FFFFFF; border-bottom: 1px solid #E2E8F0; spacing: 6px; padding: 7px; }
            QToolButton, QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 10px; }
            QToolButton:hover, QPushButton:hover { border-color: #06B6D4; }
            #primaryButton { background: #0F766E; color: white; border: none; font-weight: 600; padding: 10px 18px; }
            #bottomBar { background: #FFFFFF; border-top: 1px solid #E2E8F0; }
            #brandLabel { color: #64748B; padding: 0 10px; }
            #hint { color: #64748B; }
            QListWidget, QTabWidget::pane, QLineEdit, QComboBox, QSpinBox { background: #FFFFFF; border: 1px solid #CBD5E1; }
            QListWidget::item { padding: 6px; border-bottom: 1px solid #E2E8F0; }
            QListWidget::item:selected { background: #CCFBF1; color: #134E4A; }
            QTabBar::tab { background: #E2E8F0; padding: 8px 9px; }
            QTabBar::tab:selected { background: #FFFFFF; color: #0F766E; }
        """)

    def import_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "匯入圖片", "", "圖片 (*.jpg *.jpeg *.png *.webp)")
        self.add_inputs(paths)

    def import_folder(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "匯入資料夾")
        if path: self.add_inputs([path])

    def add_inputs(self, paths: list[str]) -> None:
        new_items = discover_images(paths)
        existing = {item.path for item in self.items}
        for item in new_items:
            if item.path in existing: continue
            self.items.append(item)
            list_item = QListWidgetItem(QIcon(str(item.path)), item.display_name)
            list_item.setToolTip(str(item.path)); self.thumbnail_list.addItem(list_item)
        self.status_label.setText(f"共 {len(self.items)} 張圖片")
        if self.items and self.thumbnail_list.currentRow() < 0: self.thumbnail_list.setCurrentRow(0)

    def remove_selected(self) -> None:
        row = self.thumbnail_list.currentRow()
        if row >= 0:
            self.thumbnail_list.takeItem(row); self.items.pop(row)
            if not self.items: self.current_source = None; self.preview.set_pil_image(None)
        self.status_label.setText(f"共 {len(self.items)} 張圖片")

    def clear_items(self) -> None:
        self.items.clear(); self.thumbnail_list.clear(); self.current_source = None; self.preview.set_pil_image(None); self.status_label.setText("尚未匯入圖片")

    def select_image(self, row: int) -> None:
        if row < 0 or row >= len(self.items): return
        try:
            self.current_source = self.pipeline.load(self.items[row].path).image
            self.refresh_preview()
        except Exception as exc:
            self.logger.exception("Unable to preview %s", self.items[row].path)
            QMessageBox.warning(self, "圖片讀取失敗", str(exc))

    def schedule_preview(self, *_):
        self.preview_timer.start()

    def refresh_preview(self) -> None:
        if self.current_source is None: return
        try:
            if self.show_original:
                image = self.current_source.copy(); crop_visible = False
            else:
                preview_settings = copy.deepcopy(self.settings)
                crop_visible = preview_settings.crop.enabled
                if crop_visible: preview_settings.crop.enabled = False
                image = self.pipeline.process(self.current_source, preview_settings, preview_max=(1600, 1200))
            self.preview.set_pil_image(image)
            crop = self.settings.crop
            self.preview.set_crop(crop_visible, crop.normalized_box())
        except Exception as exc:
            self.logger.exception("Preview failed")
            self.status_label.setText(f"預覽錯誤：{exc}")

    def update_crop(self, left: float, top: float, right: float, bottom: float) -> None:
        crop = self.settings.crop; crop.left, crop.top, crop.right, crop.bottom = left, top, right, bottom

    def toggle_compare(self, checked: bool) -> None:
        self.show_original = checked; self.compare_action.setText("顯示加工後" if checked else "顯示原圖"); self.refresh_preview()

    def start_export(self) -> None:
        if not self.items:
            QMessageBox.information(self, "尚無圖片", "請先匯入至少一張圖片。")
            return
        self.export_button.setEnabled(False); self.progress.setVisible(True); self.cancel_button.setVisible(True)
        total = len(self.items) * len([p for p in self.settings.export.profiles if p.enabled]); self.progress.setRange(0, total); self.progress.setValue(0)
        self.worker_thread = QThread(self); self.worker = ExportWorker(list(self.items), copy.deepcopy(self.settings)); self.worker.moveToThread(self.worker_thread)
        self.worker_thread.started.connect(self.worker.run); self.worker.progress.connect(self.on_export_progress); self.worker.finished.connect(self.on_export_finished); self.worker.failed.connect(self.on_export_failed)
        self.worker.finished.connect(self.worker_thread.quit); self.worker.failed.connect(self.worker_thread.quit); self.worker_thread.finished.connect(self.worker.deleteLater); self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.start()

    def cancel_export(self) -> None:
        if self.worker: self.worker.cancel(); self.status_label.setText("正在取消…")

    def on_export_progress(self, done: int, total: int, message: str) -> None:
        self.progress.setMaximum(total); self.progress.setValue(done); self.status_label.setText(message)

    def on_export_finished(self, summary) -> None:
        self._reset_export_ui()
        if summary.failures:
            details = "\n".join(f"{item.source.name}: {item.message}" for item in summary.failures[:8])
            QMessageBox.warning(self, "批次完成（含錯誤）", f"成功 {summary.completed}/{summary.total}\n\n{details}")
        else:
            QMessageBox.information(self, "批次完成", f"已輸出 {summary.completed} 個檔案。")
        self.status_label.setText("已取消" if summary.cancelled else f"完成 {summary.completed}/{summary.total}")

    def on_export_failed(self, message: str) -> None:
        self._reset_export_ui(); self.logger.error("Export worker failed: %s", message); QMessageBox.critical(self, "導出失敗", message)

    def _reset_export_ui(self) -> None:
        self.export_button.setEnabled(True); self.cancel_button.setVisible(False); self.progress.setVisible(False); self.worker = None; self.worker_thread = None

    def show_about(self) -> None:
        box = QMessageBox(self); box.setWindowTitle("關於"); box.setText(f"<b>{APP_NAME}</b><br>版本 {APP_VERSION}<br><br>正式版桌面圖片批次加工工具<br><br><b>製作來源：CUverse</b>")
        logo = QPixmap(str(resource_path("assets/cuverse-logo.webp")))
        if not logo.isNull(): box.setIconPixmap(logo.scaled(180, 90, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        box.exec()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls(): event.acceptProposedAction()

    def dropEvent(self, event) -> None:  # noqa: N802
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.add_inputs(paths); event.acceptProposedAction()

