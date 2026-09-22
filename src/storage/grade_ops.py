from collections import namedtuple

from src.storage.db import db
from src.storage.models import AcademicGrade, Exam, Student
from src.utils.persian_utils import to_ascii_digits

SaveResult = namedtuple("SaveResult", ("created", "updated", "cleared"))


def _number(value) -> float:
    return float(to_ascii_digits(value))


def _score(value):
    if value is None or str(value).strip() == "":
        return None
    return _number(value)


def create_grade(
    student: Student,
    subject_name: str,
    score,
    *,
    exam: Exam = None,
    weight=1.0,
) -> AcademicGrade:
    grade = AcademicGrade(
        student=student,
        exam=exam,
        subject_name=subject_name,
        score=_score(score),
        weight=_number(weight),
    )
    grade.save(force_insert=True)
    return grade


def update_grade(grade_id, **fields) -> AcademicGrade:
    grade = AcademicGrade.get_by_id(grade_id)
    if "score" in fields:
        fields["score"] = _score(fields["score"])
    if "weight" in fields:
        fields["weight"] = _number(fields["weight"])
    for name, value in fields.items():
        if not hasattr(grade, name):
            raise AttributeError("فیلد نمره نامعتبر است: {}".format(name))
        setattr(grade, name, value)
    grade.save()
    return grade


def delete_grade(grade_id) -> None:
    AcademicGrade.delete_by_id(grade_id)


def save_grades_bulk(exam: Exam, entries, *, actor=None) -> SaveResult:
    created = updated = cleared = 0
    existing = {
        (row.student_id, row.subject_name): row
        for row in AcademicGrade.select().where(AcademicGrade.exam == exam)
    }
    with db.atomic():
        for entry in entries:
            student = entry["student"]
            subject_name = entry["subject_name"]
            score = _score(entry["score"])
            row = existing.get((student.id, subject_name))
            if score is None:
                if row is not None and row.score is not None:
                    row.score = None
                    row.save()
                    cleared += 1
                continue
            if row is None:
                row = AcademicGrade(
                    exam=exam,
                    student=student,
                    subject_name=subject_name,
                    score=score,
                    weight=1.0,
                )
                row.save(force_insert=True)
                existing[(student.id, subject_name)] = row
                created += 1
            else:
                row.score = score
                row.save()
                updated += 1
    return SaveResult(created=created, updated=updated, cleared=cleared)


def list_grades(student: Student, *, terms=None, subject=None, limit=None) -> list:
    query = (
        AcademicGrade.select(AcademicGrade, Exam).join(Exam).where(AcademicGrade.student == student)
    )
    if terms is not None:
        query = query.where(Exam.term << tuple(terms))
    if subject is not None:
        query = query.where(AcademicGrade.subject_name == subject)
    query = query.order_by(Exam.exam_date.desc(), AcademicGrade.created_at.desc())
    if limit is not None:
        query = query.limit(limit)
    return list(query)
