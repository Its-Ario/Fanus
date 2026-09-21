from __future__ import annotations

import re
from datetime import date

from PyQt5.QtCore import (
    QAbstractTableModel,
    QEvent,
    QModelIndex,
    Qt,
    QTimer,
    pyqtSignal,
)
from PyQt5.QtGui import QColor, QValidator
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QStackedWidget,
    QStyledItemDelegate,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from src.storage import grade_ops
from src.storage.audit import record_audit
from src.storage.db import db
from src.storage.models import (
    AcademicGrade,
    Classroom,
    Exam,
    ExamClassroom,
    GradeTerm,
    GradeValidationError,
    Student,
    subject_options,
)
from src.styles.theme import Colors
from src.utils.persian_utils import to_ascii_digits, to_persian_digits
from src.views.components.persian_date_picker import PersianDatePicker
from src.views.components.ui_kit import (
    Dropdown,
    EmptyState,
    FormField,
    PrimaryButton,
    SecondaryButton,
)

_LABEL_CSS = f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};"
SCORE_COL_START = 2


def _field(placeholder: str = "") -> QLineEdit:
    box = QLineEdit()
    box.setPlaceholderText(placeholder)
    box.setFixedHeight(38)
    box.setStyleSheet(
        f"QLineEdit {{ background: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
        f"border-radius: 8px; padding: 0 10px; color: {Colors.TEXT_MAIN}; font-size: 13px; }}"
        f"QLineEdit:focus {{ border: 2px solid {Colors.PRIMARY}; }}"
    )
    return box


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


_GRID_CSS = (
    f"QTableWidget {{ background: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
    f"border-radius: 10px; gridline-color: {Colors.BORDER}; color: {Colors.TEXT_MAIN}; }}"
    f"QHeaderView::section {{ background: {Colors.SURFACE_HOVER}; border: none; "
    f"border-bottom: 1px solid {Colors.BORDER}; padding: 9px; font-weight: 700; "
    f"color: {Colors.TEXT_MUTED}; }}"
    f"QTableWidget::item {{ padding: 6px; }}"
)

class _PersianNumberValidator(QValidator):
    def validate(self, text, pos):
        ascii_text = to_ascii_digits(text)
        if ascii_text != text:
            return (QValidator.Acceptable, ascii_text, pos)
        if ascii_text == "" or re.fullmatch(r"\d*\.?\d*", ascii_text):
            return (QValidator.Acceptable, ascii_text, pos)
        return (QValidator.Invalid, text, pos)


class _ScoreDelegate(QStyledItemDelegate):
    move = pyqtSignal(int, int)

    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        editor.setAlignment(Qt.AlignCenter)
        editor.setValidator(_PersianNumberValidator(editor))
        return editor

    def eventFilter(self, editor, event):
        if event.type() == QEvent.KeyPress:
            key, mods = event.key(), event.modifiers()
            step = None
            if key in (Qt.Key_Return, Qt.Key_Enter):
                step = (-1, 0) if mods & Qt.ShiftModifier else (1, 0)
            elif key == Qt.Key_Down:
                step = (1, 0)
            elif key == Qt.Key_Up:
                step = (-1, 0)
            elif key in (Qt.Key_Tab, Qt.Key_Left):
                step = (0, 1)
            elif key in (Qt.Key_Backtab, Qt.Key_Right):
                step = (0, -1)
            if step is not None:
                self.commitData.emit(editor)
                self.closeEditor.emit(editor)
                self.move.emit(*step)
                return True
        return super().eventFilter(editor, event)


