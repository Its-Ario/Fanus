from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import jdatetime
from peewee import fn
from PyQt5.QtCore import QRectF, Qt
from PyQt5.QtGui import QColor, QFont, QFontDatabase, QPainter, QPen
from PyQt5.QtPrintSupport import QPrinter

from src.planner import catalog
from src.storage.models import (
    AcademicGrade,
    AttendanceRecord,
    AttendanceStatus,
    DayOfWeek,
    Exam,
    GradeTerm,
    SchoolProfile,
)
from src.utils.persian_utils import to_persian_digits

_MARGIN = 46
_COLORS = {
    "calc": "#DBEAFE",
    "descriptive": "#DCFCE7",
    "light": "#FEF3C7",
}


@dataclass(frozen=True)
class FormalScore:
    subject: str
    term: str
    score: float
    ceiling: float
    exam_date: date


@dataclass(frozen=True)
class MockTrend:
    name: str
    exam_date: date
    percentage: float


@dataclass(frozen=True)
class AttendanceSummary:
    absent: int
    late: int
    excused: int


def jalali_date(value: date) -> str:
    if not value:
        return "—"
    converted = jdatetime.date.fromgregorian(date=value)
    return to_persian_digits(f"{converted.year:04d}/{converted.month:02d}/{converted.day:02d}")


def formal_scores(student) -> tuple[FormalScore, ...]:
    """Return the newest scored نوبت اول/دوم grade for each subject and term."""
    rows = (
        AcademicGrade.select(AcademicGrade, Exam)
        .join(Exam)
        .where(
            AcademicGrade.student == student,
            AcademicGrade.score.is_null(False),
            Exam.term << (GradeTerm.NOBAT_1, GradeTerm.NOBAT_2),
        )
        .order_by(Exam.exam_date.desc(), AcademicGrade.created_at.desc())
    )
    newest = {}
    for row in rows:
        newest.setdefault((row.subject_name, row.exam.term), row)
    return tuple(
        FormalScore(
            row.subject_name, row.exam.term, row.score, row.exam.max_score, row.exam.exam_date
        )
        for _, row in sorted(newest.items(), key=lambda item: (item[0][0], item[0][1]))
    )


def mock_trends(student) -> tuple[MockTrend, ...]:
    rows = (
        AcademicGrade.select(AcademicGrade, Exam)
        .join(Exam)
        .where(
            AcademicGrade.student == student,
            AcademicGrade.score.is_null(False),
            Exam.term == GradeTerm.AZMAYESHI,
        )
        .order_by(Exam.exam_date)
    )
    grouped = defaultdict(list)
    for row in rows:
        if row.exam.max_score:
            grouped[row.exam_id].append(row)
    return tuple(
        MockTrend(
            values[0].exam.name,
            values[0].exam.exam_date,
            round(sum(row.score * 100.0 / row.exam.max_score for row in values) / len(values), 1),
        )
        for _, values in sorted(grouped.items(), key=lambda item: item[1][0].exam.exam_date)
    )


def attendance_summary(student) -> AttendanceSummary:
    rows = (
        AttendanceRecord.select(
            AttendanceRecord.status, fn.COUNT(AttendanceRecord.id).alias("count")
        )
        .where(AttendanceRecord.student == student)
        .group_by(AttendanceRecord.status)
    )
    counts = {row.status: row.count for row in rows}
    return AttendanceSummary(
        absent=counts.get(AttendanceStatus.ABSENT, 0),
        late=counts.get(AttendanceStatus.LATE, 0),
        excused=counts.get(AttendanceStatus.EXCUSED, 0),
    )


def weekly_hours(plan) -> tuple[tuple[float, ...], float]:
    daily = [0.0] * 7
    for session in plan.get_active_sessions():
        daily[session.day_of_week] += session.duration_minutes / 60.0
    return tuple(round(value, 1) for value in daily), round(sum(daily), 1)


def focus_note(student, plan) -> str:
    grades = (
        AcademicGrade.select(AcademicGrade, Exam)
        .join(Exam)
        .where(AcademicGrade.student == student, AcademicGrade.score.is_null(False))
        .order_by(Exam.exam_date.desc(), AcademicGrade.created_at.desc())
    )
    by_subject = defaultdict(list)
    for row in grades:
        if row.exam.max_score and len(by_subject[row.subject_name]) < 3:
            by_subject[row.subject_name].append(row.score / row.exam.max_score)
    weakest = sorted(
        ((sum(values) / len(values), subject) for subject, values in by_subject.items()),
        key=lambda item: item[0],
    )[:2]
    if weakest:
        return "تمرکز ویژه روی " + " و ".join(subject for _, subject in weakest) + " پیشنهاد می‌شود."
    subjects = Counter(session.subject_name for session in plan.get_active_sessions())
    frequent = [subject for subject, _ in subjects.most_common(2)]
    return (
        "تمرکز هفته بر مرور منظم " + " و ".join(frequent) + " است."
        if frequent
        else "برای هفته پیش رو، پیگیری منظم برنامه توصیه می‌شود."
    )


