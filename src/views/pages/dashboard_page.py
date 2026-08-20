from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional, Tuple

from peewee import fn
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from src.storage.models import (
    AcademicGrade,
    Classroom,
    DailyCheckIn,
    PlanStatus,
    RiskLevel,
    Student,
    StudyPlan,
)
from src.styles.theme import Colors
from src.utils.persian_utils import to_persian_digits
from src.views.components.ui_kit import (
    AIInsightCard,
    Card,
    Divider,
    PrimaryButton,
    ProgressBar,
    SecondaryButton,
    SectionHeader,
    StatCard,
    StudentRow,
)


@dataclass(frozen=True)
class SubjectAverage:
    name: str
    percentage: int


@dataclass(frozen=True)
class DashboardData:
    active_student_count: int
    high_risk_student_count: int
    active_plan_count: int
    weekly_completion_rate: int
    attention_students: Tuple[Student, ...]
    subject_averages: Tuple[SubjectAverage, ...]


def _week_start(today: date) -> date:
    return today - timedelta(days=(today.weekday() - 5) % 7)


def load_dashboard_data(today: Optional[date] = None) -> DashboardData:
    today = today or date.today()
    week_start = _week_start(today)

    active_student_count = Student.select().where(Student.is_active).count()
    high_risk_student_count = Student.select().where(
        Student.is_active, Student.risk_level == RiskLevel.HIGH
    ).count()
    active_plan_count = (
        StudyPlan.select()
        .join(Student)
        .where(Student.is_active, StudyPlan.status == PlanStatus.ACTIVE)
        .count()
    )

    completed, total = (
        DailyCheckIn.select(
            fn.COALESCE(fn.SUM(DailyCheckIn.completed_sessions), 0),
            fn.COALESCE(fn.SUM(DailyCheckIn.total_sessions), 0),
        )
        .join(Student)
        .where(
            Student.is_active,
            DailyCheckIn.date.between(week_start, today),
            DailyCheckIn.total_sessions > 0,
        )
        .scalar(as_tuple=True)
    )
    weekly_completion_rate = round((completed / total) * 100) if total else 0

    attention_students = tuple(
        Student.select(Student, Classroom)
        .join(Classroom)
        .where(
            Student.is_active,
            Student.risk_level.in_((RiskLevel.HIGH, RiskLevel.MEDIUM)),
        )
        .order_by(Student.risk_level, Student.burnout_score.desc())
        .limit(4)
    )

    subject_rows = (
        AcademicGrade.select(
            AcademicGrade.subject_name,
            (
                fn.SUM(AcademicGrade.score)
                * 100.0
                / fn.NULLIF(fn.SUM(AcademicGrade.max_score), 0)
            ).alias("percentage"),
        )
        .join(Student)
        .where(Student.is_active)
        .group_by(AcademicGrade.subject_name)
        .order_by(fn.SUM(AcademicGrade.score).desc())
        .limit(4)
        .dicts()
    )
    subject_averages = tuple(
        SubjectAverage(name=row["subject_name"], percentage=round(row["percentage"]))
        for row in subject_rows
    )

    return DashboardData(
        active_student_count=active_student_count,
        high_risk_student_count=high_risk_student_count,
        active_plan_count=active_plan_count,
        weekly_completion_rate=weekly_completion_rate,
        attention_students=attention_students,
        subject_averages=subject_averages,
    )