class _ScoreGrid(QTableWidget):

    changed = pyqtSignal()

    def __init__(self, exam: Exam, room: Classroom, read_only: bool, parent=None):
        self.subjects = list(exam.subjects)
        super().__init__(0, SCORE_COL_START + len(self.subjects), parent)
        self.exam = exam
        self.room = room
        self.read_only = read_only
        self.score_cols = range(SCORE_COL_START, SCORE_COL_START + len(self.subjects))
        self.rows_model: list[dict] = []
        self._loading = False

        self.setHorizontalHeaderLabels(["ردیف", "دانش‌آموز", *self.subjects])
        self.verticalHeader().setVisible(False)
        self.setLayoutDirection(Qt.RightToLeft)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setAlternatingRowColors(False)
        self.setStyleSheet(_GRID_CSS)
        head = self.horizontalHeader()
        head.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        head.setSectionResizeMode(1, QHeaderView.Stretch)
        for col in self.score_cols:
            head.setSectionResizeMode(col, QHeaderView.Fixed)
            self.setColumnWidth(col, 120)

        if read_only:
            self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        else:
            self.setEditTriggers(
                QAbstractItemView.DoubleClicked
                | QAbstractItemView.SelectedClicked
                | QAbstractItemView.EditKeyPressed
                | QAbstractItemView.AnyKeyPressed
            )
            self._delegate = _ScoreDelegate(self)
            self._delegate.move.connect(self._move_cursor)
            for col in self.score_cols:
                self.setItemDelegateForColumn(col, self._delegate)

        self.itemChanged.connect(self._on_item_changed)
        self._load()


    def _load(self):
        self._loading = True
        students = list(
            Student.select()
            .where(Student.classroom == self.room, Student.is_active)
            .order_by(Student.last_name, Student.first_name)
        )
        grades: dict[tuple, AcademicGrade] = {}
        if students:
            for grade in AcademicGrade.select().where(
                AcademicGrade.exam == self.exam,
                AcademicGrade.student << [s.id for s in students],
            ):
                grades[(grade.student_id, grade.subject_name)] = grade

        self.setRowCount(len(students))
        for row, student in enumerate(students):
            cells: dict[str, str] = {}
            ordinal = QTableWidgetItem(to_persian_digits(row + 1))
            ordinal.setFlags(Qt.ItemIsEnabled)
            ordinal.setTextAlignment(Qt.AlignCenter)
            name = QTableWidgetItem(student.full_name)
            name.setFlags(Qt.ItemIsEnabled)
            name.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.setItem(row, 0, ordinal)
            self.setItem(row, 1, name)
            for col, subject in zip(self.score_cols, self.subjects):
                grade = grades.get((student.id, subject))
                loaded = (
                    to_persian_digits(f"{grade.score:g}")
                    if grade is not None and grade.score is not None
                    else ""
                )
                cells[subject] = to_ascii_digits(loaded)
                item = QTableWidgetItem(loaded)
                item.setTextAlignment(Qt.AlignCenter)
                if self.read_only:
                    item.setFlags(Qt.ItemIsEnabled)
                    item.setForeground(QColor(Colors.TEXT_MUTED))
                self.setItem(row, col, item)
            self.rows_model.append({"student": student, "cells": cells})

        self._loading = False
        if self.rowCount() and not self.read_only:
            self.setCurrentCell(0, SCORE_COL_START)


    def keyPressEvent(self, event):
        if (
            event.key() in (Qt.Key_Return, Qt.Key_Enter)
            and self.state() != QAbstractItemView.EditingState
            and self.currentColumn() in self.score_cols
        ):
            item = self.currentItem()
            if item is not None and item.flags() & Qt.ItemIsEditable:
                self.editItem(item)
                return
        super().keyPressEvent(event)

    def _move_cursor(self, row_step: int, col_step: int):
        row = self.currentRow() + row_step
        col = self.currentColumn() + col_step
        if not 0 <= row < self.rowCount():
            row = self.currentRow()
        if col not in self.score_cols:
            col = self.currentColumn()

        def open_target():
            self.setCurrentCell(row, col)
            item = self.item(row, col)
            if item is not None and item.flags() & Qt.ItemIsEditable:
                self.editItem(item)

        QTimer.singleShot(0, open_target)

    def _on_item_changed(self, item):
        if self._loading or item.column() not in self.score_cols:
            return
        self.changed.emit()

    def cell_error(self, text: str) -> str | None:
        raw = to_ascii_digits((text or "").strip())
        if not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            return "عدد نامعتبر"
        ceiling = self.exam.max_score
        if not 0 <= value <= ceiling:
            return f"نمره باید بین ۰ و {to_persian_digits(f'{ceiling:g}')} باشد"
        return None

    def apply_validation(self) -> int:
        invalid = 0
        self._loading = True
        for row in range(self.rowCount()):
            for col in self.score_cols:
                item = self.item(row, col)
                if item is None:
                    continue
                error = self.cell_error(item.text())
                if error:
                    item.setBackground(QColor(Colors.ERROR_BG))
                    item.setToolTip(error)
                    invalid += 1
                else:
                    item.setBackground(QColor(Colors.SURFACE))
                    item.setToolTip("")
        self._loading = False
        return invalid

    def filled_count(self) -> int:
        count = 0
        for row in range(self.rowCount()):
            for col in self.score_cols:
                item = self.item(row, col)
                if item and to_ascii_digits(item.text().strip()):
                    count += 1
        return count

    def total_count(self) -> int:
        return self.rowCount() * len(self.subjects)

    def _iter_cells(self):
        for row, model in enumerate(self.rows_model):
            for col, subject in zip(self.score_cols, self.subjects):
                item = self.item(row, col)
                raw = to_ascii_digits(item.text().strip()) if item else ""
                yield model, subject, raw

    def dirty(self) -> bool:
        return any(raw != model["cells"][subject] for model, subject, raw in self._iter_cells())

    def collect_changes(self) -> list[dict]:
        out = []
        for model, subject, raw in self._iter_cells():
            if raw == model["cells"][subject]:
                continue
            out.append(
                {"student": model["student"], "subject_name": subject, "score": raw or None}
            )
        return out

    def rebaseline(self):
        for model, subject, raw in self._iter_cells():
            model["cells"][subject] = raw