def _font(size: int, bold: bool = False) -> QFont:
    font = QFont("Vazir")
    font.setPixelSize(size)
    font.setBold(bold)
    return font


def _ensure_font() -> None:
    assets = Path(__file__).resolve().parents[1] / "assets" / "fonts"
    for filename in ("Vazir.ttf", "Vazir-Bold.ttf"):
        QFontDatabase.addApplicationFont(str(assets / filename))


def _printer(path: str, landscape: bool) -> QPrinter:
    printer = QPrinter(QPrinter.ScreenResolution)
    printer.setOutputFormat(QPrinter.PdfFormat)
    printer.setOutputFileName(path)
    printer.setPaperSize(QPrinter.A4)
    printer.setOrientation(QPrinter.Landscape if landscape else QPrinter.Portrait)
    return printer


def _text(painter: QPainter, rect: QRectF, text: str, size=13, bold=False, align=Qt.AlignRight):
    painter.setFont(_font(size, bold))
    painter.setPen(QColor("#1F2937"))
    painter.drawText(rect, align | Qt.AlignVCenter | Qt.TextWordWrap, text)


def _line(painter: QPainter, x1, y1, x2, y2, color="#CBD5E1"):
    painter.setPen(QPen(QColor(color), 1))
    painter.drawLine(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))


def _header(painter: QPainter, width: int, title: str, student) -> int:
    profile = SchoolProfile.get_instance()
    _text(painter, QRectF(_MARGIN, _MARGIN, width - 2 * _MARGIN, 30), profile.school_name, 18, True)
    _text(painter, QRectF(_MARGIN, _MARGIN + 31, width - 2 * _MARGIN, 24), title, 15, True)
    classroom = student.classroom
    details = (
        f"دانش‌آموز: {student.full_name}   |   پایه: {to_persian_digits(classroom.grade_level)} "
        f"{classroom.major}   |   کد ملی: {to_persian_digits(student.national_id)}\n"
        f"سال تحصیلی: {to_persian_digits(profile.academic_year)}   |   کلاس: {classroom.name}"
    )
    _text(painter, QRectF(_MARGIN, _MARGIN + 60, width - 2 * _MARGIN, 42), details, 11)
    _line(painter, _MARGIN, _MARGIN + 108, width - _MARGIN, _MARGIN + 108, "#0D9488")
    return _MARGIN + 124


def _footer(painter: QPainter, width: int, height: int) -> None:
    _line(painter, _MARGIN, height - _MARGIN, width - _MARGIN, height - _MARGIN)
    _text(
        painter,
        QRectF(_MARGIN, height - _MARGIN + 7, width - 2 * _MARGIN, 20),
        f"تاریخ تهیه: {jalali_date(date.today())}",
        9,
    )


def _signature_y(height: int) -> int:
    """Keep signature blocks clear of the footer rule and generated-date text."""
    return height - _MARGIN - 62


def export_weekly_plan_pdf(plan, path: str) -> None:
    _ensure_font()
    printer = _printer(path, landscape=True)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("ایجاد فایل PDF ممکن نشد.")
    try:
        page = printer.pageRect(QPrinter.DevicePixel)
        width, height = page.width(), page.height()
        y = _header(painter, width, "برنامه مطالعاتی هفتگی", plan.student)
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 22),
            f"بازه برنامه: {jalali_date(plan.start_date)} تا {jalali_date(plan.end_date)}",
            11,
        )
        y += 32
        # Reserve the lower page for hours, notes, signatures, and footer.
        grid_height = min(400, height - y - 270)
        col_width = (width - 2 * _MARGIN) / 7.0
        sessions = defaultdict(list)
        for session in plan.get_active_sessions():
            sessions[session.day_of_week].append(session)
        rows = max(1, max((len(values) for values in sessions.values()), default=0))
        row_height = grid_height / (rows + 1)
        for column in range(8):
            _line(
                painter,
                _MARGIN + column * col_width,
                y,
                _MARGIN + column * col_width,
                y + grid_height,
            )
        for row in range(rows + 2):
            _line(painter, _MARGIN, y + row * row_height, width - _MARGIN, y + row * row_height)
        for day in range(7):
            left = _MARGIN + day * col_width
            _text(
                painter,
                QRectF(left + 3, y + 2, col_width - 6, row_height - 4),
                DayOfWeek.PERSIAN_NAMES[day],
                11,
                True,
                Qt.AlignCenter,
            )
            for row, session in enumerate(sessions[day]):
                cell = QRectF(
                    left + 2, y + (row + 1) * row_height + 2, col_width - 4, row_height - 4
                )
                painter.fillRect(cell, QColor(_COLORS[catalog.type_for(session.subject_name)]))
                _text(
                    painter,
                    cell,
                    f"{session.subject_name}\n{session.start_time}–{session.end_time}\n{session.session_type}",
                    9,
                    False,
                    Qt.AlignCenter,
                )
        y += grid_height + 16
        daily, total = weekly_hours(plan)
        target = plan.student.daily_active_hours
        hours = " | ".join(
            f"{DayOfWeek.PERSIAN_NAMES[day]}: {to_persian_digits(daily[day]):} از {to_persian_digits(target)} ساعت"
            for day in range(7)
        )
        _text(painter, QRectF(_MARGIN, y, width - 2 * _MARGIN, 36), hours, 9)
        y += 44
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 22),
            f"مجموع ساعات موظف: {to_persian_digits(round(target * 7, 1))} ساعت | مجموع برنامه‌ریزی‌شده: {to_persian_digits(total)} ساعت",
            11,
            True,
        )
        y += 30
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 38),
            "یادداشت آموزشی: " + focus_note(plan.student, plan),
            11,
        )
        signature_y = _signature_y(height)
        _text(
            painter,
            QRectF(_MARGIN, signature_y, (width - 2 * _MARGIN) / 2, 30),
            "امضای مشاور: ........................",
            11,
        )
        _text(
            painter,
            QRectF(width / 2, signature_y, (width - 2 * _MARGIN) / 2, 30),
            "امضای والدین: ........................",
            11,
        )
        _footer(painter, width, height)
    finally:
        painter.end()


