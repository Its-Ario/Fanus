from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from peewee import IntegrityError
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QRectF, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from src.storage.models import Classroom, Student
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.ui_kit import (
    EmptyState,
    Dropdown,
    FormField,
    PrimaryButton,
    SearchInput,
    SecondaryButton,
)

PAGE_SIZE = 25


@dataclass(frozen=True)
class StudentPage:
    students: tuple[Student, ...]
    total: int


def load_students_page(query: str = "", page: int = 0, page_size: int = PAGE_SIZE) -> StudentPage:
    """Read only the requested active-student slice from the local database."""
    query_builder = Student.select(Student, Classroom).join(Classroom).where(Student.is_active)
    normalized = query.strip()
    if normalized:
        query_builder = query_builder.where(
            (Student.first_name.contains(normalized))
            | (Student.last_name.contains(normalized))
            | (Student.national_id.contains(normalized))
        )

    total = query_builder.count()
    students = tuple(
        query_builder.order_by(Student.last_name, Student.first_name).paginate(page + 1, page_size)
    )
    return StudentPage(students=students, total=total)


class StudentTableModel(QAbstractTableModel):
    HEADERS = ("نام دانش آموز", "کد ملی", "کلاس", "رشته", "ریسک", "وضعیت")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.students: tuple[Student, ...] = ()

    def set_students(self, students: tuple[Student, ...]):
        self.beginResetModel()
        self.students = students
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.students)

    def columnCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self.HEADERS[section]
        return super().headerData(section, orientation, role)

    def data(self, index, role=Qt.DisplayRole):
        if not index.isValid() or not 0 <= index.row() < len(self.students):
            return None
        student = self.students[index.row()]
        values = (
            student.full_name,
            student.national_id,
            student.classroom.name,
            student.major,
            student.risk_level,
            "فعال" if student.is_active else "غیرفعال",
        )
        if role == Qt.DisplayRole:
            return values[index.column()]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.UserRole:
            return student
        return None


class RiskBadgeDelegate(QStyledItemDelegate):
    COLORS = {
        "Low": (Colors.SUCCESS_BG, Colors.SUCCESS, "کم"),
        "Medium": (Colors.WARNING_BG, Colors.WARNING, "متوسط"),
        "High": (Colors.ERROR_BG, Colors.ERROR, "زیاد"),
    }

    def paint(self, painter, option, index):
        level = index.data(Qt.DisplayRole)
        background, foreground, label = self.COLORS.get(level, self.COLORS["Low"])
        rect = option.rect.adjusted(12, 9, -12, -9)
        painter.save()
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(QRectF(rect), 10, 10)
        painter.setPen(QColor(foreground))
        painter.drawText(rect, Qt.AlignCenter, label)
        painter.restore()


class NewStudentDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("دانش آموز جدید")
        self.setMinimumWidth(390)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        self.first_name = FormField("نام", "برای مثال: سارا")
        self.last_name = FormField("نام خانوادگی", "برای مثال: احمدی")
        self.national_id = FormField("کد ملی", "۱۰ رقم")
        self.classroom = Dropdown()
        self._classrooms = tuple(Classroom.select().order_by(Classroom.grade_level, Classroom.name))
        for room in self._classrooms:
            self.classroom.addItem(room.name, room)

        class_label = QLabel("کلاس")
        class_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")
        self.error = QLabel()
        self.error.setWordWrap(True)
        self.error.setStyleSheet(f"font-size: 11px; color: {Colors.ERROR};")
        self.error.hide()

        layout.addWidget(self.first_name)
        layout.addWidget(self.last_name)
        layout.addWidget(self.national_id)
        layout.addWidget(class_label)
        layout.addWidget(self.classroom)
        layout.addWidget(self.error)

        actions = QHBoxLayout()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self.reject)
        save = PrimaryButton("ثبت دانش آموز")
        save.clicked.connect(self._save)
        actions.addWidget(cancel)
        actions.addStretch()
        actions.addWidget(save)
        layout.addLayout(actions)

    @staticmethod
    def _normalize_digits(value: str) -> str:
        return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))

    def _show_error(self, message: str):
        self.error.setText(message)
        self.error.show()

    def _save(self):
        first_name, last_name = self.first_name.text(), self.last_name.text()
        national_id = self._normalize_digits(self.national_id.text())
        classroom = self.classroom.currentData()
        if not first_name or not last_name or not classroom:
            self._show_error("نام، نام خانوادگی و کلاس را وارد کنید.")
            return
        if len(national_id) != 10 or not national_id.isdigit():
            self._show_error("کد ملی باید دقیقا ۱۰ رقم باشد.")
            return
        try:
            Student.create(
                first_name=first_name,
                last_name=last_name,
                national_id=national_id,
                classroom=classroom,
                major=classroom.major,
            )
        except IntegrityError:
            self._show_error("دانش آموزی با این کد ملی قبلا ثبت شده است.")
            return
        self.accept()


