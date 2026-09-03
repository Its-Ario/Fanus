from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits


class LineChartWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.points: Sequence[Tuple[str, Optional[float]]] = ()
        self.overlay_text: Optional[str] = None
        self.overlay_detail: Optional[str] = None
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(
        self,
        points: Iterable[Tuple[str, Optional[float]]],
        overlay_text: Optional[str] = None,
        overlay_detail: Optional[str] = None,
    ) -> None:
        self.points = tuple(points)
        self.overlay_text = overlay_text
        self.overlay_detail = overlay_detail
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(Colors.SURFACE))
        if self.overlay_text:
            self._paint_overlay(painter)
        else:
            self._paint_chart(painter)
        painter.end()

    def _paint_overlay(self, painter: QPainter) -> None:
        box = QRectF(self.rect()).adjusted(28, self.height() / 2 - 34, -28, -self.height() / 2 + 34)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(Colors.SURFACE_HOVER))
        painter.drawRoundedRect(box, 10, 10)
        painter.setPen(QColor(Colors.TEXT_MAIN))
        painter.drawText(box.adjusted(12, 8, -12, -20), Qt.AlignCenter, self.overlay_text)
        if self.overlay_detail:
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(box.adjusted(12, 29, -12, -4), Qt.AlignCenter, self.overlay_detail)

    def _paint_chart(self, painter: QPainter) -> None:
        if not self.points:
            self.overlay_text = "اطلاعاتی برای نمایش وجود ندارد"
            self._paint_overlay(painter)
            return
        plot = QRectF(22, 26, self.width() - 44, self.height() - 73)
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        values = [value for _, value in self.points if value is not None]
        maximum = max(100.0, max(values) if values else 100.0)
        step = plot.width() / max(1, len(self.points) - 1)
        previous = None
        for index, (label, value) in enumerate(self.points):
            x = plot.right() - index * step
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(x - 34, plot.bottom() + 8, 68, 30), Qt.AlignCenter | Qt.TextWordWrap, label
            )
            if value is None:
                previous = None
                continue
            point = QPointF(x, plot.bottom() - value / maximum * plot.height() * 0.8)
            if previous is not None:
                painter.setPen(QPen(QColor(Colors.PRIMARY), 2.5))
                painter.drawLine(previous, point)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(Colors.PRIMARY))
            painter.drawEllipse(point, 4, 4)
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(x - 28, point.y() - 22, 56, 17),
                Qt.AlignCenter,
                to_persian_digits(f"{value:.0f}٪"),
            )
            previous = point
