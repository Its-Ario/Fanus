from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, Optional, Tuple

from peewee import JOIN, Case, fn
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from src.storage.models import (
    MOADEL_TERMS,
    AcademicGrade,
    AcademicMajor,
    AttendanceRecord,
    Classroom,
    DailyCheckIn,
    Exam,
    RiskLevel,
    SchoolProfile,
    Student,
    StudyPlan,
    StudySession,
    grade_options,
)
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.bar_chart import BarChartWidget
from src.views.components.line_chart import LineChartWidget
from src.views.components.ui_kit import Card, Dropdown, SectionHeader
from src.views.pages.dashboard_page import _week_start

RISK_LEVELS = (RiskLevel.HIGH, RiskLevel.MEDIUM, RiskLevel.LOW)
RISK_SERIES = (
    (RiskLevel.HIGH, Colors.ERROR, "🔴 ریسک بالا"),
    (RiskLevel.MEDIUM, Colors.WARNING, "🟡 ریسک متوسط"),
    (RiskLevel.LOW, Colors.SUCCESS, "🟢 ریسک پایین"),
)
GPA_BANDS = (("زیر ۱۲", 0, 12), ("۱۲–۱۵", 12, 15), ("۱۵–۱۸", 15, 18), ("۱۸–۲۰", 18, 20.001))


@dataclass(frozen=True)
class RiskDistribution:
    classes: Tuple[Tuple[str, Tuple[int, int, int]], ...]
    collapsed: bool
    student_count: int


@dataclass(frozen=True)
class CompletionTrend:
    points: Tuple[Tuple[str, Optional[float]], ...]
    check_in_count: int


@dataclass(frozen=True)
class GpaBandData:
    label: str
    average_absences: float
    student_count: int


@dataclass(frozen=True)
class SubjectWorkload:
    subject_name: str
    hours: float


@dataclass(frozen=True)
class AnalyticsData:
    panel1: RiskDistribution
    panel2: CompletionTrend
    panel3: Tuple[GpaBandData, ...]
    panel3_enough_data: bool
    panel3_has_attendance: bool
    panel4: Tuple[SubjectWorkload, ...]


def _filtered_students(grade: Optional[int], major: Optional[str]):
    query = Student.select().join(Classroom).where(Student.is_active)
    if grade is not None:
        query = query.where(Classroom.grade_level == grade)
    if major is not None:
        query = query.where(Classroom.major == major)
    return query


def _filter_conditions(grade: Optional[int], major: Optional[str]):
    conditions = [Student.is_active]
    if grade is not None:
        conditions.append(Classroom.grade_level == grade)
    if major is not None:
        conditions.append(Classroom.major == major)
    return conditions


def _completion_trend(grade: Optional[int], major: Optional[str], today: date) -> CompletionTrend:
    current_start = _week_start(today)
    starts = [current_start - timedelta(days=7 * offset) for offset in range(7, -1, -1)]
    selected = []
    for start in starts:
        end = start + timedelta(days=7)
        selected.extend(
            (
                fn.COALESCE(
                    fn.SUM(
                        Case(
                            None,
                            (
                                (
                                    (DailyCheckIn.date >= start) & (DailyCheckIn.date < end),
                                    DailyCheckIn.completed_sessions,
                                ),
                            ),
                            0,
                        )
                    ),
                    0,
                ),
                fn.COALESCE(
                    fn.SUM(
                        Case(
                            None,
                            (
                                (
                                    (DailyCheckIn.date >= start) & (DailyCheckIn.date < end),
                                    DailyCheckIn.total_sessions,
                                ),
                            ),
                            0,
                        )
                    ),
                    0,
                ),
            )
        )
    conditions = _filter_conditions(grade, major) + [
        DailyCheckIn.date >= starts[0],
        DailyCheckIn.date < starts[-1] + timedelta(days=7),
    ]
    values = (
        DailyCheckIn.select(*selected)
        .join(Student)
        .join(Classroom)
        .where(*conditions)
        .scalar(as_tuple=True)
    )
    check_in_count = DailyCheckIn.select().join(Student).join(Classroom).where(*conditions).count()
    points = []
    for index, start in enumerate(starts):
        completed, total = values[index * 2 : index * 2 + 2]
        label = "هفته جاری" if index == 7 else f"{to_persian_digits(7 - index)} هفته پیش"
        points.append((label, round(completed * 100.0 / total, 1) if total else None))
    return CompletionTrend(points=tuple(points), check_in_count=check_in_count)