class ExamGridView(QWidget):
    back_requested = pyqtSignal()
    saved = pyqtSignal()

    def __init__(self, exam: Exam, current_user=None, read_only: bool = False, parent=None):
        super().__init__(parent)
        self.exam = exam
        self.current_user = current_user
        self.read_only = read_only
        self._grids: list[_ScoreGrid] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        back = SecondaryButton("بازگشت", icon="←")
        back.clicked.connect(self.back_requested.emit)
        title = QLabel(exam.name)
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        meta = QLabel(
            "{} · {} · سقف {}".format(
                exam.term,
                to_persian_digits(exam.exam_date.isoformat()),
                to_persian_digits(f"{exam.max_score:g}"),
            )
        )
        meta.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        header.addWidget(back)
        header.addWidget(title)
        header.addSpacing(10)
        header.addWidget(meta)
        header.addStretch()
        layout.addLayout(header)

        self.banner = QLabel()
        self.banner.setWordWrap(True)
        self.banner.hide()
        layout.addWidget(self.banner)

        self.tabs = QTabWidget()
        rooms = [ec.classroom for ec in exam.exam_classrooms.order_by(ExamClassroom.created_at)]
        for room in rooms:
            grid = _ScoreGrid(exam, room, read_only)
            if grid.rowCount() == 0:
                self.tabs.addTab(
                    EmptyState("", "دانش‌آموزی در این کلاس نیست", ""), room.name
                )
                continue
            grid.changed.connect(self._refresh)
            self._grids.append(grid)
            self.tabs.addTab(grid, room.name)
        self.tabs.tabBar().setVisible(self.tabs.count() != 1)
        self.tabs.currentChanged.connect(self._on_tab)
        layout.addWidget(self.tabs, stretch=1)

        footer = QHBoxLayout()
        self.counter = QLabel()
        self.counter.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        footer.addWidget(self.counter)
        footer.addStretch()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self.back_requested.emit)
        footer.addWidget(cancel)
        self.save_button = PrimaryButton("ثبت نمرات")
        self.save_button.clicked.connect(self._save)
        if not read_only:
            footer.addWidget(self.save_button)
        layout.addLayout(footer)

        self._refresh()
        self._on_tab(self.tabs.currentIndex())


    def _on_tab(self, index):
        widget = self.tabs.widget(index)
        if isinstance(widget, _ScoreGrid) and widget.rowCount() and not self.read_only:
            widget.setCurrentCell(0, SCORE_COL_START)

    def _refresh(self):
        filled = sum(g.filled_count() for g in self._grids)
        total = sum(g.total_count() for g in self._grids)
        invalid = sum(g.apply_validation() for g in self._grids)
        self.counter.setText(
            "{} از {} نمره وارد شده".format(
                to_persian_digits(filled), to_persian_digits(total)
            )
        )
        self.save_button.setEnabled(not self.read_only and invalid == 0)

    def _banner(self, text: str, ok: bool = False):
        fg, bg = (Colors.SUCCESS, Colors.SUCCESS_BG) if ok else (Colors.ERROR, Colors.ERROR_BG)
        self.banner.setText(text)
        self.banner.setStyleSheet(
            f"background: {bg}; border: 1px solid {fg}; border-radius: 8px; padding: 8px 12px; "
            f"font-size: 12px; font-weight: 600; color: {fg};"
        )
        self.banner.show()

    def has_unsaved_changes(self) -> bool:
        if self.read_only:
            return False
        return any(g.dirty() for g in self._grids)

    def _save(self):
        if self._refresh() is None and any(g.apply_validation() for g in self._grids):
            return
        entries = [entry for g in self._grids for entry in g.collect_changes()]
        if not entries:
            self._banner("تغییری برای ثبت وجود ندارد.")
            return
        try:
            result = grade_ops.save_grades_bulk(self.exam, entries, actor=self.current_user)
        except Exception as error:
            self._banner(f"ثبت نشد: {error}")
            return

        if self.current_user is not None:
            record_audit(
                self.current_user,
                "grade.bulk_save",
                "AcademicGrade",
                target_id=self.exam.id,
                details="{} · {} ثبت، {} ویرایش، {} غایب".format(
                    self.exam.name,
                    to_persian_digits(result.created),
                    to_persian_digits(result.updated),
                    to_persian_digits(result.cleared),
                ),
            )

        for grid in self._grids:
            grid.rebaseline()
        self._refresh()
        self._banner(
            "ثبت شد: {} جدید، {} ویرایش، {} غایب".format(
                to_persian_digits(result.created),
                to_persian_digits(result.updated),
                to_persian_digits(result.cleared),
            ),
            ok=True,
        )
        self.saved.emit()




