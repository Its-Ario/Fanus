from datetime import date, timedelta

import src.storage.models as grade_models
from src.planner.generator import _weakness_map
from src.storage.db import DatabaseManager
from src.storage.models import (
    AcademicGrade,
    AcademicMajor,
    Classroom,
    Exam,
    ExamClassroom,
    GradeTerm,
    GradeValidationError,
    Student,
    _round2,
)

EXAM = date(2026, 9, 1)


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
    return manager, student, classroom


def _exam(classroom, subjects, *, term=GradeTerm.NOBAT_1, max_score=20.0, exam_date=EXAM):
    exam = Exam(
        name="آزمون",
        exam_date=exam_date,
        term=term,
        max_score=max_score,
        grade_level=classroom.grade_level,
        major=classroom.major,
    )
    exam.subjects = list(subjects)
    exam.save(force_insert=True)
    ExamClassroom.create(exam=exam, classroom=classroom)
    return exam


def _add_peers(classroom, exam, subject, scores, *, start=8000000000):
    for index, score in enumerate(scores, start=1):
        peer = Student.create(
            national_id=str(start + index),
            first_name=f"دانش‌آموز {index}",
            last_name="همکلاسی",
            classroom=classroom,
        )
        AcademicGrade.create(student=peer, exam=exam, subject_name=subject, score=score)


def test_exam_validation(tmp_path):
    manager, _, classroom = _student(tmp_path)
    try:
        base = dict(
            exam_date=EXAM,
            term=GradeTerm.NOBAT_1,
            max_score=20.0,
            grade_level=10,
            major=AcademicMajor.MATH,
        )
        cases = (
            {**base, "name": "  ", "subjects_json": '["ریاضی ۱"]'},
            {**base, "name": "آ", "subjects_json": "[]"},
            {**base, "name": "آ", "subjects_json": '["ریاضی ۱"]', "term": "نامعتبر"},
            {**base, "name": "آ", "subjects_json": '["ریاضی ۱"]', "max_score": 0},
            {**base, "name": "آ", "subjects_json": '["ریاضی ۱"]', "max_score": 101},
            {**base, "name": "آ", "subjects_json": '["ریاضی ۱"]', "exam_date": None},
        )
        for fields in cases:
            try:
                Exam(**fields).save(force_insert=True)
                assert False, f"expected GradeValidationError for {fields}"
            except GradeValidationError:
                pass
    finally:
        manager.close()