def load_analytics_data(
    grade: Optional[int] = None, major: Optional[str] = None, today: Optional[date] = None
) -> AnalyticsData:
    """Load school-wide aggregates without materialising any student collection in Python."""
    today = today or date.today()
    conditions = _filter_conditions(grade, major)
    student_count = _filtered_students(grade, major).count()

    risk_rows = (
        Student.select(Classroom.name, Student.risk_level, fn.COUNT(Student.id).alias("count"))
        .join(Classroom)
        .where(*conditions)
        .group_by(Classroom.name, Student.risk_level)
        .dicts()
    )
    by_class: Dict[str, Dict[str, int]] = {}
    for row in risk_rows:
        by_class.setdefault(row["name"], {})[row["risk_level"]] = row["count"]
    collapsed = grade is None and major is None and len(by_class) > 8
    if collapsed:
        totals = {
            level: sum(values.get(level, 0) for values in by_class.values())
            for level in RISK_LEVELS
        }
        class_data = (("کل مدرسه", tuple(totals[level] for level in RISK_LEVELS)),)
    else:
        class_data = tuple(
            (name, tuple(values.get(level, 0) for level in RISK_LEVELS))
            for name, values in sorted(by_class.items())
        )

    gpa = (
        AcademicGrade.select(
            AcademicGrade.student.alias("student_id"),
            fn.AVG(AcademicGrade.score).alias("gpa"),
            fn.COUNT(AcademicGrade.score).alias("grade_count"),
        )
        .join(Exam)
        .where(Exam.term << MOADEL_TERMS, AcademicGrade.score.is_null(False))
        .group_by(AcademicGrade.student)
        .having(fn.COUNT(AcademicGrade.score) > 0)
        .alias("gpa_by_student")
    )
    band_case = Case(
        None,
        (
            (gpa.c.gpa < 12, "زیر ۱۲"),
            (gpa.c.gpa < 15, "۱۲–۱۵"),
            (gpa.c.gpa < 18, "۱۵–۱۸"),
            (gpa.c.gpa <= 20, "۱۸–۲۰"),
        ),
    )
    absence_condition = AttendanceRecord.status.not_in(("present", ""))
    band_rows = (
        Student.select(
            band_case.alias("band"),
            fn.COUNT(fn.DISTINCT(Student.id)).alias("student_count"),
            fn.COUNT(AttendanceRecord.id).alias("absence_count"),
        )
        .join(Classroom)
        .join(gpa, on=(Student.id == gpa.c.student_id))
        .switch(Student)
        .join(
            AttendanceRecord,
            JOIN.LEFT_OUTER,
            on=((AttendanceRecord.student == Student.id) & absence_condition),
        )
        .where(*conditions, gpa.c.gpa >= 0, gpa.c.gpa <= 20)
        .group_by(band_case)
        .dicts()
    )
    bands = {row["band"]: row for row in band_rows}
    panel3 = tuple(
        GpaBandData(
            label=label,
            average_absences=(row["absence_count"] / row["student_count"]) if row else 0.0,
            student_count=row["student_count"] if row else 0,
        )
        for label, _, _ in GPA_BANDS
        for row in (bands.get(label),)
    )
    has_attendance = (
        AttendanceRecord.select().join(Student).join(Classroom).where(*conditions).exists()
    )

    workload_rows = (
        StudySession.select(
            StudySession.subject_name,
            (fn.SUM(StudySession.duration_minutes) / 60.0).alias("hours"),
        )
        .join(StudyPlan)
        .join(Student)
        .join(Classroom)
        .where(*conditions)
        .group_by(StudySession.subject_name)
        .having(fn.SUM(StudySession.duration_minutes) > 0)
        .order_by(fn.SUM(StudySession.duration_minutes).desc())
        .dicts()
    )
    return AnalyticsData(
        panel1=RiskDistribution(class_data, collapsed, student_count),
        panel2=_completion_trend(grade, major, today),
        panel3=panel3,
        panel3_enough_data=student_count >= 10,
        panel3_has_attendance=has_attendance,
        panel4=tuple(SubjectWorkload(row["subject_name"], row["hours"]) for row in workload_rows),
    )