class _ExamTableModel(QAbstractTableModel):
    HEADERS = ("نام آزمون", "تاریخ", "نوبت", "کلاس‌ها", "درس‌ها", "پیشرفت")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.rows: list[tuple[Exam, str]] = []

    def set_rows(self, rows):
        self.beginResetModel()
        self.rows = rows
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.rows):
            return None
        exam, progress = self.rows[index.row()]
        if role == Qt.UserRole:
            return exam
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        if role != Qt.DisplayRole:
            return None
        return (
            exam.name,
            to_persian_digits(exam.exam_date.isoformat()),
            exam.term,
            f"{to_persian_digits(exam.classroom_count)} کلاس",
            f"{to_persian_digits(len(exam.subjects))} درس",
            progress,
        )[index.column()]


class ExamListView(QWidget):
    exam_opened = pyqtSignal(object)
    new_exam_requested = pyqtSignal()

    def __init__(self, read_only: bool = False, parent=None):
        super().__init__(parent)
        self.read_only = read_only

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("ثبت نمرات")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        header.addWidget(title)
        header.addStretch()
        self.new_button = PrimaryButton("آزمون جدید", icon="+")
        self.new_button.clicked.connect(self.new_exam_requested.emit)
        if not read_only:
            header.addWidget(self.new_button)
        layout.addLayout(header)

        self.table = QTableView()
        self.model = _ExamTableModel(self)
        self.table.setModel(self.model)
        self.table.setLayoutDirection(Qt.RightToLeft)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            f"QTableView {{ background: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
            f"border-radius: 10px; gridline-color: {Colors.BORDER}; color: {Colors.TEXT_MAIN}; }}"
            f"QHeaderView::section {{ background: {Colors.SURFACE_HOVER}; border: none; "
            f"border-bottom: 1px solid {Colors.BORDER}; padding: 9px; font-weight: 700; "
            f"color: {Colors.TEXT_MUTED}; }}"
            f"QTableView::item {{ padding: 8px; }}"
        )
        self.table.doubleClicked.connect(self._open)
        layout.addWidget(self.table, stretch=1)

        self.empty_state = EmptyState(
            "",
            "هنوز آزمونی ثبت نشده است",
            "برای ثبت نمرات، ابتدا یک آزمون تعریف کنید.",
            None if read_only else "آزمون جدید",
            None if read_only else self.new_exam_requested.emit,
        )
        self.empty_state.hide()
        layout.addWidget(self.empty_state, stretch=1)

    def showEvent(self, event):
        super().showEvent(event)
        self.reload()

    def reload(self):
        rows = []
        for exam in Exam.select().order_by(Exam.exam_date.desc()):
            room_ids = [ec.classroom_id for ec in exam.exam_classrooms]
            exam.classroom_count = len(room_ids)
            students = (
                Student.select()
                .where(Student.classroom << room_ids, Student.is_active)
                .count()
                if room_ids
                else 0
            )
            total = students * len(exam.subjects)
            filled = (
                AcademicGrade.select()
                .where(AcademicGrade.exam == exam, AcademicGrade.score.is_null(False))
                .count()
            )
            rows.append(
                (
                    exam,
                    "{} از {}".format(to_persian_digits(filled), to_persian_digits(total)),
                )
            )
        self.model.set_rows(rows)
        self.table.setVisible(bool(rows))
        self.empty_state.setVisible(not rows)

    def _open(self, index):
        exam = index.data(Qt.UserRole)
        if exam is not None:
            self.exam_opened.emit(exam)