def test_grade_validation_and_rounding(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        exam = _exam(classroom, ["ریاضی ۱"])
        for fields in (
            {"subject_name": "", "score": 10},
            {"subject_name": "ریاضی ۱", "score": 21},
            {"subject_name": "ریاضی ۱", "score": 10, "weight": 0},
        ):
            try:
                AcademicGrade.create(student=student, exam=exam, **fields)
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
    manager, student, classroom = _student(tmp_path)
    try:
        subjects = ["ریاضی", "فیزیک", "شیمی", "زیست", "عربی"]
        n1 = _exam(classroom, subjects, term=GradeTerm.NOBAT_1, exam_date=EXAM)
        n2 = _exam(classroom, subjects, term=GradeTerm.NOBAT_2, exam_date=EXAM + timedelta(days=30))
        mostamar = _exam(classroom, subjects, term=GradeTerm.MOSTAMAR)
        kelasi = _exam(classroom, subjects, term=GradeTerm.KELASI)
        azmayeshi = _exam(classroom, subjects, term=GradeTerm.AZMAYESHI)

        AcademicGrade.create(student=student, exam=n1, subject_name="ریاضی", score=12)
        AcademicGrade.create(student=student, exam=n2, subject_name="ریاضی", score=16)
        AcademicGrade.create(student=student, exam=n1, subject_name="فیزیک", score=15, weight=2)
        AcademicGrade.create(student=student, exam=n1, subject_name="شیمی", score=None)
        AcademicGrade.create(student=student, exam=mostamar, subject_name="شیمی", score=2)
        AcademicGrade.create(student=student, exam=kelasi, subject_name="زیست", score=1)
        AcademicGrade.create(student=student, exam=azmayeshi, subject_name="عربی", score=1)

        assert student.calculate_gpa() == 15.33
        assert student.is_passing
    finally:
        manager.close()


def test_gpa_empty_when_no_moadel_grades(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        kelasi = _exam(classroom, ["ریاضی"], term=GradeTerm.KELASI)
        AcademicGrade.create(student=student, exam=kelasi, subject_name="ریاضی", score=18)
        assert student.calculate_gpa() == 0.0
    finally:
        manager.close()


def test_recent_ratio_weakness_map_skips_null_scores(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        for offset, score, maximum in ((1, 20, 20), (2, 10, 20), (3, 18, 20), (30, 0, 20)):
            exam = _exam(
                classroom,
                ["ریاضی"],
                term=GradeTerm.AZMAYESHI,
                max_score=maximum,
                exam_date=date.today() - timedelta(days=offset),
            )
            AcademicGrade.create(student=student, exam=exam, subject_name="ریاضی", score=score)
        absent = _exam(classroom, ["ریاضی"], term=GradeTerm.AZMAYESHI, exam_date=date.today())
        AcademicGrade.create(student=student, exam=absent, subject_name="ریاضی", score=None)

        weaknesses = _weakness_map(student, ("ریاضی",), ())
        assert weaknesses["ریاضی"] == 1.5
    finally:
        manager.close()


def test_weakness_map_rewards_strong_result_on_a_brutal_exam(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        exam = _exam(classroom, ["فیزیک"], max_score=20.0)
        AcademicGrade.create(student=student, exam=exam, subject_name="فیزیک", score=7)
        _add_peers(classroom, exam, "فیزیک", (8, 6, 6, 5, 5, 4, 4))

        assert _weakness_map(student, ("فیزیک",), ())["فیزیک"] == 1.5
    finally:
        manager.close()


def test_weakness_map_uses_raw_score_for_small_or_absent_cohorts(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        exam = _exam(classroom, ["فیزیک"], max_score=20.0)
        AcademicGrade.create(student=student, exam=exam, subject_name="فیزیک", score=7)
        _add_peers(classroom, exam, "فیزیک", (8, 6, 6, 5, 5, 4))
        absent = Student.create(
            national_id="8999999999", first_name="غایب", last_name="همکلاسی", classroom=classroom
        )
        AcademicGrade.create(student=absent, exam=exam, subject_name="فیزیک", score=None)

        assert _weakness_map(student, ("فیزیک",), ())["فیزیک"] == 2.0
    finally:
        manager.close()


def test_weakness_map_keeps_everyone_failed_floor(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        exam = _exam(classroom, ["فیزیک"], max_score=20.0)
        AcademicGrade.create(student=student, exam=exam, subject_name="فیزیک", score=3)
        _add_peers(classroom, exam, "فیزیک", (3, 3, 2, 2, 2, 1, 1))

        assert _weakness_map(student, ("فیزیک",), ())["فیزیک"] == 2.0
    finally:
        manager.close()


def test_weakness_map_isolates_multi_class_exam_cohorts(tmp_path):
    manager, student, classroom = _student(tmp_path)
    try:
        other_classroom = Classroom.create(
            name="دهم ب", grade_level=10, major=AcademicMajor.MATH, code="ب"
        )
        exam = _exam(classroom, ["فیزیک"], max_score=20.0)
        ExamClassroom.create(exam=exam, classroom=other_classroom)
        AcademicGrade.create(student=student, exam=exam, subject_name="فیزیک", score=7)
        _add_peers(classroom, exam, "فیزیک", (8, 6, 6, 5, 5, 4, 4))
        _add_peers(other_classroom, exam, "فیزیک", (20,) * 8, start=7000000000)

        assert _weakness_map(student, ("فیزیک",), ())["فیزیک"] == 1.5
    finally:
        manager.close()