class StudentsPage(QWidget):
    student_opened = pyqtSignal(object)

    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self._loaded = False
        self._page = 0
        self._query = ""
        self._total = 0

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(250)
        self.search_timer.timeout.connect(self._apply_search)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("دانش آموزان")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        subtitle = QLabel("فهرست دانش آموزان فعال مدرسه")
        subtitle.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        add_button = PrimaryButton("دانش آموز جدید", icon="+")
        add_button.clicked.connect(self._open_new_student)
        header.addWidget(add_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self.result_label = QLabel("در حال آماده سازی فهرست")
        self.result_label.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        self.search_input = SearchInput("نام یا کد ملی را جستجو کنید")
        self.search_input.setMinimumWidth(300)
        self.search_input.textChanged.connect(self._schedule_search)
        controls.addWidget(self.result_label)
        controls.addStretch()
        controls.addWidget(self.search_input)
        layout.addLayout(controls)

        self.error_banner = QFrame()
        self.error_banner.setStyleSheet(
            f"QFrame {{ background: {Colors.ERROR_BG}; border: 1px solid {Colors.ERROR}; border-radius: 8px; }}"
        )
        banner_layout = QHBoxLayout(self.error_banner)
        banner_layout.setContentsMargins(12, 7, 12, 7)
        self.error_banner_label = QLabel("فهرست به روز نشد؛ اطلاعات قبلی نمایش داده می شود.")
        self.error_banner_label.setStyleSheet(
            f"font-size: 12px; color: {Colors.ERROR}; font-weight: 600;"
        )
        retry_banner_button = SecondaryButton("تلاش دوباره")
        retry_banner_button.setFixedHeight(30)
        retry_banner_button.clicked.connect(self.reload)
        banner_layout.addWidget(self.error_banner_label)
        banner_layout.addStretch()
        banner_layout.addWidget(retry_banner_button)
        self.error_banner.hide()
        layout.addWidget(self.error_banner)

        self.table = QTableView()
        self.model = StudentTableModel(self)
        self.table.setModel(self.model)
        self.table.setItemDelegateForColumn(4, RiskBadgeDelegate(self.table))
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet(
            f"QTableView {{ background: {Colors.SURFACE}; border: 1px solid {Colors.BORDER}; "
            f"border-radius: 10px; gridline-color: {Colors.BORDER}; color: {Colors.TEXT_MAIN}; }}"
            f"QHeaderView::section {{ background: {Colors.SURFACE_HOVER}; border: none; "
            f"border-bottom: 1px solid {Colors.BORDER}; padding: 10px; font-weight: 700; color: {Colors.TEXT_MUTED}; }}"
            f"QTableView::item {{ padding: 8px; border-bottom: 1px solid {Colors.BORDER}; }}"
            f"QTableView::item:selected {{ background: {Colors.PRIMARY}18; color: {Colors.TEXT_MAIN}; }}"
        )
        self.table.doubleClicked.connect(self._open_selected_student)

        self.state_frame = QFrame()
        state_layout = QVBoxLayout(self.state_frame)
        state_layout.setContentsMargins(0, 0, 0, 0)
        self.loading_state = EmptyState("…", "در حال بارگذاری دانش آموزان", "چند لحظه صبر کنید.")
        self.empty_state = EmptyState(
            "",
            "هنوز دانش آموز فعالی ثبت نشده است",
            "برای شروع، اولین دانش آموز را ثبت کنید.",
            "دانش آموز جدید",
            self._open_new_student,
        )
        self.no_results_state = EmptyState(
            "",
            "دانش آموزی پیدا نشد",
            "عبارت جستجو را بررسی کنید یا جستجو را پاک کنید.",
            "پاک کردن جستجو",
            self._clear_search,
        )
        self.error_state = EmptyState(
            "!",
            "فهرست دانش آموزان بارگذاری نشد",
            "اتصال پایگاه داده را بررسی کنید و دوباره تلاش کنید.",
            "تلاش دوباره",
            self.reload,
        )
        self._states = (
            self.loading_state,
            self.empty_state,
            self.no_results_state,
            self.error_state,
        )
        for state in self._states:
            state.hide()
            state_layout.addWidget(state)
        layout.addWidget(self.table, stretch=1)
        layout.addWidget(self.state_frame, stretch=1)
        self.state_frame.hide()

        pagination = QHBoxLayout()
        self.previous_button = SecondaryButton("صفحه قبل")
        self.previous_button.clicked.connect(lambda: self._go_to_page(self._page - 1))
        self.page_label = QLabel()
        self.page_label.setAlignment(Qt.AlignCenter)
        self.page_label.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
        self.next_button = SecondaryButton("صفحه بعد")
        self.next_button.clicked.connect(lambda: self._go_to_page(self._page + 1))
        pagination.addWidget(self.previous_button)
        pagination.addStretch()
        pagination.addWidget(self.page_label)
        pagination.addStretch()
        pagination.addWidget(self.next_button)
        layout.addLayout(pagination)
        self._update_pagination()

    def showEvent(self, event):
        super().showEvent(event)
        if not self._loaded:
            self.reload()

    def _schedule_search(self):
        self.search_timer.start()

    def _apply_search(self):
        self._query = self.search_input.text().strip()
        self._page = 0
        self.reload()

    def _go_to_page(self, page: int):
        if page >= 0 and page < self.page_count:
            self._page = page
            self.reload()

    @property
    def page_count(self) -> int:
        return max(1, ceil(self._total / PAGE_SIZE))

    def _show_state(self, state):
        self.table.setVisible(state is None)
        self.state_frame.setVisible(state is not None)
        for candidate in self._states:
            candidate.setVisible(candidate is state)

    def reload(self):
        had_rows = bool(self.model.students)
        if not had_rows:
            self._show_state(self.loading_state)
        try:
            result = load_students_page(self._query, self._page)
        except Exception:
            if had_rows:
                self.error_banner.show()
            else:
                self._show_state(self.error_state)
            return
        self._loaded = True
        self.error_banner.hide()
        self._total = result.total
        self.model.set_students(result.students)
        self._update_pagination()
        if result.total:
            self._show_state(None)
        elif self._query:
            self._show_state(self.no_results_state)
        else:
            self._show_state(self.empty_state)

    def _update_pagination(self):
        self.previous_button.setHidden(not self._page > 0)
        self.next_button.setHidden(not self._page + 1 < self.page_count)
        self.page_label.setText(
            f"صفحه {to_persian_digits(self._page + 1)} از {to_persian_digits(self.page_count)}"
        )
        self.result_label.setText(f"{to_persian_digits(self._total)} دانش آموز فعال")

    def _clear_search(self):
        self.search_input.clear()
        self._query = ""
        self._page = 0
        self.reload()

    def _open_selected_student(self, index):
        student = index.data(Qt.UserRole)
        if student:
            self.student_opened.emit(student)

    def _open_new_student(self):
        if NewStudentDialog(self).exec_() == QDialog.Accepted:
            self._page = 0
            self._query = ""
            self.search_input.blockSignals(True)
            self.search_input.clear()
            self.search_input.blockSignals(False)
            self.reload()
