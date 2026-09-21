from __future__ import annotations

from datetime import date

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.storage import attendance_ops
from src.storage.audit import record_audit
from src.storage.models import AttendanceRecord, AttendanceStatus, Classroom, Student
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.persian_date_picker import PersianDatePicker
from src.views.components.ui_kit import Dropdown, EmptyState, PrimaryButton, SecondaryButton

_LABEL_CSS = f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};"
STATUS_COL, REASON_COL = 2, 3
_GRID_CSS = (
    f"QTableWidget {{ background: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
    f"border-radius: 10px; gridline-color: {Colors.BORDER}; color: {Colors.TEXT_MAIN}; }}"
    f"QHeaderView::section {{ background: {Colors.SURFACE_HOVER}; border: none; "
    f"border-bottom: 1px solid {Colors.BORDER}; padding: 9px; font-weight: 700; "
    f"color: {Colors.TEXT_MUTED}; }}"
    f"QTableWidget::item {{ padding: 6px; }}"
)


def _labelled(text: str, widget: QWidget) -> QWidget:
    wrapper = QWidget()
    box = QVBoxLayout(wrapper)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(4)
    label = QLabel(text)
    label.setStyleSheet(_LABEL_CSS)
    box.addWidget(label)
    box.addWidget(widget)
    return wrapper


