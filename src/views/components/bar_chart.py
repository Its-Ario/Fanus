from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import QSizePolicy, QWidget

from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits

BarSeries = Tuple[float, str, str]
BarGroup = Tuple[str, Sequence[BarSeries]]


class BarChartWidget(QWidget):

    VERTICAL_GROUPED = "vertical_grouped"
    HORIZONTAL = "horizontal"

    def __init__(self, mode: str = VERTICAL_GROUPED, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.groups: Sequence[BarGroup] = ()
        self.overlay_text: Optional[str] = None
        self.overlay_detail: Optional[str] = None
        self.setMinimumHeight(210)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_data(
        self,
        groups: Iterable[BarGroup],
        overlay_text: Optional[str] = None,
        overlay_detail: Optional[str] = None,
    ) -> None:
        self.groups = tuple(groups)
        self.overlay_text = overlay_text
        self.overlay_detail = overlay_detail
        self.update()

    def paintEvent(self, _event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(Colors.SURFACE))
        if self.overlay_text:
            self._paint_overlay(painter)
        elif self.mode == self.HORIZONTAL:
            self._paint_horizontal(painter)
        else:
            self._paint_vertical(painter)
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

    @staticmethod
    def _nice_max(value: float) -> float:
        if value <= 1:
            return 1
        magnitude = 10 ** max(0, len(str(int(value))) - 1)
        return (int(value / magnitude) + 1) * magnitude

    @staticmethod
    def _value_text(value: float, suffix: str = "") -> str:
        text = f"{value:.1f}" if suffix or value % 1 else str(int(value))
        return to_persian_digits(text) + suffix

    def _paint_vertical(self, painter: QPainter) -> None:
        if not self.groups:
            self.overlay_text = "اطلاعاتی برای نمایش وجود ندارد"
            self._paint_overlay(painter)
            return
        label_height = 38
        label_gap = 8
        bottom_margin = 16
        plot = QRectF(
            16,
            22,
            self.width() - 32,
            self.height() - 22 - label_gap - label_height - bottom_margin,
        )
        maximum = self._nice_max(max(value for _, series in self.groups for value, _, _ in series))
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        group_width = plot.width() / len(self.groups)
        for index, (category, series) in enumerate(self.groups):
            bar_area = min(group_width * 0.72, 78)
            bar_width = max(7, (bar_area - 5 * (len(series) - 1)) / len(series))
            start_x = plot.left() + index * group_width + (group_width - bar_area) / 2
            for series_index, (value, color, label) in enumerate(series):
                height = (value / maximum) * plot.height() * 0.82
                rect = QRectF(
                    start_x + series_index * (bar_width + 5),
                    plot.bottom() - height,
                    bar_width,
                    height,
                )
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(color))
                painter.drawRoundedRect(rect, min(4, bar_width / 2), min(4, bar_width / 2))
                painter.setPen(QColor(Colors.TEXT_MUTED))
                painter.drawText(
                    QRectF(rect.left() - 16, rect.top() - 19, rect.width() + 32, 17),
                    Qt.AlignCenter,
                    self._value_text(value, label),
                )
            category_rect = QRectF(
                plot.left() + index * group_width,
                plot.bottom() + label_gap,
                group_width,
                label_height,
            )
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(category_rect, Qt.AlignCenter | Qt.TextWordWrap, category)

    def _paint_horizontal(self, painter: QPainter) -> None:
        if not self.groups:
            self.overlay_text = "اطلاعاتی برای نمایش وجود ندارد"
            self._paint_overlay(painter)
            return
        row_height = max(34, min(52, (self.height() - 24) / len(self.groups)))
        label_width = min(145, max(92, self.width() * 0.28))
        plot = QRectF(16, 12, self.width() - label_width - 42, self.height() - 24)
        maximum = self._nice_max(max(series[0][0] for _, series in self.groups))
        painter.setPen(QPen(QColor(Colors.BORDER), 1))
        painter.drawLine(plot.topRight(), plot.bottomRight())
        for index, (category, series) in enumerate(self.groups):
            value, color, suffix = series[0]
            y = plot.top() + index * row_height + (row_height - 17) / 2
            width = (value / maximum) * plot.width() * 0.88
            rect = QRectF(plot.right() - width, y, width, 17)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(rect, 5, 5)
            painter.setPen(QColor(Colors.TEXT_MAIN))
            painter.drawText(
                QRectF(self.width() - label_width - 12, y - 2, label_width, 22),
                Qt.AlignRight | Qt.AlignVCenter,
                category,
            )
            painter.setPen(QColor(Colors.TEXT_MUTED))
            painter.drawText(
                QRectF(rect.left() - 50, y - 2, 46, 22),
                Qt.AlignRight | Qt.AlignVCenter,
                self._value_text(value, suffix),
            )
