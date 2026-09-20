from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget
from PIL import Image


class PreviewWidget(QWidget):
    crop_changed = Signal(float, float, float, float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(460, 360)
        self.setMouseTracking(True)
        self._pixmap = QPixmap()
        self._crop_enabled = False
        self._crop = QRectF(0.08, 0.08, 0.84, 0.84)
        self._image_rect = QRectF()
        self._drag_mode = ""
        self._drag_start = QPointF()
        self._crop_start = QRectF()

    def set_pil_image(self, image: Image.Image | None) -> None:
        if image is None:
            self._pixmap = QPixmap()
        else:
            rgba = image.convert("RGBA")
            qimage = QImage(
                rgba.tobytes("raw", "RGBA"), rgba.width, rgba.height,
                rgba.width * 4, QImage.Format.Format_RGBA8888,
            ).copy()
            self._pixmap = QPixmap.fromImage(qimage)
        self.update()

    def set_crop(self, enabled: bool, box: tuple[float, float, float, float]) -> None:
        self._crop_enabled = enabled
        left, top, right, bottom = box
        self._crop = QRectF(left, top, right - left, bottom - top)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#111827"))
        if self._pixmap.isNull():
            painter.setPen(QColor("#94A3B8"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "拖曳圖片或資料夾到這裡")
            return
        fitted = self._pixmap.scaled(
            self.size() - self._margins(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        x = (self.width() - fitted.width()) / 2
        y = (self.height() - fitted.height()) / 2
        self._image_rect = QRectF(x, y, fitted.width(), fitted.height())
        painter.drawPixmap(round(x), round(y), fitted)
        if self._crop_enabled:
            crop_rect = self._to_widget(self._crop)
            shade = QColor(0, 0, 0, 130)
            painter.fillRect(QRectF(self._image_rect.left(), self._image_rect.top(), self._image_rect.width(), crop_rect.top() - self._image_rect.top()), shade)
            painter.fillRect(QRectF(self._image_rect.left(), crop_rect.bottom(), self._image_rect.width(), self._image_rect.bottom() - crop_rect.bottom()), shade)
            painter.fillRect(QRectF(self._image_rect.left(), crop_rect.top(), crop_rect.left() - self._image_rect.left(), crop_rect.height()), shade)
            painter.fillRect(QRectF(crop_rect.right(), crop_rect.top(), self._image_rect.right() - crop_rect.right(), crop_rect.height()), shade)
            painter.setPen(QPen(QColor("#22D3EE"), 2))
            painter.drawRect(crop_rect)
            painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DashLine))
            painter.drawLine(crop_rect.left() + crop_rect.width() / 3, crop_rect.top(), crop_rect.left() + crop_rect.width() / 3, crop_rect.bottom())
            painter.drawLine(crop_rect.left() + crop_rect.width() * 2 / 3, crop_rect.top(), crop_rect.left() + crop_rect.width() * 2 / 3, crop_rect.bottom())
            painter.drawLine(crop_rect.left(), crop_rect.top() + crop_rect.height() / 3, crop_rect.right(), crop_rect.top() + crop_rect.height() / 3)
            painter.drawLine(crop_rect.left(), crop_rect.top() + crop_rect.height() * 2 / 3, crop_rect.right(), crop_rect.top() + crop_rect.height() * 2 / 3)
            painter.setBrush(QColor("#22D3EE"))
            for point in (crop_rect.topLeft(), crop_rect.topRight(), crop_rect.bottomLeft(), crop_rect.bottomRight()):
                painter.drawEllipse(point, 5, 5)

    @staticmethod
    def _margins():
        from PySide6.QtCore import QSize
        return QSize(24, 24)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._crop_enabled or not self._image_rect.contains(event.position()):
            return
        rect = self._to_widget(self._crop)
        point = event.position()
        handles = {
            "top-left": rect.topLeft(), "top-right": rect.topRight(),
            "bottom-left": rect.bottomLeft(), "bottom-right": rect.bottomRight(),
        }
        self._drag_mode = next((name for name, pos in handles.items() if (point - pos).manhattanLength() <= 14), "move" if rect.contains(point) else "")
        self._drag_start = point
        self._crop_start = QRectF(self._crop)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if not self._drag_mode or self._image_rect.isEmpty():
            return
        dx = (event.position().x() - self._drag_start.x()) / self._image_rect.width()
        dy = (event.position().y() - self._drag_start.y()) / self._image_rect.height()
        rect = QRectF(self._crop_start)
        if self._drag_mode == "move":
            rect.translate(dx, dy)
            if rect.left() < 0: rect.moveLeft(0)
            if rect.top() < 0: rect.moveTop(0)
            if rect.right() > 1: rect.moveRight(1)
            if rect.bottom() > 1: rect.moveBottom(1)
        else:
            point = self._to_normalized(event.position())
            if "left" in self._drag_mode: rect.setLeft(min(point.x(), rect.right() - 0.02))
            if "right" in self._drag_mode: rect.setRight(max(point.x(), rect.left() + 0.02))
            if "top" in self._drag_mode: rect.setTop(min(point.y(), rect.bottom() - 0.02))
            if "bottom" in self._drag_mode: rect.setBottom(max(point.y(), rect.top() + 0.02))
        self._crop = rect.intersected(QRectF(0, 0, 1, 1))
        self.update()
        self.crop_changed.emit(self._crop.left(), self._crop.top(), self._crop.right(), self._crop.bottom())

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        self._drag_mode = ""

    def _to_widget(self, rect: QRectF) -> QRectF:
        return QRectF(
            self._image_rect.left() + rect.left() * self._image_rect.width(),
            self._image_rect.top() + rect.top() * self._image_rect.height(),
            rect.width() * self._image_rect.width(),
            rect.height() * self._image_rect.height(),
        )

    def _to_normalized(self, point: QPointF) -> QPointF:
        return QPointF(
            min(max((point.x() - self._image_rect.left()) / self._image_rect.width(), 0), 1),
            min(max((point.y() - self._image_rect.top()) / self._image_rect.height(), 0), 1),
        )

