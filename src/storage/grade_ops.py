"""Validated write operations for student grades.

This module intentionally has no UI dependency so future entry/import surfaces use
the same validation boundary as the current application.
"""

from datetime import date
from typing import Optional

from src.storage.models import AcademicGrade, Student
from src.utils.persian_utils import to_ascii_digits


def _number(value) -> float:
    return float(to_ascii_digits(value))


def create_grade(
    student: Student,
    subject_name: str,
    score,
    *,
    term: str,
    max_score=20.0,
    weight=1.0,
    exam_date: Optional[date] = None,
) -> AcademicGrade:
    grade = AcademicGrade(
        student=student,
        subject_name=subject_name,
        score=_number(score),
        term=term,
        max_score=_number(max_score),
        weight=_number(weight),
        exam_date=exam_date or date.today(),
    )
    grade.save(force_insert=True)
    return grade


def update_grade(grade_id, **fields) -> AcademicGrade:
    grade = AcademicGrade.get_by_id(grade_id)
    for name in ("score", "max_score", "weight"):
        if name in fields:
            fields[name] = _number(fields[name])
    for name, value in fields.items():
        if not hasattr(grade, name):
            raise AttributeError("فیلد نمره نامعتبر است: {}".format(name))
        setattr(grade, name, value)
    grade.save()
    return grade


def delete_grade(grade_id) -> None:
    AcademicGrade.delete_by_id(grade_id)


def list_grades(student: Student, *, terms=None, subject=None, limit=None) -> list:
    query = AcademicGrade.select().where(AcademicGrade.student == student)
    if terms is not None:
        query = query.where(AcademicGrade.term << tuple(terms))
    if subject is not None:
        query = query.where(AcademicGrade.subject_name == subject)
    query = query.order_by(AcademicGrade.exam_date.desc(), AcademicGrade.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return list(query)
