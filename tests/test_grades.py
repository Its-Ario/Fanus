from datetime import date, timedelta

import src.storage.models as grade_models
from src.planner.generator import _weakness_map
from src.storage.db import DatabaseManager
from src.storage.grade_ops import create_grade
from src.storage.models import (
    AcademicGrade,
    AcademicMajor,
    Classroom,
    GradeTerm,
    GradeValidationError,
    Student,
    _round2,
)


def _student(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    manager.initialize_public()
    classroom = Classroom.create(name="دهم", grade_level=10, major=AcademicMajor.MATH)
    student = Student.create(
        national_id="3000000001", first_name="آرین", last_name="امینی", classroom=classroom
    )
    return manager, student


def test_grade_validation_and_rounding(tmp_path):
    manager, student = _student(tmp_path)
    try:
        for fields in (
            {"subject_name": "", "score": 10},
            {"subject_name": "ریاضی", "score": 10, "max_score": 0},
            {"subject_name": "ریاضی", "score": 21},
            {"subject_name": "ریاضی", "score": 10, "term": "نامعتبر"},
            {"subject_name": "ریاضی", "score": 10, "weight": 0},
        ):
            try:
                AcademicGrade.create(student=student, **fields)
                assert False, "expected GradeValidationError"
            except GradeValidationError:
                pass
        assert _round2(19.999) == 19.99
        original = grade_models.GPA_ROUNDING
        grade_models.GPA_ROUNDING = "half_up"
        assert _round2(19.995) == 20.0
        grade_models.GPA_ROUNDING = original
    finally:
        manager.close()


def test_gpa_uses_latest_highest_term_and_weights(tmp_path):
    manager, student = _student(tmp_path)
    try:
        today = date.today()
        AcademicGrade.create(student=student, subject_name="ریاضی", score=12, term=GradeTerm.NOBAT_1)
        AcademicGrade.create(student=student, subject_name="ریاضی", score=16, term=GradeTerm.NOBAT_2)
        AcademicGrade.create(
            student=student, subject_name="فیزیک", score=13, term=GradeTerm.NOBAT_1, weight=2
        )
        AcademicGrade.create(
            student=student,
            subject_name="فیزیک",
            score=15,
            term=GradeTerm.NOBAT_1,
            exam_date=today + timedelta(days=1),
            weight=2,
        )
        AcademicGrade.create(student=student, subject_name="شیمی", score=2, term=GradeTerm.MOSTAMAR)
        AcademicGrade.create(student=student, subject_name="زیست", score=1, term=GradeTerm.KELASI)
        AcademicGrade.create(student=student, subject_name="عربی", score=1, term=GradeTerm.AZMAYESHI)
        assert student.calculate_gpa() == 15.33
        assert student.is_passing
        assert not AcademicGrade.get(AcademicGrade.subject_name == "شیمی").is_passing
    finally:
        manager.close()


def test_grade_ops_and_recent_ratio_weakness_map(tmp_path):
    manager, student = _student(tmp_path)
    try:
        grade = create_grade(student, "پروژه پژوهشی", "۵", term=GradeTerm.KELASI, max_score="۱۰")
        assert grade.score == 5.0 and grade.max_score == 10.0
        for offset, score, maximum in ((1, 10, 20), (2, 5, 10), (3, 18, 20), (30, 0, 20)):
            AcademicGrade.create(
                student=student,
                subject_name="ریاضی",
                score=score,
                max_score=maximum,
                term=GradeTerm.AZMAYESHI,
                exam_date=date.today() - timedelta(days=offset),
            )
        weaknesses = _weakness_map(student, ("ریاضی", "پروژه پژوهشی"), ())
        assert weaknesses["ریاضی"] == 1.5  # last three normalized ratios average to 2/3
        assert weaknesses["پروژه پژوهشی"] == 2.0
    finally:
        manager.close()