def export_academic_summary_pdf(student, path: str) -> None:
    _ensure_font()
    printer = _printer(path, landscape=False)
    painter = QPainter()
    if not painter.begin(printer):
        raise RuntimeError("ایجاد فایل PDF ممکن نشد.")
    try:
        page = printer.pageRect(QPrinter.DevicePixel)
        width, height = page.width(), page.height()
        y = _header(painter, width, "کارنامه و سوابق تحصیلی", student)
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 24),
            "نمرات رسمی (آخرین نمره هر درس در هر نوبت)",
            13,
            True,
        )
        y += 32
        cols = ("درس", "نوبت", "نمره", "تاریخ")
        widths = (0.40, 0.22, 0.18, 0.20)
        lefts, cursor = [], _MARGIN
        for part in widths:
            lefts.append(cursor)
            cursor += (width - 2 * _MARGIN) * part
        row_height = 28

        def table_row(values, header=False):
            nonlocal y
            painter.fillRect(
                QRectF(_MARGIN, y, width - 2 * _MARGIN, row_height),
                QColor("#E2E8F0" if header else "#FFFFFF"),
            )
            for index, value in enumerate(values):
                cell_width = (width - 2 * _MARGIN) * widths[index]
                _text(
                    painter,
                    QRectF(lefts[index] + 4, y + 2, cell_width - 8, row_height - 4),
                    value,
                    10,
                    header,
                    Qt.AlignCenter if index > 0 else Qt.AlignRight,
                )
            _line(painter, _MARGIN, y + row_height, width - _MARGIN, y + row_height)
            y += row_height

        table_row(cols, True)
        scores = formal_scores(student)
        if scores:
            for score in scores:
                table_row(
                    (
                        score.subject,
                        score.term,
                        to_persian_digits(f"{score.score:g}/{score.ceiling:g}"),
                        jalali_date(score.exam_date),
                    )
                )
        else:
            table_row(("نمره رسمی ثبت نشده است.", "—", "—", "—"))
        y += 18
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 24),
            "روند عملکرد آزمون آزمایشی",
            13,
            True,
        )
        y += 30
        trends = mock_trends(student)
        if trends:
            for trend in trends:
                _text(
                    painter,
                    QRectF(_MARGIN, y, width - 2 * _MARGIN, 24),
                    f"{trend.name} — {jalali_date(trend.exam_date)}: {to_persian_digits(trend.percentage)}٪",
                    11,
                )
                y += 26
        else:
            _text(
                painter,
                QRectF(_MARGIN, y, width - 2 * _MARGIN, 24),
                "آزمون آزمایشی ثبت نشده است.",
                11,
            )
            y += 28
        attendance = attendance_summary(student)
        y += 12
        _text(painter, QRectF(_MARGIN, y, width - 2 * _MARGIN, 24), "حضور و غیاب", 13, True)
        y += 27
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 36),
            f"غیبت: {to_persian_digits(attendance.absent)} | تأخیر: {to_persian_digits(attendance.late)} | موجه: {to_persian_digits(attendance.excused)}\n"
            "به دلیل ثبت‌نشدن همه روزهای حضور، نرخ قابلیت اتکای حضور قابل محاسبه نیست.",
            10,
        )
        y += 55
        _text(
            painter,
            QRectF(_MARGIN, y, width - 2 * _MARGIN, 32),
            "یادداشت‌های محرمانه مشاور در این گزارش وجود ندارد و به هیچ‌وجه صادر نمی‌شود.",
            10,
            True,
        )
        _footer(painter, width, height)
    finally:
        painter.end()