class DashboardPage(QWidget):
    def __init__(self):
        super().__init__()
        data = load_dashboard_data()

        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")
        outer_layout.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(20)

        header_row = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        page_title = QLabel("داشبورد")
        page_title.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {Colors.TEXT_MAIN};")
        page_subtitle = QLabel("خلاصه‌ای از وضعیت دانش‌آموزان و برنامه‌های مطالعاتی")
        page_subtitle.setStyleSheet(f"font-size: 13px; color: {Colors.TEXT_MUTED};")
        title_box.addWidget(page_title)
        title_box.addWidget(page_subtitle)
        header_row.addLayout(title_box)
        header_row.addStretch()
        header_row.addWidget(PrimaryButton("دانش‌آموز جدید", icon="➕"))
        layout.addLayout(header_row)

        stats_row = QHBoxLayout()
        stats_row.setSpacing(14)
        stats_row.addWidget(StatCard("کل دانش‌آموزان", data.active_student_count, "👥"))
        stats_row.addWidget(StatCard("ریسک بالا", data.high_risk_student_count, "⚠️", accent_color=Colors.ERROR))
        stats_row.addWidget(StatCard("برنامه‌های فعال", data.active_plan_count, "📚"))
        stats_row.addWidget(
            StatCard("نرخ تکمیل هفتگی", f"{data.weekly_completion_rate}٪", "✅", accent_color=Colors.SUCCESS)
        )
        layout.addLayout(stats_row)

        insight = (
            f"{to_persian_digits(data.high_risk_student_count)} دانش‌آموز در وضعیت ریسک بالا هستند."
            if data.high_risk_student_count
            else "در حال حاضر دانش‌آموزی با وضعیت ریسک بالا ثبت نشده است."
        )
        layout.addWidget(AIInsightCard(insight))

        columns = QHBoxLayout()
        columns.setSpacing(18)
        columns.addWidget(self._attention_card(data.attention_students), stretch=6)

        side_column = QVBoxLayout()
        side_column.setSpacing(18)
        side_column.addWidget(self._subject_averages_card(data.subject_averages))
        side_column.addWidget(self._quick_actions_card())
        side_column.addStretch()
        columns.addLayout(side_column, stretch=4)
        layout.addLayout(columns)
        layout.addStretch()

    @staticmethod
    def _attention_card(students: Tuple[Student, ...]) -> Card:
        card = Card(padding=0)
        card.body_layout.setSpacing(0)
        card.body_layout.setContentsMargins(18, 14, 18, 8)
        card.body_layout.addWidget(SectionHeader("نیازمند توجه"))

        if not students:
            label = QLabel("دانش‌آموزی با ریسک متوسط یا بالا ثبت نشده است.")
            label.setWordWrap(True)
            label.setStyleSheet(f"padding: 16px 0; font-size: 12px; color: {Colors.TEXT_MUTED};")
            card.body_layout.addWidget(label)
            return card

        for student in students:
            subtitle = f"{student.classroom.name} · {student.major}"
            card.body_layout.addWidget(
                StudentRow(
                    student.full_name,
                    subtitle,
                    student.risk_level,
                    on_click=lambda name=student.full_name: print(f"Open profile: {name}"),
                )
            )
        return card

    @staticmethod
    def _subject_averages_card(subjects: Tuple[SubjectAverage, ...]) -> Card:
        card = Card()
        title = QLabel("میانگین نمرات دروس")
        title.setAlignment(Qt.AlignRight)
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        card.body_layout.addWidget(title)
        card.body_layout.addWidget(Divider())

        if not subjects:
            label = QLabel("هنوز نمره‌ای برای نمایش ثبت نشده است.")
            label.setWordWrap(True)
            label.setStyleSheet(f"font-size: 12px; color: {Colors.TEXT_MUTED};")
            card.body_layout.addWidget(label)
            return card

        for subject in subjects:
            color = Colors.SUCCESS if subject.percentage >= 70 else Colors.WARNING if subject.percentage >= 50 else Colors.ERROR
            row = QVBoxLayout()
            row.setSpacing(4)
            label_row = QHBoxLayout()
            name_label = QLabel(subject.name)
            name_label.setAlignment(Qt.AlignRight)
            name_label.setStyleSheet(f"font-size: 12px; font-weight: 600; color: {Colors.TEXT_MAIN};")
            percentage_label = QLabel(to_persian_digits(f"{subject.percentage}٪"))
            percentage_label.setStyleSheet(f"font-size: 12px; font-weight: 700; color: {color};")
            label_row.addWidget(name_label)
            label_row.addStretch()
            label_row.addWidget(percentage_label)
            row.addLayout(label_row)
            row.addWidget(ProgressBar(value=subject.percentage, color=color))
            card.body_layout.addLayout(row)
        return card

    @staticmethod
    def _quick_actions_card() -> Card:
        card = Card()
        title = QLabel("اقدامات سریع")
        title.setAlignment(Qt.AlignRight)
        title.setStyleSheet(f"font-size: 14px; font-weight: 700; color: {Colors.TEXT_MAIN};")
        card.body_layout.addWidget(title)
        card.body_layout.addWidget(Divider())
        card.body_layout.addWidget(SecondaryButton("ساخت برنامه مطالعاتی", icon="📅"))
        card.body_layout.addWidget(SecondaryButton("افزودن دانش‌آموز", icon="👤"))
        card.body_layout.addWidget(SecondaryButton("خروجی گزارش هفتگی", icon="📄"))
        return card
