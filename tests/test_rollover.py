from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.storage import rollover_ops
from src.storage.db import DatabaseCredentials, DatabaseManager
from src.storage.models import (
    AcademicGrade,
    AttendanceRecord,
    AuditLog,
    Classroom,
    CounselorNote,
    DailyCheckIn,
    Exam,
    ExamClassroom,
    SchoolProfile,
    Student,
    StudyPlan,
    StudySession,
)

ACTOR = SimpleNamespace(id=uuid4(), full_name="مدیر")


@pytest.fixture
def env(tmp_path):
    manager = DatabaseManager(
        DatabaseCredentials.from_vault_pin("1234", tmp_path / "database_salts.json"),
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
        state_anchor_path=tmp_path / "anchor",
    )
    manager.initialize()
    _seed()
    try:
        yield manager
    finally:
        try:
            manager.close()
        except Exception:
            pass


def _seed():
    SchoolProfile.create(id=1, school_name="مدرسه", academic_year="1404-1405", type="high")
    room = Classroom.create(grade_level=10, code="101", academic_year="1404-1405")
    student = Student.create(
        national_id="2000000001", first_name="ف", last_name="خ", classroom=room
    )
    exam = Exam.create(
        name="امتحان",
        exam_date=date(2025, 10, 1),
        term="نوبت اول",
        grade_level=10,
        major="عمومی",
        subjects_json='["ریاضی"]',
    )
    ExamClassroom.create(exam=exam, classroom=room)
    AcademicGrade.create(student=student, exam=exam, subject_name="ریاضی", score=18.0)
    AttendanceRecord.create(student=student, date=date(2025, 10, 1), status="present")
    plan = StudyPlan.create(student=student, end_date=date(2025, 12, 1))
    StudySession.create(plan=plan, day_of_week=0, subject_name="ریاضی")
    DailyCheckIn.create(student=student, date=date(2025, 10, 1))
    CounselorNote.create(student_id=student.id, content="محرمانه")


def _academic_empty():
    return all(m.select().count() == 0 for m in rollover_ops.ROLLOVER_MODELS)


def test_keep_classrooms(env):
    counts = rollover_ops.roll_over_year(
        "1405-1406", keep_classrooms=True, wipe_vault=False, actor=ACTOR
    )
    assert _academic_empty()
    assert counts["Student"] == 1
    room = Classroom.get()
    assert room.academic_year == "1405-1406"
    assert SchoolProfile.get_instance().academic_year == "1405-1406"
    assert AuditLog.select().where(AuditLog.action == "school.year_rollover").count() == 1


def test_drop_classrooms(env):
    rollover_ops.roll_over_year("1405-1406", keep_classrooms=False, wipe_vault=False, actor=ACTOR)
    assert Classroom.select().count() == 0


def test_vault_wiped_only_when_requested(env):
    rollover_ops.roll_over_year("1405-1406", keep_classrooms=True, wipe_vault=False, actor=ACTOR)
    assert CounselorNote.select().count() == 1

    rollover_ops.roll_over_year("1406-1407", keep_classrooms=True, wipe_vault=True, actor=ACTOR)
    assert CounselorNote.select().count() == 0


def test_failure_rolls_back(env, monkeypatch):
    real_delete = Student.delete

    def boom(cls):
        raise RuntimeError("boom")

    monkeypatch.setattr(Student, "delete", classmethod(boom))
    with pytest.raises(RuntimeError):
        rollover_ops.roll_over_year(
            "1405-1406", keep_classrooms=True, wipe_vault=False, actor=ACTOR
        )
    monkeypatch.setattr(Student, "delete", real_delete)

    assert Student.select().count() == 1
    assert AttendanceRecord.select().count() == 1
    assert SchoolProfile.get_instance().academic_year == "1404-1405"
    assert AuditLog.select().where(AuditLog.action == "school.year_rollover").count() == 0
