from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Iterable

from peewee import fn
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QPainter, QPen
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from src.planner import generator
from src.storage.db import DatabaseCredentials, get_database_manager
from src.storage.models import (
    GRADE_ORDINALS,
    MOADEL_TERMS,
    AcademicGrade,
    AttendanceRecord,
    DailyCheckIn,
    DayOfWeek,
    Exam,
    PlanStatus,
    StudyPlan,
    StudySession,
    subject_options,
)
from src.storage.note_ops import (
    NotePermissionError,
    NoteValidationError,
    create_note,
    list_note_audit,
    list_notes,
    update_note,
)
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.persian_date_picker import PersianDatePicker
from src.views.components.ui_kit import (
    Card,
    Dropdown,
    EmptyState,
    FormField,
    PrimaryButton,
    SecondaryButton,
)
from src.views.pages.settings.settings_page import SEGMENTED_STYLE


def _latin_digits(value: str) -> str:
    return value.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


def _duration_minutes(start_time: str, end_time: str) -> int:
    try:
        start = datetime.strptime(_latin_digits(start_time), "%H:%M")
        end = datetime.strptime(_latin_digits(end_time), "%H:%M")
    except ValueError as exc:
        raise ValueError("زمان را با قالب HH:MM وارد کنید.") from exc
    minutes = int((end - start).total_seconds() // 60)
    if minutes <= 0:
        raise ValueError("زمان پایان باید بعد از زمان شروع باشد.")
    return minutes


class _DeleteRowButton(QToolButton):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(28, 28)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("حذف جلسه")
        self.setAccessibleName("حذف جلسه")
        self.setStyleSheet(f"""
            QToolButton {{ background: transparent; border: 1px solid transparent; border-radius: 6px; }}
            QToolButton:hover {{ background: {Colors.ERROR_BG}; }}
            QToolButton:pressed {{ background: {Colors.ERROR_BG}; border-color: {Colors.ERROR}; }}
            QToolButton:focus {{ border: 2px solid {Colors.ERROR}; }}
        """)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        color = QColor(Colors.ERROR if self.underMouse() else Colors.TEXT_MUTED)
        painter.setPen(QPen(color, 1.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        left, top = 8, 7
        painter.drawLine(left - 1, top + 3, left + 13, top + 3)
        painter.drawLine(left + 5, top + 1, left + 8, top + 1)
        painter.drawLine(left + 2, top + 5, left + 3, top + 14)
        painter.drawLine(left + 12, top + 5, left + 11, top + 14)
        painter.drawLine(left + 3, top + 14, left + 11, top + 14)
        painter.drawLine(left + 6, top + 6, left + 6, top + 12)
        painter.drawLine(left + 9, top + 6, left + 9, top + 12)


def create_manual_plan(
    student, start_date: date, end_date: date, title="برنامه مطالعاتی دستی"
) -> StudyPlan:
    if end_date < start_date:
        raise ValueError("تاریخ پایان نمی تواند قبل از تاریخ شروع باشد.")
    if (
        StudyPlan.select()
        .where(StudyPlan.student == student, StudyPlan.status == PlanStatus.ACTIVE)
        .exists()
    ):
        raise ValueError("یک برنامه فعال از قبل وجود دارد؛ ابتدا آن را آرشیو کنید.")
    return StudyPlan.create(
        student=student,
        title=title,
        start_date=start_date,
        end_date=end_date,
        status=PlanStatus.ACTIVE,
        is_approved=True,
        is_ai_generated=False,
    )


def save_plan_sessions(plan: StudyPlan, sessions: Iterable[dict]) -> None:
    normalized = []
    for session in sessions:
        day = int(session["day_of_week"])
        if day not in DayOfWeek.PERSIAN_NAMES:
            raise ValueError("روز هفته نامعتبر است.")
        subject = str(session["subject_name"]).strip()
        if not subject:
            raise ValueError("نام درس را وارد کنید.")
        start, end = _latin_digits(session["start_time"]), _latin_digits(session["end_time"])
        normalized.append(
            {
                "day_of_week": day,
                "start_time": start,
                "end_time": end,
                "subject_name": subject,
                "session_type": str(session.get("session_type") or "مطالعه").strip(),
                "duration_minutes": _duration_minutes(start, end),
            }
        )
    database = StudyPlan._meta.database
    with database.atomic():
        StudySession.delete().where(StudySession.plan == plan).execute()
        if normalized:
            StudySession.insert_many([{"plan": plan, **row} for row in normalized]).execute()


def archive_plan(plan: StudyPlan) -> None:
    plan.status = PlanStatus.ARCHIVED
    plan.save()


def regenerate_plan(student):
    active = StudyPlan.get_or_none(
        StudyPlan.student == student, StudyPlan.status == PlanStatus.ACTIVE
    )
    database = StudyPlan._meta.database
    with database.atomic():
        result = generator.generate_plan(
            student,
            generator.get_student_params(student, keep_locked=bool(active)),
        )
        if active:
            active.status = PlanStatus.ARCHIVED
            active.save()
        plan = result.plan
        plan.title = "برنامه مطالعاتی هوشمند"
        plan.status = PlanStatus.ACTIVE
        plan.is_approved = True
        plan.approved_at = datetime.now()
        plan.save()
    return plan, result.warnings


class SummaryTab(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 12, 0, 0)
        self.layout.setSpacing(14)

    def reload(self):
        _clear_layout(self.layout)
        student = self.panel.student
        if not student:
            return
        facts = Card()
        grid = QGridLayout()
        grid.setSpacing(12)
        grade_rows = (
            AcademicGrade.select()
            .join(Exam)
            .where(
                AcademicGrade.student == student,
                AcademicGrade.score.is_null(False),
                Exam.term << MOADEL_TERMS,
            )
            .count()
        )
        gpa = student.calculate_gpa()
        values = (
            ("معدل", "—" if not grade_rows else f"{gpa:.2f}"),
        )
        for index, (label, value) in enumerate(values):
            box = QVBoxLayout()
            heading = QLabel(label)
            heading.setStyleSheet(f"font-size:12px; color:{Colors.TEXT_MUTED};")
            value_widget = QLabel(to_persian_digits(value))
            value_widget.setStyleSheet(
                f"font-size:20px; font-weight:800; color:{Colors.TEXT_MAIN};"
            )
            box.addWidget(heading)
            box.addWidget(value_widget)
            holder = QWidget()
            holder.setLayout(box)
            grid.addWidget(holder, 0, index)
        facts.body_layout.addLayout(grid)
        self.layout.addWidget(facts)

        self._add_grades(student)

        attendance = Card()
        attendance.body_layout.addWidget(_section_title("حضور و غیاب"))
        since = date.today() - timedelta(days=30)
        count = (
            AttendanceRecord.select()
            .where(AttendanceRecord.student == student, AttendanceRecord.date >= since)
            .count()
        )
        message = QLabel(
            f"{to_persian_digits(count)} رکورد حضور و غیاب در ۳۰ روز گذشته"
            if count
            else "هنوز رکورد حضور و غیابی برای این دانش آموز ثبت نشده است."
        )
        message.setStyleSheet(f"font-size:13px; color:{Colors.TEXT_MUTED}; padding:8px 0;")
        attendance.body_layout.addWidget(message)
        self.layout.addWidget(attendance)

        user = self.panel.current_user
        if user and user.role == "assistant":
            self.layout.addStretch()
            return
        history = Card()
        history.body_layout.addWidget(_section_title("تاریخچه برنامه ها"))
        rows = (
            StudyPlan.select()
            .where(StudyPlan.student == student, StudyPlan.status != PlanStatus.ACTIVE)
            .order_by(StudyPlan.start_date.desc())
        )
        table = QTableWidget(0, 3)
        table.setHorizontalHeaderLabels(("عنوان", "بازه زمانی", "وضعیت"))
        _style_table(table)
        rows = list(rows)
        table.setRowCount(len(rows))
        for row_index, plan in enumerate(rows):
            table.setItem(row_index, 0, QTableWidgetItem(plan.title))
            table.setItem(row_index, 1, QTableWidgetItem(f"{plan.start_date} تا {plan.end_date}"))
            table.setItem(
                row_index, 2, QTableWidgetItem(PlanStatus.PERSIAN_MAP.get(plan.status, plan.status))
            )
        table.setMinimumHeight(max(72, min(210, 38 * (len(rows) + 1))))
        history.body_layout.addWidget(table)
        self.layout.addWidget(history)
        self.layout.addStretch()

    def _add_grades(self, student):
        grades = Card()
        grades.body_layout.addWidget(_section_title("نمرات"))
        toggle = QCheckBox("نمایش امتحان‌های کلاسی و آزمایشی")
        toggle.setLayoutDirection(Qt.RightToLeft)
        grades.body_layout.addWidget(toggle)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(("درس", "نمره", "نوع", "تاریخ"))
        _style_table(table)

        def populate(show_extra=False):
            terms = MOADEL_TERMS + (("مستمر",) if not show_extra else ())
            query = (
                AcademicGrade.select(AcademicGrade, Exam)
                .join(Exam)
                .where(AcademicGrade.student == student, Exam.term << terms)
                .order_by(Exam.exam_date.desc(), AcademicGrade.created_at.desc())
            )
            rows = list(query)
            table.setRowCount(len(rows))
            for index, row in enumerate(rows):
                ceiling = row.exam.max_score
                table.setItem(index, 0, QTableWidgetItem(row.subject_name))
                if row.score is None:
                    score = QTableWidgetItem("غایب")
                    score.setForeground(QColor(Colors.TEXT_MUTED))
                else:
                    score = QTableWidgetItem(to_persian_digits(f"{row.score:g}/{ceiling:g}"))
                    if row.score < ceiling / 2:
                        score.setForeground(QColor(Colors.ERROR))
                table.setItem(index, 1, score)
                table.setItem(index, 2, QTableWidgetItem(row.exam.term))
                table.setItem(
                    index, 3, QTableWidgetItem(to_persian_digits(row.exam.exam_date.isoformat()))
                )
            table.setMinimumHeight(max(72, min(250, 38 * (len(rows) + 1))))

        toggle.toggled.connect(populate)
        populate()
        grades.body_layout.addWidget(table)
        self.layout.addWidget(grades)

        recent = Card()
        recent.body_layout.addWidget(_section_title("۵ امتحان اخیر"))
        rows = (
            AcademicGrade.select(AcademicGrade, Exam)
            .join(Exam)
            .where(AcademicGrade.student == student)
            .order_by(Exam.exam_date.desc(), AcademicGrade.created_at.desc())
            .limit(5)
        )
        values = list(rows)
        if not values:
            recent.body_layout.addWidget(QLabel("هنوز نمره‌ای ثبت نشده است."))
        for row in values:
            shown = (
                "غایب"
                if row.score is None
                else to_persian_digits(f"{row.score:g}/{row.exam.max_score:g}")
            )
            label = QLabel(f"{row.subject_name} — {shown} ({row.exam.term})")
            label.setStyleSheet(f"font-size:13px; color:{Colors.TEXT_MAIN}; padding:3px 0;")
            recent.body_layout.addWidget(label)
        self.layout.addWidget(recent)


class PlanTab(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.plan = None
        self.editor_rows: list[dict] = []
        self.creating = False
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 12, 0, 0)
        self.layout.setSpacing(14)

    def reload(self):
        self.plan = StudyPlan.get_or_none(
            StudyPlan.student == self.panel.student, StudyPlan.status == PlanStatus.ACTIVE
        )
        self._show_view()

    def _show_view(self):
        _clear_layout(self.layout)
        if not self.plan:
            empty = EmptyState(
                "",
                "هنوز برنامه مطالعاتی فعالی ثبت نشده است.",
                "برنامه را با موتور هوشمند بسازید یا به صورت دستی وارد کنید.",
                "+ ساخت برنامه جدید",
                self._begin_create,
            )
            self.layout.addWidget(empty, 1)
            generate = SecondaryButton("⚡ تولید با موتور هوشمند")
            generate.clicked.connect(self._regenerate)
            self.layout.addWidget(generate, 0, Qt.AlignHCenter)
            return
        checkins = (
            DailyCheckIn.select(fn.AVG(DailyCheckIn.completion_rate))
            .where(
                DailyCheckIn.student == self.panel.student,
                DailyCheckIn.date.between(self.plan.start_date, self.plan.end_date),
            )
            .scalar()
        )
        status = f"وضعیت فعلی: {PlanStatus.PERSIAN_MAP[self.plan.status]}"
        status += " (تأیید شده)" if self.plan.is_approved else " (در انتظار تأیید)"
        status += f" | نرخ پایبندی: {to_persian_digits(round(checkins or 0))}٪"
        line = QLabel(status)
        line.setStyleSheet(f"font-size:14px; font-weight:700; color:{Colors.TEXT_MAIN};")
        self.layout.addWidget(line)
        actions = QHBoxLayout()
        regenerate = SecondaryButton("⚡ تولید مجدد")
        regenerate.clicked.connect(self._regenerate)
        edit = PrimaryButton("ویرایش دستی", icon="✏️")
        edit.clicked.connect(self._begin_edit)
        export = SecondaryButton("🖨️ چاپ برنامه A4 PDF")
        export.setEnabled(False)
        export.setToolTip("خروجی PDF هنوز فعال نشده است.")
        archive = SecondaryButton("پایان برنامه", icon="🗄️")
        archive.clicked.connect(self._archive)
        for button in (regenerate, edit, export, archive):
            actions.addWidget(button)
        actions.addStretch()
        self.layout.addLayout(actions)
        self.layout.addWidget(self._session_grid(self.plan.get_active_sessions()), 1)

    def _session_grid(self, sessions):
        table = QTableWidget(0, 7)
        table.setHorizontalHeaderLabels(tuple(DayOfWeek.PERSIAN_NAMES[i] for i in range(7)))
        _style_table(table)
        header = table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(QHeaderView.Stretch)
        table.setWordWrap(True)
        table.setTextElideMode(Qt.ElideNone)
        table.verticalHeader().setDefaultSectionSize(62)
        buckets = {day: [] for day in range(7)}
        for session in sessions:
            buckets[session.day_of_week].append(session)
        row_count = max(1, max((len(items) for items in buckets.values()), default=0))
        table.setRowCount(row_count)
        for day, items in buckets.items():
            for row, session in enumerate(items):
                table.setItem(
                    row,
                    day,
                    QTableWidgetItem(
                        f"{session.subject_name}\n{session.start_time}–{session.end_time}\n{session.session_type}"
                    ),
                )
        return table

    def _begin_create(self):
        self.creating, self.plan, self.editor_rows = True, None, []
        self._show_editor()

    def _begin_edit(self):
        self.creating = False
        self.editor_rows = [
            dict(
                day_of_week=s.day_of_week,
                start_time=s.start_time,
                end_time=s.end_time,
                subject_name=s.subject_name,
                session_type=s.session_type,
            )
            for s in self.plan.get_active_sessions()
        ]
        self._show_editor()

    def _show_editor(self):
        _clear_layout(self.layout)
        if self.creating:
            dates = QHBoxLayout()
            self.start_date = PersianDatePicker("تاریخ شروع", default=date.today())
            self.end_date = PersianDatePicker(
                "تاریخ پایان", default=date.today() + timedelta(days=6)
            )
            dates.addWidget(self.start_date)
            dates.addWidget(self.end_date)
            self.layout.addLayout(dates)
        else:
            label = QLabel(f"ویرایش {self.plan.title}")
            label.setStyleSheet(f"font-size:15px; font-weight:800; color:{Colors.TEXT_MAIN};")
            self.layout.addWidget(label)
        form = QHBoxLayout()
        self.day = Dropdown()
        for key, name in DayOfWeek.PERSIAN_NAMES.items():
            self.day.addItem(name, key)
        self.start = FormField("شروع", "16:00")
        self.end = FormField("پایان", "17:30")
        self.subject = Dropdown()
        subjects = subject_options(
            self.panel.student.classroom.grade_level,
            self.panel.student.classroom.major,
        )
        if subjects:
            self.subject.addItem("انتخاب درس")
            self.subject.addItems(subjects)
        else:
            self.subject.setEditable(True)
            self.subject.setPlaceholderText("مثلاً ریاضی")
        self.kind = Dropdown()
        self.kind.addItems(("مطالعه", "تمرین", "مرور"))
        add = PrimaryButton("افزودن جلسه", icon="+")
        add.clicked.connect(self._add_row)
        form.addWidget(self.day)
        form.addWidget(self.start)
        form.addWidget(self.end)
        form.addWidget(self.subject)
        form.addWidget(self.kind)
        form.addWidget(add)
        self.layout.addLayout(form)
        self.editor_table = QTableWidget(0, 6)
        self.editor_table.setHorizontalHeaderLabels(("روز", "شروع", "پایان", "درس", "نوع", ""))
        _style_table(self.editor_table)
        header = self.editor_table.horizontalHeader()
        header.setStretchLastSection(False)
        for column in (0, 1, 2, 4):
            header.setSectionResizeMode(column, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.Fixed)
        self.editor_table.setColumnWidth(5, 44)
        self.editor_table.verticalHeader().setDefaultSectionSize(38)
        self.layout.addWidget(self.editor_table, 1)
        self._render_editor_rows()
        actions = QHBoxLayout()
        cancel = SecondaryButton("انصراف")
        cancel.clicked.connect(self._cancel_editor)
        save = PrimaryButton("ذخیره برنامه")
        save.clicked.connect(self._save_editor)
        actions.addWidget(cancel)
        actions.addStretch()
        actions.addWidget(save)
        self.layout.addLayout(actions)

    def _add_row(self):
        try:
            row = {
                "day_of_week": self.day.currentData(),
                "start_time": self.start.text(),
                "end_time": self.end.text(),
                "subject_name": self.subject.currentText().strip(),
                "session_type": self.kind.currentText(),
            }
            _duration_minutes(row["start_time"], row["end_time"])
            if not row["subject_name"] or row["subject_name"] == "انتخاب درس":
                raise ValueError("نام درس را وارد کنید.")
        except ValueError as exc:
            QMessageBox.warning(self, "درس", str(exc))
            return
        self.editor_rows.append(row)
        if self.subject.isEditable():
            self.subject.setCurrentText("")
        else:
            self.subject.setCurrentIndex(0)
        self._render_editor_rows()

    def _render_editor_rows(self):
        self.editor_table.setRowCount(len(self.editor_rows))
        for index, row in enumerate(self.editor_rows):
            for col, value in enumerate(
                (
                    DayOfWeek.PERSIAN_NAMES[row["day_of_week"]],
                    row["start_time"],
                    row["end_time"],
                    row["subject_name"],
                    row["session_type"],
                )
            ):
                self.editor_table.setItem(index, col, QTableWidgetItem(value))
            action_cell = QWidget()
            action_layout = QHBoxLayout(action_cell)
            action_layout.setContentsMargins(0, 0, 0, 0)
            action_layout.setAlignment(Qt.AlignCenter)
            remove = _DeleteRowButton(action_cell)
            remove.clicked.connect(lambda _, i=index: self._delete_row(i))
            action_layout.addWidget(remove)
            self.editor_table.setCellWidget(index, 5, action_cell)

    def _delete_row(self, index):
        del self.editor_rows[index]
        self._render_editor_rows()

    def _save_editor(self):
        try:
            if self.creating:
                self.plan = create_manual_plan(
                    self.panel.student,
                    self.start_date.date(),
                    self.end_date.date(),
                )
            save_plan_sessions(self.plan, self.editor_rows)
        except ValueError as exc:
            if self.creating:
                self.start_date.set_error(str(exc))
            return
        self.creating = False
        self.reload()
        self.panel.summary.reload()

    def _cancel_editor(self):
        self.creating = False
        self.reload()

    def _regenerate(self):
        if (
            QMessageBox.question(
                self,
                "تولید برنامه",
                "برنامه فعلی (در صورت وجود) آرشیو و یک برنامه جدید توسط موتور هوشمند "
                "ساخته می شود. ادامه می دهید؟",
                QMessageBox.Yes | QMessageBox.No,
            )
            != QMessageBox.Yes
        ):
            return
        try:
            _, warnings = regenerate_plan(self.panel.student)
        except Exception as exc:
            QMessageBox.critical(self, "تولید برنامه", f"ساخت برنامه ناموفق بود: {exc}")
            return
        self.reload()
        self.panel.summary.reload()
        if warnings:
            QMessageBox.information(self, "نکات برنامه", "\n".join(warnings))

    def _archive(self):
        if (
            QMessageBox.question(
                self,
                "پایان برنامه",
                "این برنامه آرشیو می شود و غیرفعال خواهد شد. ادامه می دهید؟",
                QMessageBox.Yes | QMessageBox.No,
            )
            == QMessageBox.Yes
        ):
            archive_plan(self.plan)
            self.reload()
            self.panel.summary.reload()


class NotesTab(QWidget):
    def __init__(self, panel):
        super().__init__()
        self.panel = panel
        self.unlocked = False
        self.editing_note_id = None
        self.idle_timer = QTimer(self)
        self.idle_timer.setSingleShot(True)
        self.idle_timer.setInterval(5 * 60 * 1000)
        self.idle_timer.timeout.connect(self.lock)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 12, 0, 0)
        self.layout.setSpacing(12)

    def reload(self):
        _clear_layout(self.layout)
        if not self.unlocked:
            self.pin = FormField("پین گاوصندوق", password=True, revealable=True)
            unlock = PrimaryButton("باز کردن گاوصندوق")
            unlock.clicked.connect(self._unlock)
            self.layout.addStretch()
            self.layout.addWidget(QLabel("یادداشت های محرمانه"))
            self.layout.addWidget(self.pin)
            self.layout.addWidget(unlock)
            self.layout.addStretch()
            return
        self.title = FormField("عنوان", "عنوان یادداشت")
        self.tags = FormField("برچسب ها", "مثلاً پیگیری، خانواده")
        self.content = QTextEdit()
        self.content.setPlaceholderText("متن یادداشت محرمانه")
        self.content.setMinimumHeight(90)
        self.title.input.textEdited.connect(self.touch)
        self.tags.input.textEdited.connect(self.touch)
        self.content.textChanged.connect(self.touch)
        action = PrimaryButton("ذخیره تغییرات" if self.editing_note_id else "افزودن یادداشت")
        action.clicked.connect(self._save_note)
        self.layout.addWidget(self.title)
        self.layout.addWidget(self.tags)
        self.layout.addWidget(self.content)
        self.layout.addWidget(action)
        try:
            notes = list_notes(self.panel.current_user, self.panel.student)
        except NotePermissionError:
            self.lock()
            return
        for note in notes:
            card = Card()
            card.body_layout.addWidget(_section_title(note.title))
            meta = QLabel(f"{note.created_at:%Y-%m-%d}  |  {note.tags}")
            meta.setStyleSheet(f"font-size:11px; color:{Colors.TEXT_MUTED};")
            body = QLabel(note.content)
            body.setWordWrap(True)
            card.body_layout.addWidget(meta)
            card.body_layout.addWidget(body)
            edit = SecondaryButton("ویرایش")
            edit.clicked.connect(lambda _, item=note: self._edit_note(item))
            card.body_layout.addWidget(edit)
            self.layout.addWidget(card)
        events = list_note_audit(self.panel.current_user, self.panel.student)
        if events:
            self.layout.addWidget(_section_title("فعالیت های محرمانه من"))
            labels = {
                "note.create": "ایجاد یادداشت",
                "note.view": "مشاهده یادداشت",
                "note.edit": "ویرایش یادداشت",
            }
            for event in events[:10]:
                self.layout.addWidget(
                    QLabel(f"{event.created_at:%Y-%m-%d %H:%M} — {labels.get(event.action, event.action)}")
                )
        self.layout.addStretch()

    def _unlock(self):
        try:
            get_database_manager().unlock_vault(DatabaseCredentials.from_vault_pin(self.pin.text()))
            self.unlocked = True
            self.touch()
            self.reload()
        except Exception as exc:
            self.pin.set_error(str(exc))

    def touch(self, *_):
        if self.unlocked:
            self.idle_timer.start()

    def lock(self):
        self.idle_timer.stop()
        self.unlocked = False
        self.editing_note_id = None
        get_database_manager().lock_vault()
        self.reload()

    def _edit_note(self, note):
        self.editing_note_id = note.id
        self.title.input.setText(note.title)
        self.tags.input.setText(note.tags)
        self.content.setPlainText(note.content)
        self.touch()

    def _save_note(self):
        try:
            values = {"title": self.title.text(), "tags": self.tags.text(), "content": self.content.toPlainText()}
            if self.editing_note_id:
                update_note(self.panel.current_user, self.editing_note_id, **values)
            else:
                create_note(self.panel.current_user, self.panel.student, **values)
        except (NotePermissionError, NoteValidationError) as exc:
            self.title.set_error(str(exc))
            return
        self.editing_note_id = None
        self.touch()
        self.reload()


class StudentPanel(QWidget):
    back_requested = pyqtSignal()

    def __init__(self, current_user=None, parent=None):
        super().__init__(parent)
        self.current_user = current_user
        self.student = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(12)
        header = QHBoxLayout()
        back = SecondaryButton("بازگشت", icon="←")
        back.clicked.connect(self.back_requested.emit)
        self.title = QLabel("پرونده تحصیلی")
        self.title.setStyleSheet(f"font-size:20px; font-weight:800; color:{Colors.TEXT_MAIN};")
        header.addWidget(back)
        header.addWidget(self.title)
        header.addStretch()
        layout.addLayout(header)
        self.seg = QFrame()
        self.seg.setObjectName("SegmentedBar")
        self.seg.setStyleSheet(SEGMENTED_STYLE)
        self.seg.setFixedHeight(44)
        seg_layout = QHBoxLayout(self.seg)
        seg_layout.setContentsMargins(4, 4, 4, 4)
        seg_layout.setSpacing(4)
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        self.stack = QStackedWidget()
        self._tab_viewports = {}
        self.summary = SummaryTab(self)
        self.plan = PlanTab(self)
        self.notes = NotesTab(self)
        role = current_user.role if current_user else None
        panels = [("خلاصه و سوابق", self.summary)]
        # ponytail: study plans hidden from assistants here; no shared ops layer
        # exists to guard, and PlanTab is the only path that mutates them.
        if role != "assistant":
            panels.append(("برنامه مطالعاتی هفتگی", self.plan))
        if role == "counselor":
            panels.append(("یادداشت ها", self.notes))
        for index, (text, widget) in enumerate(panels):
            button = QPushButton(text)
            button.setObjectName("SegItem")
            button.setCheckable(True)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedHeight(32)
            self.group.addButton(button, index)
            seg_layout.addWidget(button)
            viewport = _scrollable_tab(widget)
            self._tab_viewports[widget] = viewport
            self.stack.addWidget(viewport)
        self.group.buttonClicked.connect(self._select_tab)
        layout.addWidget(self.seg)
        layout.addWidget(self.stack, 1)

    def load(self, student):
        if self.notes.unlocked:
            self.notes.lock()
        self.student = student
        classroom = student.classroom
        ordinal = GRADE_ORDINALS.get(classroom.grade_level, str(classroom.grade_level))
        self.title.setText(
            f"پرونده تحصیلی: {student.full_name} — پایه {ordinal} {student.major} (کد ملی: {to_persian_digits(student.national_id)})"
        )
        self.reload()
        default = self.stack.indexOf(self._tab_viewports[self.plan]) if self.plan in self._tab_viewports else 0
        self.group.button(default).setChecked(True)
        self.stack.setCurrentIndex(default)

    def reload(self):
        if self.student:
            self.summary.reload()
            if self.plan in self._tab_viewports:
                self.plan.reload()
            if self.notes in self._tab_viewports:
                self.notes.reload()

    def _select_tab(self, button):
        index = self.group.id(button)
        if self.notes in self._tab_viewports and index != self.stack.indexOf(self._tab_viewports[self.notes]):
            if self.notes.unlocked:
                self.notes.lock()
        self.stack.setCurrentIndex(index)


def _section_title(text):
    label = QLabel(text)
    label.setStyleSheet(f"font-size:15px; font-weight:800; color:{Colors.TEXT_MAIN};")
    return label


def _scrollable_tab(widget):
    scroll = QScrollArea()
    scroll.setObjectName("StudentTabScroll")
    scroll.setWidgetResizable(True)
    scroll.setFrameShape(QFrame.NoFrame)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    scroll.setStyleSheet(
        f"QScrollArea#StudentTabScroll {{ background: transparent; }} "
        f"QScrollBar:vertical {{ background: transparent; width: 10px; margin: 4px 0; }} "
        f"QScrollBar::handle:vertical {{ background: {Colors.BORDER}; border-radius: 5px; min-height: 28px; }} "
        f"QScrollBar::handle:vertical:hover {{ background: {Colors.TEXT_MUTED}; }} "
        "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
    )
    scroll.setWidget(widget)
    return scroll


def _clear_layout(layout):
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        if widget:
            widget.deleteLater()
        elif item.layout():
            _clear_layout(item.layout())


def _style_table(table):
    table.setLayoutDirection(Qt.RightToLeft)
    table.setEditTriggers(QTableWidget.NoEditTriggers)
    table.verticalHeader().setVisible(False)
    table.horizontalHeader().setStretchLastSection(True)
    table.setStyleSheet(
        f"QTableWidget {{ background:{Colors.SURFACE}; border:1px solid {Colors.BORDER}; border-radius:10px; gridline-color:{Colors.BORDER}; }} QHeaderView::section {{ background:{Colors.SURFACE_HOVER}; border:none; padding:8px; color:{Colors.TEXT_MUTED}; font-weight:700; }} QTableWidget::item {{ padding:7px; color:{Colors.TEXT_MAIN}; }}"
    )