class AttendancePage(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.read_only = bool(current_user and current_user.role != "assistant")
        self._rows: list[dict] = []
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        back = SecondaryButton("بازگشت", icon="arrow-right")
        back.clicked.connect(self._on_back)
        title = QLabel("حضور و غیاب")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        header.addWidget(back)
        header.addWidget(title)
        header.addStretch()
        layout.addLayout(header)

        self.access_notice = QLabel(
            "شما این صفحه را فقط برای مشاهده می‌بینید. ثبت و ویرایش حضور و غیاب "
            "فقط برای نقش «معاون» فعال است. برای اعمال تغییرات، با معاون مدرسه هماهنگ کنید."
        )
        self.access_notice.setWordWrap(True)
        self.access_notice.setStyleSheet(
            f"background: {Colors.SURFACE_HOVER}; border: 1px solid {Colors.BORDER}; "
            f"border-radius: 8px; padding: 9px 12px; font-size: 12px; "
            f"font-weight: 600; color: {Colors.TEXT_MAIN};"
        )
        self.access_notice.setHidden(not self.read_only)
        layout.addWidget(self.access_notice)

        self.classroom = Dropdown()
        self.date_picker = PersianDatePicker(default=date.today())
        selectors = QHBoxLayout()
        selectors.setSpacing(12)
        selectors.addWidget(_labelled("کلاس", self.classroom), 2)
        selectors.addWidget(_labelled("تاریخ", self.date_picker), 1)
        selectors.addStretch(2)
        layout.addLayout(selectors)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.hide()
        layout.addWidget(self.banner)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(("ردیف", "دانش‌آموز", "وضعیت", "توضیح"))
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(46)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setStyleSheet(_GRID_CSS)
        head = self.table.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        head.setSectionResizeMode(STATUS_COL, QHeaderView.Fixed)
        head.setSectionResizeMode(REASON_COL, QHeaderView.Stretch)
        self.table.setColumnWidth(STATUS_COL, 130)
        if self.read_only:
            self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemChanged.connect(self._on_changed)
        layout.addWidget(self.table, stretch=1)

        self.empty = EmptyState("calendar-check", "دانش‌آموزی در این کلاس نیست", "")
        self.empty.hide()
        layout.addWidget(self.empty, stretch=1)

        footer = QHBoxLayout()
        self.counter = QLabel()
        self.counter.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        footer.addWidget(self.counter)
        footer.addStretch()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self._on_back)
        footer.addWidget(cancel)
        self.save_button = PrimaryButton("ثبت حضور و غیاب")
        self.save_button.clicked.connect(self._save)
        if not self.read_only:
            footer.addWidget(self.save_button)
        layout.addLayout(footer)

        self._populate_classrooms()
        self.classroom.currentIndexChanged.connect(self._on_selector_changed)
        self.date_picker.changed.connect(self._on_selector_changed)
        self._reload()


    def showEvent(self, event):
        super().showEvent(event)
        if not self._loading and not self.has_unsaved_changes():
            self._populate_classrooms()
            self._reload()

    def _populate_classrooms(self):
        keep = self.classroom.currentText()
        self.classroom.blockSignals(True)
        self.classroom.clear()
        for room in Classroom.select().order_by(Classroom.grade_level, Classroom.name):
            self.classroom.addItem(room.name, room)
        if keep:
            self.classroom.setCurrentIndex(max(0, self.classroom.findText(keep)))
        self.classroom.blockSignals(False)

    def _status_combo(self, current: str) -> Dropdown:
        combo = Dropdown()
        for value in AttendanceStatus.VALUES:
            combo.addItem(AttendanceStatus.PERSIAN[value], value)
        combo.setCurrentIndex(max(0, combo.findData(current)))
        if self.read_only:
            combo.setEnabled(False)
        else:
            combo.currentIndexChanged.connect(self._on_changed)
        return combo

    def _reload(self):
        self._loading = True
        self.banner.hide()
        self.table.setRowCount(0)
        self._rows = []

        room = self.classroom.currentData()
        record_date = self.date_picker.date()
        students = (
            list(
                Student.select()
                .where(Student.classroom == room, Student.is_active)
                .order_by(Student.last_name, Student.first_name)
            )
            if room is not None
            else []
        )
        existing = {
            r.student_id: r
            for r in AttendanceRecord.select().where(
                AttendanceRecord.date == record_date,
                AttendanceRecord.student << [s.id for s in students],
            )
        } if students else {}

        self.table.setVisible(bool(students))
        self.empty.setVisible(room is not None and not students)

        self.table.setRowCount(len(students))
        for index, student in enumerate(students):
            record = existing.get(student.id)
            status = record.status if record else AttendanceStatus.PRESENT
            reason = record.reason if record and record.reason else ""
            self._rows.append({"student": student, "status": status, "reason": reason})

            ordinal = QTableWidgetItem(to_persian_digits(index + 1))
            ordinal.setFlags(Qt.ItemIsEnabled)
            ordinal.setTextAlignment(Qt.AlignCenter)
            name = QTableWidgetItem(student.full_name)
            name.setFlags(Qt.ItemIsEnabled)
            name.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            reason_item = QTableWidgetItem(reason)
            if self.read_only:
                reason_item.setFlags(Qt.ItemIsEnabled)
                reason_item.setForeground(QColor(Colors.TEXT_MUTED))
            self.table.setItem(index, 0, ordinal)
            self.table.setItem(index, 1, name)
            self.table.setItem(index, REASON_COL, reason_item)
            self.table.setCellWidget(index, STATUS_COL, self._status_combo(status))

        self._loading = False
        self._refresh()


    def _row_values(self, index: int) -> tuple[str, str]:
        combo = self.table.cellWidget(index, STATUS_COL)
        item = self.table.item(index, REASON_COL)
        status = combo.currentData() if combo else AttendanceStatus.PRESENT
        return status, (item.text().strip() if item else "")

    def _on_changed(self, *_):
        if not self._loading:
            self._refresh()

    def _refresh(self):
        absent = late = excused = 0
        for index in range(self.table.rowCount()):
            status, _ = self._row_values(index)
            absent += status == AttendanceStatus.ABSENT
            late += status == AttendanceStatus.LATE
            excused += status == AttendanceStatus.EXCUSED
        parts = []
        if absent:
            parts.append(f"{to_persian_digits(absent)} غایب")
        if late:
            parts.append(f"{to_persian_digits(late)} تأخیر")
        if excused:
            parts.append(f"{to_persian_digits(excused)} غیبت موجه")
        self.counter.setText(" · ".join(parts) if parts else "همه حاضر")
        self.save_button.setEnabled(not self.read_only and self.has_unsaved_changes())

    def has_unsaved_changes(self) -> bool:
        if self.read_only:
            return False
        for index, base in enumerate(self._rows):
            status, reason = self._row_values(index)
            if status != base["status"] or reason != base["reason"]:
                return True
        return False

    def confirm_navigation_away(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        answer = QMessageBox.question(
            self,
            "تغییرات ذخیره‌نشده",
            "حضور و غیاب ذخیره‌نشده دارید. بدون ثبت خارج می‌شوید؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _on_back(self):
        if self.confirm_navigation_away():
            self.back_requested.emit()

    def _on_selector_changed(self, *_):
        if self.has_unsaved_changes() and not self.confirm_navigation_away():
            return
        self._reload()


    def _banner(self, text: str, ok: bool = False):
        fg, bg = (Colors.SUCCESS, Colors.SUCCESS_BG) if ok else (Colors.ERROR, Colors.ERROR_BG)
        self.banner.setText(text)
        self.banner.setStyleSheet(
            f"background: {bg}; border: 1px solid {fg}; border-radius: 8px; padding: 8px 12px; "
            f"font-size: 12px; font-weight: 600; color: {fg};"
        )
        self.banner.show()

    def _save(self):
        record_date = self.date_picker.date()
        entries = []
        for index, base in enumerate(self._rows):
            status, reason = self._row_values(index)
            if status == base["status"] and reason == base["reason"]:
                continue
            entries.append({"student": base["student"], "status": status, "reason": reason})
        if not entries:
            self._banner("تغییری برای ثبت وجود ندارد.")
            return
        try:
            result = attendance_ops.save_attendance_bulk(
                record_date, entries, actor=self.current_user
            )
        except Exception as error:
            self._banner(f"ثبت نشد: {error}")
            return

        if self.current_user is not None:
            record_audit(
                self.current_user,
                "attendance.bulk_save",
                "AttendanceRecord",
                details="{} · {} · {} ثبت، {} ویرایش".format(
                    self.classroom.currentText(),
                    to_persian_digits(record_date.isoformat()),
                    to_persian_digits(result.created),
                    to_persian_digits(result.updated),
                ),
            )
        self._reload()
        self._banner(
            "ثبت شد: {} جدید، {} ویرایش".format(
                to_persian_digits(result.created), to_persian_digits(result.updated)
            ),
            ok=True,
        )
