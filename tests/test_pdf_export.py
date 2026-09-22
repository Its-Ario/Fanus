from datetime import date

from src import pdf_export
from src.storage.db import DatabaseManager
from src.storage.models import (
    AcademicGrade,
    AcademicMajor,
    AttendanceRecord,
    AttendanceStatus,
    Classroom,
    Exam,
    ExamClassroom,
    GradeTerm,
    SchoolProfile,
    Student,
    StudyPlan,
    StudySession,
)


def _seed(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    manager.initialize_public()
    SchoolProfile.create(id=1, school_name="مدرسه نمونه", academic_year="1405-1406", type="high")
    room = Classroom.create(grade_level=12, major=AcademicMajor.EXPERIMENTAL, code="الف")
    student = Student.create(
        national_id="1000000001", first_name="سارا", last_name="احمدی", classroom=room,
        major=AcademicMajor.EXPERIMENTAL, daily_active_hours=4,
    )
    first = Exam(
        name="نوبت اول", exam_date=date(2026, 1, 1), term=GradeTerm.NOBAT_1,
        max_score=20, grade_level=12, major=AcademicMajor.EXPERIMENTAL,
    )
    first.subjects = ["زیست"]
    first.save(force_insert=True)
    second = Exam(
        name="آزمون آزمایشی", exam_date=date(2026, 2, 1), term=GradeTerm.AZMAYESHI,
        max_score=100, grade_level=12, major=AcademicMajor.EXPERIMENTAL,
    )
    second.subjects = ["زیست", "شیمی"]
    second.save(force_insert=True)
    ExamClassroom.create(exam=first, classroom=room)
    ExamClassroom.create(exam=second, classroom=room)
    AcademicGrade.create(student=student, exam=first, subject_name="زیست", score=15)
    AcademicGrade.create(student=student, exam=second, subject_name="زیست", score=60)
    AcademicGrade.create(student=student, exam=second, subject_name="شیمی", score=80)
    AttendanceRecord.create(student=student, date=date(2026, 1, 3), status=AttendanceStatus.ABSENT)
    plan = StudyPlan.create(student=student, start_date=date(2026, 1, 3), end_date=date(2026, 1, 9))
    StudySession.create(plan=plan, day_of_week=0, start_time="16:00", end_time="17:30", subject_name="زیست", duration_minutes=90)
    return manager, student, plan


def test_pdf_data_helpers_select_and_aggregate(tmp_path):
    manager, student, plan = _seed(tmp_path)
    try:
        assert [(row.subject, row.term) for row in pdf_export.formal_scores(student)] == [("زیست", GradeTerm.NOBAT_1)]
        assert pdf_export.mock_trends(student)[0].percentage == 70.0
        assert pdf_export.attendance_summary(student).absent == 1
        assert pdf_export.weekly_hours(plan) == ((1.5, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0), 1.5)
        assert "زیست" in pdf_export.focus_note(student, plan)
    finally:
        manager.close()


def test_exports_write_nonempty_pdfs(tmp_path, qapp):
    manager, student, plan = _seed(tmp_path)
    try:
        weekly = tmp_path / "weekly.pdf"
        summary = tmp_path / "summary.pdf"
        pdf_export.export_weekly_plan_pdf(plan, str(weekly))
        pdf_export.export_academic_summary_pdf(student, str(summary))
        assert weekly.stat().st_size > 100
        assert summary.stat().st_size > 100
        assert weekly.read_bytes().startswith(b"%PDF")
        assert summary.read_bytes().startswith(b"%PDF")
    finally:
        manager.close()


def test_pdf_uses_readable_screen_coordinate_scale(tmp_path, qapp):
    printer = pdf_export._printer(str(tmp_path / "scale.pdf"), landscape=True)

    assert printer.resolution() <= 120
    assert printer.pageRect().width() < 2_000


def test_signature_row_stays_above_footer():
    height = 793

    assert pdf_export._signature_y(height) + 30 < height - pdf_export._MARGIN