class AnalyticsPage(QWidget):
    def __init__(self):
        super().__init__()
        self._loaded = False

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer.addWidget(scroll)
        content = QWidget()
        scroll.setWidget(content)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(18)

        title = QLabel("تحلیل و آمار کلی مدرسه")
        title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        subtitle = QLabel("روندهای تحصیلی، ریسک و پایبندی به برنامه در سطح مدرسه")
        subtitle.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        filters = QHBoxLayout()
        filters.setSpacing(12)
        self.grade_combo = self._filter_combo("پایه تحصیلی")
        self.major_combo = self._filter_combo("رشته تحصیلی")
        profile = SchoolProfile.get_instance()
        self.grade_combo.addItem("پایه تحصیلی: همه", None)
        for value in grade_options(profile.type):
            self.grade_combo.addItem(f"پایه تحصیلی: {to_persian_digits(value)}", value)
        self.major_combo.addItem("رشته تحصیلی: همه", None)
        for value in AcademicMajor.VALUES:
            self.major_combo.addItem(f"رشته تحصیلی: {value}", value)
        filters.addWidget(self.grade_combo)
        filters.addWidget(self.major_combo)
        filters.addStretch()
        layout.addLayout(filters)
        self.grade_combo.currentIndexChanged.connect(self.reload)
        self.major_combo.currentIndexChanged.connect(self.reload)

        grid = QGridLayout()
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(18)
        self.risk_chart = BarChartWidget()
        self.trend_chart = LineChartWidget()
        self.gpa_chart = BarChartWidget()
        self.workload_chart = BarChartWidget(BarChartWidget.HORIZONTAL)
        self.risk_note = QLabel()
        self.risk_note.setStyleSheet(f"font-size: 11px; color: {Colors.TEXT_MUTED};")
        grid.addWidget(
            self._panel("پنل ۱: توزیع سطح ریسک به تفکیک کلاس", self.risk_chart, self.risk_note),
            0,
            0,
        )
        grid.addWidget(
            self._panel("پنل ۲: روند پایبندی به برنامه — ۸ هفته اخیر", self.trend_chart), 0, 1
        )
        grid.addWidget(self._panel("پنل ۳: میانگین غیبت بر حسب بازه معدل", self.gpa_chart), 1, 0)
        grid.addWidget(
            self._panel("پنل ۴: ساعت برنامه ریزی شده هفتگی به تفکیک درس", self.workload_chart), 1, 1
        )
        layout.addLayout(grid)
        layout.addStretch()

    @staticmethod
    def _filter_combo(label: str) -> Dropdown:
        combo = Dropdown()
        combo.setMinimumWidth(185)
        combo.setToolTip(label)
        return combo

    @staticmethod
    def _panel(title: str, chart: QWidget, note: Optional[QLabel] = None) -> Card:
        card = Card()
        card.setMinimumHeight(280)
        card.body_layout.addWidget(SectionHeader(title))
        if note is not None:
            card.body_layout.addWidget(note)
        card.body_layout.addWidget(chart, stretch=1)
        return card

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._loaded:
            self._build_ui()
            self._loaded = True
        self.reload()

    def reload(self) -> None:
        if not self.isVisible():
            return
        data = load_analytics_data(self.grade_combo.currentData(), self.major_combo.currentData())
        self.risk_note.setText(
            "🔴 ریسک بالا   |   🟡 ریسک متوسط   |   🟢 ریسک پایین"
            + (
                "\nنمای کل مدرسه — برای تفکیک کلاسی، پایه یا رشته را انتخاب کنید"
                if data.panel1.collapsed
                else ""
            )
        )
        risk_groups = []
        for class_name, counts in data.panel1.classes:
            risk_groups.append(
                (class_name, tuple((counts[i], RISK_SERIES[i][1], "") for i in range(3)))
            )
        if data.panel1.student_count == 0:
            risk_overlay = "اطلاعاتی برای نمایش وجود ندارد"
            risk_detail = None
        elif data.panel1.student_count < 10:
            risk_overlay = "داده کافی موجود نیست"
            risk_detail = "حداقل ۱۰ دانش آموز برای محاسبه لازم است"
        else:
            risk_overlay = None
            risk_detail = None
        self.risk_chart.set_data(risk_groups, risk_overlay, risk_detail)
        self.trend_chart.set_data(
            data.panel2.points,
            "داده کافی موجود نیست" if data.panel2.check_in_count < 5 else None,
            "حداقل ۵ ثبت روزانه برای نمایش روند لازم است"
            if data.panel2.check_in_count < 5
            else None,
        )
        gpa_groups = []
        for band in data.panel3:
            tag = " (نمونه کوچک)" if 0 < band.student_count < 10 else ""
            gpa_groups.append(
                (
                    f"معدل {band.label} (n={to_persian_digits(band.student_count)}){tag}",
                    ((band.average_absences, Colors.WARNING, ""),),
                )
            )
        panel3_overlay = None
        if not data.panel3_enough_data or not data.panel3_has_attendance:
            panel3_overlay = "اطلاعاتی برای نمایش وجود ندارد"
        self.gpa_chart.set_data(gpa_groups, panel3_overlay)
        self.workload_chart.set_data(
            tuple(
                (item.subject_name, ((item.hours, Colors.PRIMARY, " ساعت"),))
                for item in data.panel4
            ),
            "اطلاعاتی برای نمایش وجود ندارد" if not data.panel4 else None,
        )
