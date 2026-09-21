from __future__ import annotations

from dataclasses import dataclass
from math import ceil

from peewee import IntegrityError
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QTableView,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.storage.audit import record_audit
from src.storage.models import (
    GRADE_ORDINALS,
    AcademicMajor,
    Classroom,
    Student,
)
from src.storage.student_ops import bulk_create_students, read_roster, write_roster
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.ui_kit import (
    ActionDropdown,
    Dropdown,
    EmptyState,
    FormField,
    PrimaryButton,
    SearchInput,
    SecondaryButton,
)

PAGE_SIZE = 25

SORT_COLUMNS = (
    (Student.last_name, Student.first_name),
    (Student.national_id,),
    (Classroom.grade_level, Classroom.name),
    (Student.major,),
    (Student.is_active,),
)


@dataclass(frozen=True)
class StudentPage:
    students: tuple[Student, ...]
    total: int


def _filtered_student_query(
    query: str = "",
    *,
    major: str = "",
    grade_level=None,
    classroom_id=None,
    sort_key: int = 0,
    sort_desc: bool = False,
):
    query_builder = Student.select(Student, Classroom).join(Classroom).where(Student.is_active)
    normalized = query.strip()
    if normalized:
        query_builder = query_builder.where(
            (Student.first_name.contains(normalized))
            | (Student.last_name.contains(normalized))
            | (Student.national_id.contains(normalized))
        )
    if major:
        query_builder = query_builder.where(Student.major == major)
    if grade_level is not None:
        query_builder = query_builder.where(Classroom.grade_level == grade_level)
    if classroom_id is not None:
        query_builder = query_builder.where(Student.classroom == classroom_id)
    columns = SORT_COLUMNS[sort_key] if 0 <= sort_key < len(SORT_COLUMNS) else SORT_COLUMNS[0]
    order = [column.desc() if sort_desc else column for column in columns]
    return query_builder.order_by(*order)


def load_students_page(
    query: str = "",
    page: int = 0,
    page_size: int = PAGE_SIZE,
    *,
    major: str = "",
    grade_level=None,
    classroom_id=None,
    sort_key: int = 0,
    sort_desc: bool = False,
) -> StudentPage:
    query_builder = _filtered_student_query(
        query,
        major=major,
        grade_level=grade_level,
        classroom_id=classroom_id,
        sort_key=sort_key,
        sort_desc=sort_desc,
    )
    total = query_builder.count()
    students = tuple(query_builder.paginate(page + 1, page_size))
    return StudentPage(students=students, total=total)


def load_all_students(query: str = "", **filters) -> tuple[Student, ...]:
    return tuple(_filtered_student_query(query, **filters))


class StudentTableModel(QAbstractTableModel):
    HEADERS = ("نام دانش آموز", "کد ملی", "کلاس", "رشته", "وضعیت")

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
            "فعال" if student.is_active else "غیرفعال",
        )
        if role == Qt.DisplayRole:
            return values[index.column()]
        if role == Qt.TextAlignmentRole:
            return Qt.AlignRight | Qt.AlignVCenter
        if role == Qt.UserRole:
            return student
        return None


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


class ImportPreviewDialog(QDialog):

    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("پیش‌نمایش ورود دانش آموزان")
        self.setMinimumWidth(460)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 20)
        layout.setSpacing(12)

        summary = QLabel(
            f"{to_persian_digits(result.created)} افزوده می‌شود · "
            f"{to_persian_digits(len(result.skipped))} رد شده · "
            f"{to_persian_digits(len(result.errors))} خطا"
        )
        summary.setStyleSheet(f"font-size: 13px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        layout.addWidget(summary)

        problems = list(result.errors) + list(result.skipped)
        if problems:
            table = QTableWidget(len(problems), 3, self)
            table.setHorizontalHeaderLabels(("ردیف", "کد ملی", "دلیل"))
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QAbstractItemView.NoEditTriggers)
            table.horizontalHeader().setStretchLastSection(True)
            for row, item in enumerate(problems):
                table.setItem(row, 0, QTableWidgetItem(to_persian_digits(item.line)))
                table.setItem(row, 1, QTableWidgetItem(to_persian_digits(item.national_id or "—")))
                table.setItem(row, 2, QTableWidgetItem(item.reason))
            table.setMinimumHeight(180)
            layout.addWidget(table)

        actions = QHBoxLayout()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self.reject)
        confirm = PrimaryButton("افزودن")
        confirm.clicked.connect(self.accept)
        confirm.setEnabled(result.created > 0)
        actions.addWidget(cancel)
        actions.addStretch()
        actions.addWidget(confirm)
        layout.addLayout(actions)


