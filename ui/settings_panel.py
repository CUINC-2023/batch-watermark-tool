from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QFileDialog, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QSlider, QSpinBox, QTabWidget, QVBoxLayout, QWidget,
)
from PySide6.QtCore import Qt

from models.settings import OutputLocation, PipelineSettings, ResizeMode, WatermarkMode


POSITIONS = [
    ("左上", "top-left"), ("上中", "top-center"), ("右上", "top-right"),
    ("左中", "middle-left"), ("中央", "center"), ("右中", "middle-right"),
    ("左下", "bottom-left"), ("下中", "bottom-center"), ("右下", "bottom-right"),
]


class SettingsPanel(QWidget):
    settings_changed = Signal()
    crop_visibility_changed = Signal(bool)

    def __init__(self, settings: PipelineSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setMinimumWidth(320)
        tabs = QTabWidget()
        tabs.addTab(self._processing_tab(), "加工")
        tabs.addTab(self._crop_tab(), "裁切")
        tabs.addTab(self._logo_tab(), "Logo")
        tabs.addTab(self._text_tab(), "文字")
        tabs.addTab(self._output_tab(), "輸出")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(tabs)

    def _processing_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
        self.resize_mode = QComboBox()
        self.resize_mode.addItem("保留原尺寸", ResizeMode.ORIGINAL)
        self.resize_mode.addItem("百分比", ResizeMode.PERCENT)
        self.resize_mode.addItem("指定長邊", ResizeMode.LONG_EDGE)
        self.resize_percent = QSpinBox(); self.resize_percent.setRange(1, 500); self.resize_percent.setValue(100); self.resize_percent.setSuffix(" %")
        self.long_edge = QSpinBox(); self.long_edge.setRange(64, 30000); self.long_edge.setValue(2048); self.long_edge.setSuffix(" px")
        form.addRow("調整方式", self.resize_mode); form.addRow("百分比", self.resize_percent); form.addRow("長邊", self.long_edge)
        for control in (self.resize_mode, self.resize_percent, self.long_edge):
            (control.currentIndexChanged if isinstance(control, QComboBox) else control.valueChanged).connect(self._sync_processing)
        return widget

    def _crop_tab(self) -> QWidget:
        widget = QWidget(); layout = QVBoxLayout(widget)
        self.crop_enabled = QCheckBox("啟用可視化裁切框")
        reset = QPushButton("重設裁切框")
        hint = QLabel("在中央預覽直接拖曳裁切框；四角可調整範圍。")
        hint.setWordWrap(True); hint.setObjectName("hint")
        self.crop_enabled.toggled.connect(self._sync_crop)
        reset.clicked.connect(self._reset_crop)
        layout.addWidget(self.crop_enabled); layout.addWidget(reset); layout.addWidget(hint); layout.addStretch()
        return widget

    def _logo_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
        self.logo_enabled = QCheckBox("啟用 Logo 浮水印")
        self.logo_path = QLineEdit(); choose = QPushButton("選擇…")
        path_row = QWidget(); row = QHBoxLayout(path_row); row.setContentsMargins(0,0,0,0); row.addWidget(self.logo_path); row.addWidget(choose)
        self.logo_mode = QComboBox(); self.logo_mode.addItem("九宮格", WatermarkMode.GRID); self.logo_mode.addItem("自由位置", WatermarkMode.FREE); self.logo_mode.addItem("平鋪", WatermarkMode.TILE)
        self.logo_position = QComboBox(); [self.logo_position.addItem(label, value) for label, value in POSITIONS]
        self.logo_position.setCurrentIndex(self.logo_position.findData("bottom-right"))
        self.logo_scale = QSpinBox(); self.logo_scale.setRange(1, 200); self.logo_scale.setValue(20); self.logo_scale.setSuffix(" %")
        self.logo_opacity = QSpinBox(); self.logo_opacity.setRange(0, 100); self.logo_opacity.setValue(85); self.logo_opacity.setSuffix(" %")
        self.logo_rotation = QSpinBox(); self.logo_rotation.setRange(-180, 180); self.logo_rotation.setSuffix("°")
        form.addRow(self.logo_enabled); form.addRow("Logo 圖片", path_row); form.addRow("位置方式", self.logo_mode); form.addRow("九宮格位置", self.logo_position); form.addRow("大小", self.logo_scale); form.addRow("透明度", self.logo_opacity); form.addRow("旋轉", self.logo_rotation)
        choose.clicked.connect(self._choose_logo)
        self.logo_path.editingFinished.connect(self._sync_logo)
        self.logo_enabled.toggled.connect(self._sync_logo)
        self.logo_mode.currentIndexChanged.connect(self._sync_logo)
        self.logo_position.currentIndexChanged.connect(self._sync_logo)
        self.logo_scale.valueChanged.connect(self._sync_logo)
        self.logo_opacity.valueChanged.connect(self._sync_logo)
        self.logo_rotation.valueChanged.connect(self._sync_logo)
        return widget

    def _text_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
        self.text_enabled = QCheckBox("啟用文字浮水印")
        self.text_value = QLineEdit(); self.text_size = QSpinBox(); self.text_size.setRange(8, 300); self.text_size.setValue(42)
        self.text_position = QComboBox(); [self.text_position.addItem(label, value) for label, value in POSITIONS]
        self.text_position.setCurrentIndex(self.text_position.findData("bottom-left"))
        form.addRow(self.text_enabled); form.addRow("文字", self.text_value); form.addRow("字級", self.text_size); form.addRow("位置", self.text_position)
        self.text_enabled.toggled.connect(self._sync_text); self.text_value.textChanged.connect(self._sync_text); self.text_size.valueChanged.connect(self._sync_text); self.text_position.currentIndexChanged.connect(self._sync_text)
        return widget

    def _output_tab(self) -> QWidget:
        widget = QWidget(); form = QFormLayout(widget)
        self.output_location = QComboBox(); self.output_location.addItem("指定資料夾", OutputLocation.CUSTOM); self.output_location.addItem("原圖資料夾／加工後", OutputLocation.SOURCE_PROCESSED)
        self.output_path = QLineEdit(); choose = QPushButton("選擇…")
        row_widget = QWidget(); row = QHBoxLayout(row_widget); row.setContentsMargins(0,0,0,0); row.addWidget(self.output_path); row.addWidget(choose)
        self.output_format = QComboBox(); [self.output_format.addItem(value) for value in ("JPEG", "PNG", "WEBP")]
        self.quality = QSpinBox(); self.quality.setRange(20, 100); self.quality.setValue(92)
        self.max_kb = QSpinBox(); self.max_kb.setRange(0, 999999); self.max_kb.setSpecialValueText("不限"); self.max_kb.setSuffix(" KB")
        self.preserve_structure = QCheckBox("保留原資料夾結構"); self.preserve_structure.setChecked(True)
        self.preserve_exif = QCheckBox("保留 EXIF"); self.preserve_exif.setChecked(True)
        self.preserve_icc = QCheckBox("保留 ICC Profile"); self.preserve_icc.setChecked(True)
        form.addRow("輸出位置", self.output_location); form.addRow("資料夾", row_widget); form.addRow("格式", self.output_format); form.addRow("品質", self.quality); form.addRow("大小限制", self.max_kb); form.addRow(self.preserve_structure); form.addRow(self.preserve_exif); form.addRow(self.preserve_icc)
        choose.clicked.connect(self._choose_output)
        self.output_path.editingFinished.connect(self._sync_output)
        self.output_location.currentIndexChanged.connect(self._sync_output)
        self.output_format.currentTextChanged.connect(self._sync_output)
        self.quality.valueChanged.connect(self._sync_output); self.max_kb.valueChanged.connect(self._sync_output)
        self.preserve_structure.toggled.connect(self._sync_output); self.preserve_exif.toggled.connect(self._sync_output); self.preserve_icc.toggled.connect(self._sync_output)
        return widget

    def _sync_processing(self, *_):
        profile = self.settings.export.profiles[0]
        profile.resize.mode = self.resize_mode.currentData(); profile.resize.percent = self.resize_percent.value(); profile.resize.long_edge = self.long_edge.value(); self.settings_changed.emit()

    def _sync_crop(self, enabled: bool):
        self.settings.crop.enabled = enabled; self.crop_visibility_changed.emit(enabled); self.settings_changed.emit()

    def _reset_crop(self):
        crop = self.settings.crop; crop.left, crop.top, crop.right, crop.bottom = 0.08, 0.08, 0.92, 0.92; self.settings_changed.emit()

    def _choose_logo(self):
        path, _ = QFileDialog.getOpenFileName(self, "選擇 Logo", "", "圖片 (*.png *.webp *.jpg *.jpeg)")
        if path: self.logo_path.setText(path); self._sync_logo()

    def _sync_logo(self, *_):
        logo = self.settings.logo; logo.enabled = self.logo_enabled.isChecked(); logo.path = self.logo_path.text(); logo.mode = self.logo_mode.currentData(); logo.grid_position = self.logo_position.currentData(); logo.scale = self.logo_scale.value()/100; logo.opacity = self.logo_opacity.value()/100; logo.rotation = self.logo_rotation.value(); self.settings_changed.emit()

    def _sync_text(self, *_):
        text = self.settings.text; text.enabled = self.text_enabled.isChecked(); text.text = self.text_value.text(); text.font_size = self.text_size.value(); text.position = self.text_position.currentData(); self.settings_changed.emit()

    def _choose_output(self):
        path = QFileDialog.getExistingDirectory(self, "選擇輸出資料夾")
        if path: self.output_path.setText(path); self._sync_output()

    def _sync_output(self, *_):
        export = self.settings.export; export.location = self.output_location.currentData(); export.output_dir = self.output_path.text(); export.preserve_structure = self.preserve_structure.isChecked(); export.preserve_exif = self.preserve_exif.isChecked(); export.preserve_icc = self.preserve_icc.isChecked()
        profile = export.profiles[0]; profile.format = self.output_format.currentText(); profile.quality = self.quality.value(); profile.max_kb = self.max_kb.value(); self.settings_changed.emit()