class NewExamDialog(QDialog):
    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.exam: Exam | None = None
        self.setWindowTitle("آزمون جدید")
        self.setMinimumWidth(430)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        self.name = FormField("نام آزمون", "برای مثال: میان‌ترم زیست")
        self.term = Dropdown()
        for value in GradeTerm.VALUES:
            self.term.addItem(value, value)
        self.exam_date = PersianDatePicker(default=date.today())
        self.max_score = _field("۲۰")
        self.max_score.setText(to_persian_digits("20"))

        self.classes = QListWidget()
        self.classes.setFixedHeight(120)
        self.subjects = QListWidget()
        self.subjects.setFixedHeight(120)
        self.subjects.setEnabled(False)
        self._rooms = list(
            Classroom.select().order_by(Classroom.grade_level, Classroom.name)
        )
        for room in self._rooms:
            item = QListWidgetItem(room.name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, room)
            self.classes.addItem(item)
        self.classes.itemChanged.connect(self._on_classes_changed)

        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"font-size: 11px; color: {Colors.ERROR};")
        self.error.hide()

        layout.addWidget(self.name)
        layout.addWidget(_labelled("نوبت", self.term))
        layout.addWidget(_labelled("تاریخ آزمون", self.exam_date))
        layout.addWidget(_labelled("سقف نمره", self.max_score))
        layout.addWidget(_labelled("کلاس‌ها", self.classes))
        layout.addWidget(_labelled("درس‌ها", self.subjects))
        layout.addWidget(self.error)

        actions = QHBoxLayout()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self.reject)
        save = PrimaryButton("ثبت آزمون")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addStretch()
        actions.addWidget(save)
        layout.addLayout(actions)


    def _checked_rooms(self) -> list[Classroom]:
        rooms = []
        for index in range(self.classes.count()):
            item = self.classes.item(index)
            if item.checkState() == Qt.Checked:
                rooms.append(item.data(Qt.UserRole))
        return rooms

    def _on_classes_changed(self, _item):
        rooms = self._checked_rooms()
        self.classes.blockSignals(True)
        if rooms:
            gate = (rooms[0].grade_level, rooms[0].major)
            for index in range(self.classes.count()):
                item = self.classes.item(index)
                room = item.data(Qt.UserRole)
                match = (room.grade_level, room.major) == gate
                item.setFlags(
                    item.flags() | Qt.ItemIsEnabled
                    if match
                    else item.flags() & ~Qt.ItemIsEnabled
                )
        else:
            for index in range(self.classes.count()):
                item = self.classes.item(index)
                item.setFlags(item.flags() | Qt.ItemIsEnabled)
        self.classes.blockSignals(False)
        self._rebuild_subjects(rooms)

    def _rebuild_subjects(self, rooms):
        kept = {
            self.subjects.item(i).text()
            for i in range(self.subjects.count())
            if self.subjects.item(i).checkState() == Qt.Checked
        }
        self.subjects.blockSignals(True)
        self.subjects.clear()
        if rooms:
            options = subject_options(rooms[0].grade_level, rooms[0].major)
            for name in options:
                item = QListWidgetItem(name)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Checked if name in kept else Qt.Unchecked)
                self.subjects.addItem(item)
            self.subjects.setEnabled(True)
        else:
            self.subjects.setEnabled(False)
        self.subjects.blockSignals(False)

    def _checked_subjects(self) -> list[str]:
        return [
            self.subjects.item(i).text()
            for i in range(self.subjects.count())
            if self.subjects.item(i).checkState() == Qt.Checked
        ]


    def _show_error(self, message: str):
        self.error.setText(message)
        self.error.show()

    def _save(self):
        rooms = self._checked_rooms()
        subjects = self._checked_subjects()
        exam_date = self.exam_date.date()
        try:
            max_score = float(to_ascii_digits(self.max_score.text().strip()))
        except ValueError:
            max_score = None

        if not self.name.text():
            self._show_error("نام آزمون را وارد کنید.")
            return
        if not rooms:
            self._show_error("حداقل یک کلاس را انتخاب کنید.")
            return
        if not subjects:
            self._show_error("حداقل یک درس را انتخاب کنید.")
            return
        if max_score is None or not 0 < max_score <= 100:
            self._show_error("سقف نمره باید بین ۰ تا ۱۰۰ باشد.")
            return

        try:
            with db.atomic():
                exam = Exam(
                    name=self.name.text(),
                    exam_date=exam_date,
                    term=self.term.currentData(),
                    max_score=max_score,
                    grade_level=rooms[0].grade_level,
                    major=rooms[0].major,
                )
                exam.subjects = subjects
                exam.save(force_insert=True)
                for room in rooms:
                    ExamClassroom.create(exam=exam, classroom=room)
        except GradeValidationError as error:
            self._show_error(str(error))
            return

        if self.current_user is not None:
            record_audit(
                self.current_user,
                "exam.create",
                "Exam",
                target_id=exam.id,
                details="{} · {} کلاس · {} درس".format(
                    exam.name,
                    to_persian_digits(len(rooms)),
                    to_persian_digits(len(subjects)),
                ),
            )
        self.exam = exam
        self.accept()