class StudentsPage(QWidget):
    student_opened = pyqtSignal(object)

    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self._loaded = False
        self._page = 0
        self._query = ""
        self._total = 0
        self._sort_key = 0
        self._sort_desc = False
        self._scope_loaded = False
        self._all_rooms: tuple[Classroom, ...] = ()

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
        subtitle = QLabel("مدیریت و مشاهده اطلاعات دانش‌آموزان")
        subtitle.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles)
        header.addStretch()
        add_button = PrimaryButton("دانش آموز جدید", icon="+")
        add_button.clicked.connect(self._open_new_student)
        header.addWidget(add_button)
        operations_button = ActionDropdown()
        operations_button.add_action("ورود از فایل", self._open_import)
        operations_button.add_action("خروجی فایل", self._export_roster)
        header.addWidget(operations_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        controls.setSpacing(10)
        self.search_input = SearchInput("جستجو بر اساس نام، کد ملی...")
        self.search_input.setFixedWidth(280)
        self.search_input.textChanged.connect(self._schedule_search)

        self.major_filter = Dropdown()
        self.major_filter.setFixedWidth(150)
        self.major_filter.addItem("همه رشته‌ها", "")
        for value in AcademicMajor.VALUES:
            self.major_filter.addItem(value, value)
        self.major_filter.currentIndexChanged.connect(self._on_scope_changed)

        self.grade_filter = Dropdown()
        self.grade_filter.setFixedWidth(120)
        self.grade_filter.addItem("همه پایه‌ها", None)
        self.grade_filter.currentIndexChanged.connect(self._on_scope_changed)

        self.class_filter = Dropdown()
        self.class_filter.setFixedWidth(150)
        self.class_filter.addItem("همه کلاس‌ها", None)
        self.class_filter.currentIndexChanged.connect(self._apply_filters)

        controls.addWidget(self.search_input)
        controls.addWidget(self.grade_filter)
        controls.addWidget(self.major_filter)
        controls.addWidget(self.class_filter)
        controls.addStretch()
        self.clear_filters_button = SecondaryButton("پاک کردن فیلترها")
        self.clear_filters_button.clicked.connect(self._clear_filters)
        controls.addWidget(self.clear_filters_button)
        self.result_label = QLabel("تعداد: — نفر")
        self.result_label.setStyleSheet(
            f"background: {Colors.SURFACE_HOVER}; color: {Colors.TEXT_MUTED}; "
            f"border: 1px solid {Colors.BORDER}; border-radius: 12px; "
            "padding: 6px 10px; font-size: 12px; font-weight: 600;"
        )
        controls.addWidget(self.result_label)
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
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(48)
        header_view = self.table.horizontalHeader()
        header_view.setStretchLastSection(True)
        header_view.setSectionsClickable(True)
        header_view.setSortIndicatorShown(True)
        header_view.setSortIndicator(self._sort_key, Qt.AscendingOrder)
        header_view.sectionClicked.connect(self._sort_by_section)
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

    def _ensure_scope_options(self):
        if self._scope_loaded:
            return
        try:
            rooms = tuple(Classroom.select().order_by(Classroom.grade_level, Classroom.name))
        except Exception:
            return
        self._all_rooms = rooms
        self.grade_filter.blockSignals(True)
        for grade in sorted({room.grade_level for room in rooms}):
            self.grade_filter.addItem(GRADE_ORDINALS.get(grade, str(grade)), grade)
        self.grade_filter.blockSignals(False)
        self._scope_loaded = True
        self._rebuild_class_options()

    def _rebuild_class_options(self):
        major = self.major_filter.currentData()
        grade = self.grade_filter.currentData()
        current = self.class_filter.currentData()
        self.class_filter.blockSignals(True)
        self.class_filter.clear()
        self.class_filter.addItem("همه کلاس‌ها", None)
        for room in self._all_rooms:
            if major and room.major != major:
                continue
            if grade is not None and room.grade_level != grade:
                continue
            self.class_filter.addItem(room.name, room.id)
        index = self.class_filter.findData(current)
        self.class_filter.setCurrentIndex(index if index >= 0 else 0)
        self.class_filter.blockSignals(False)

    def _on_scope_changed(self):
        self._rebuild_class_options()
        self._apply_filters()

    def _apply_filters(self):
        self._page = 0
        self.reload()

    def _sort_by_section(self, section: int):
        if section == self._sort_key:
            self._sort_desc = not self._sort_desc
        else:
            self._sort_key = section
            self._sort_desc = False
        order = Qt.DescendingOrder if self._sort_desc else Qt.AscendingOrder
        self.table.horizontalHeader().setSortIndicator(section, order)
        self._page = 0
        self.reload()

    def _has_filters(self) -> bool:
        return (
            bool(self.major_filter.currentData())
            or self.grade_filter.currentData() is not None
            or self.class_filter.currentData() is not None
        )

    def reload(self):
        self._ensure_scope_options()
        had_rows = bool(self.model.students)
        if not had_rows:
            self._show_state(self.loading_state)
        try:
            result = load_students_page(
                self._query,
                self._page,
                major=self.major_filter.currentData(),
                grade_level=self.grade_filter.currentData(),
                classroom_id=self.class_filter.currentData(),
                sort_key=self._sort_key,
                sort_desc=self._sort_desc,
            )
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
        elif self._query or self._has_filters():
            self._show_state(self.no_results_state)
        else:
            self._show_state(self.empty_state)

    def _update_pagination(self):
        self.previous_button.setHidden(not self._page > 0)
        self.next_button.setHidden(not self._page + 1 < self.page_count)
        self.page_label.setText(
            f"صفحه {to_persian_digits(self._page + 1)} از {to_persian_digits(self.page_count)}"
        )
        self.result_label.setText(f"تعداد: {to_persian_digits(self._total)} نفر")
        self.clear_filters_button.setEnabled(self._has_filters())

    def _reset_filters(self):
        for combo in (self.major_filter, self.grade_filter, self.class_filter):
            combo.blockSignals(True)
            combo.setCurrentIndex(0)
            combo.blockSignals(False)
        self._rebuild_class_options()

    def _clear_search(self):
        self.search_input.clear()
        self._clear_filters(reload=False)
        self._query = ""
        self._page = 0
        self.reload()

    def _clear_filters(self, checked=False, reload=True):
        self._reset_filters()
        if reload:
            self._apply_filters()

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
            self._reset_filters()
            self.reload()

    def _current_filters(self) -> dict:
        return dict(
            major=self.major_filter.currentData(),
            grade_level=self.grade_filter.currentData(),
            classroom_id=self.class_filter.currentData(),
            sort_key=self._sort_key,
            sort_desc=self._sort_desc,
        )

    def _export_roster(self):
        path, chosen = QFileDialog.getSaveFileName(
            self, "خروجی فهرست دانش آموزان", "دانش‌آموزان.xlsx", "Excel (*.xlsx);;CSV (*.csv)"
        )
        if not path:
            return
        if not path.lower().endswith((".xlsx", ".csv")):
            path += ".csv" if "csv" in chosen.lower() else ".xlsx"
        try:
            students = load_all_students(self._query, **self._current_filters())
            write_roster(path, students)
        except Exception:
            QMessageBox.critical(self, "خطا", "خروجی گرفته نشد؛ دوباره تلاش کنید.")
            return
        QMessageBox.information(
            self, "خروجی انجام شد", f"{to_persian_digits(len(students))} دانش آموز خروجی گرفته شد."
        )

    def _open_import(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "ورود دانش آموزان از فایل", "", "Excel/CSV (*.xlsx *.csv)"
        )
        if not path:
            return
        try:
            rows = read_roster(path)
        except (ValueError, OSError) as exc:
            QMessageBox.critical(self, "فایل نامعتبر", str(exc))
            return
        if not rows:
            QMessageBox.information(self, "فایل خالی", "هیچ ردیفی در فایل پیدا نشد.")
            return
        try:
            preview = bulk_create_students(rows, commit=False)
        except Exception:
            QMessageBox.critical(self, "خطا", "پردازش فایل ممکن نشد.")
            return
        if ImportPreviewDialog(preview, self).exec_() != QDialog.Accepted:
            return
        try:
            result = bulk_create_students(rows, commit=True, actor=self.current_user)
        except Exception:
            QMessageBox.critical(
                self, "خطا", "ثبت دانش آموزان ممکن نشد؛ هیچ رکوردی اضافه نشد."
            )
            return
        if self.current_user is not None:
            record_audit(
                self.current_user,
                "student.bulk_import",
                "Student",
                None,
                details=(
                    f"{result.created} افزوده، {len(result.skipped)} رد، "
                    f"{len(result.errors)} خطا"
                ),
            )
        self._page = 0
        self._query = ""
        self.search_input.blockSignals(True)
        self.search_input.clear()
        self.search_input.blockSignals(False)
        self._reset_filters()
        self.reload()
        QMessageBox.information(
            self, "ورود انجام شد", f"{to_persian_digits(result.created)} دانش آموز اضافه شد."
        )
