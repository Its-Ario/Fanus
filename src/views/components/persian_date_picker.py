from __future__ import annotations

from datetime import date

import jdatetime
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.ui_kit import Dropdown

_MONTH_NAMES = (
    "فروردین",
    "اردیبهشت",
    "خرداد",
    "تیر",
    "مرداد",
    "شهریور",
    "مهر",
    "آبان",
    "آذر",
    "دی",
    "بهمن",
    "اسفند",
)


def _days_in_month(jy: int, jm: int) -> int:
    if jm <= 6:
        return 31
    if jm <= 11:
        return 30
    return 30 if jdatetime.date(jy, 1, 1).isleap() else 29


class PersianDatePicker(QWidget):
    changed = pyqtSignal()

    def __init__(self, label=None, default=None, min_year=None, max_year=None):
        super().__init__()
        default = default or date.today()
        this_year = jdatetime.date.today().year
        min_year = min_year or this_year - 5
        max_year = max_year or this_year + 5

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        if label:
            self.label = QLabel(label)
            self.label.setStyleSheet(
                f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};"
            )
            layout.addWidget(self.label)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)

        self.year = Dropdown()
        for year in range(max_year, min_year - 1, -1):
            self.year.addItem(to_persian_digits(year), year)

        self.month = Dropdown()
        for number, name in enumerate(_MONTH_NAMES, start=1):
            self.month.addItem(name, number)

        self.day = Dropdown()

        row.addWidget(self.day, 1)
        row.addWidget(self.month, 2)
        row.addWidget(self.year, 2)
        layout.addLayout(row)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet(f"font-size: 11px; color: {Colors.ERROR};")
        self.message.setVisible(False)
        layout.addWidget(self.message)

        self._rebuild_days()
        self.set_date(default)

        self.year.currentIndexChanged.connect(self._on_ym_changed)
        self.month.currentIndexChanged.connect(self._on_ym_changed)
        self.day.currentIndexChanged.connect(self._on_changed)

    def _rebuild_days(self):
        jy, jm = self.year.currentData(), self.month.currentData()
        if jy is None or jm is None:
            return
        wanted = self.day.currentData() or 1
        count = _days_in_month(jy, jm)
        self.day.blockSignals(True)
        self.day.clear()
        for number in range(1, count + 1):
            self.day.addItem(to_persian_digits(number), number)
        self.day.setCurrentIndex(min(wanted, count) - 1)
        self.day.blockSignals(False)

    def _on_ym_changed(self, _index):
        self._rebuild_days()
        self._on_changed()

    def _on_changed(self, _index=None):
        self.clear_error()
        self.changed.emit()

    def date(self) -> date:
        return jdatetime.date(
            self.year.currentData(), self.month.currentData(), self.day.currentData()
        ).togregorian()

    def set_date(self, value: date):
        jalali = jdatetime.date.fromgregorian(date=value)
        self.year.setCurrentIndex(self.year.findData(jalali.year))
        self.month.setCurrentIndex(self.month.findData(jalali.month))
        self._rebuild_days()
        self.day.setCurrentIndex(self.day.findData(jalali.day))

    def set_error(self, message: str):
        self.message.setText(message)
        self.message.setVisible(True)

    def clear_error(self):
        self.message.setVisible(False)