class GradeEntryPage(QWidget):

    back_requested = pyqtSignal()

    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.read_only = bool(current_user and current_user.role == "principal")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)

        self.list_view = ExamListView(read_only=self.read_only)
        self.list_view.exam_opened.connect(self._open_grid)
        self.list_view.new_exam_requested.connect(self._new_exam)
        self.stack.addWidget(self.list_view)
        self.grid_view: ExamGridView | None = None


    def _open_grid(self, exam: Exam):
        if not self.confirm_navigation_away():
            return
        self._mount_grid(exam)

    def _mount_grid(self, exam: Exam):
        if self.grid_view is not None:
            self.stack.removeWidget(self.grid_view)
            self.grid_view.deleteLater()
        self.grid_view = ExamGridView(exam, self.current_user, self.read_only)
        self.grid_view.back_requested.connect(self._show_list)
        self.stack.addWidget(self.grid_view)
        self.stack.setCurrentWidget(self.grid_view)

    def _show_list(self):
        if not self.confirm_navigation_away():
            return
        self.stack.setCurrentWidget(self.list_view)
        self.list_view.reload()

    def _new_exam(self):
        dialog = NewExamDialog(self.current_user, self)
        if dialog.exec_() == QDialog.Accepted and dialog.exam is not None:
            self._mount_grid(dialog.exam)


    def has_unsaved_changes(self) -> bool:
        return (
            self.grid_view is not None
            and self.stack.currentWidget() is self.grid_view
            and self.grid_view.has_unsaved_changes()
        )

    def confirm_navigation_away(self) -> bool:
        if not self.has_unsaved_changes():
            return True
        answer = QMessageBox.question(
            self,
            "نمرات ذخیره‌نشده",
            "نمرات ذخیره‌نشده دارید. بدون ثبت خارج می‌شوید؟",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def showEvent(self, event):
        super().showEvent(event)
        if self.stack.currentWidget() is self.list_view:
            self.list_view.reload()
