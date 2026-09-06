import random
from datetime import date, timedelta

from src.storage.db import configure_database_manager, db
from src.storage.models import (
    AcademicGrade,
    AcademicMajor,
    Classroom,
    Exam,
    ExamClassroom,
    GradeTerm,
    RiskLevel,
    Student,
    StudyPeriod,
    subject_options,
)

MOCK_CLASSROOMS = (
    (10, AcademicMajor.MATH, "الف"),
    (10, AcademicMajor.EXPERIMENTAL, "ب"),
    (11, AcademicMajor.HUMANITIES, "الف"),
    (12, AcademicMajor.VOCATIONAL, "ب"),
)


MOCK_STUDENTS = (
    ("0010000001", "سارا", "احمدی", 0, RiskLevel.HIGH, 3.5, 6.0, 2.0, StudyPeriod.EVENING),
    ("0010000002", "محمد", "رضایی", 0, RiskLevel.LOW, 6.5, 7.5, 0.0, StudyPeriod.MORNING),
    ("0010000003", "نگار", "موسوی", 0, RiskLevel.MEDIUM, 4.5, 6.5, 1.0, StudyPeriod.EVENING),
    ("0010000004", "علی", "کریمی", 0, RiskLevel.LOW, 6.0, 7.0, 0.0, StudyPeriod.MORNING),
    ("0010000005", "مهسا", "حسینی", 0, RiskLevel.MEDIUM, 4.0, 6.5, 1.5, StudyPeriod.EVENING),
    ("0010000006", "پارسا", "اکبری", 1, RiskLevel.LOW, 6.5, 7.5, 0.0, StudyPeriod.MORNING),
    ("0010000007", "مریم", "قاسمی", 1, RiskLevel.MEDIUM, 4.5, 6.5, 1.0, StudyPeriod.EVENING),
    ("0010000008", "امیر", "جعفری", 1, RiskLevel.HIGH, 3.0, 5.5, 2.0, StudyPeriod.EVENING),
    ("0010000009", "یاسمن", "مرادی", 1, RiskLevel.LOW, 6.0, 7.0, 0.0, StudyPeriod.MORNING),
    ("0010000010", "کیان", "نوری", 1, RiskLevel.MEDIUM, 5.0, 6.5, 1.0, StudyPeriod.EVENING),
    ("0010000011", "زهرا", "صادقی", 2, RiskLevel.LOW, 6.5, 7.0, 0.0, StudyPeriod.MORNING),
    ("0010000012", "حسین", "کاظمی", 2, RiskLevel.MEDIUM, 4.5, 6.0, 1.0, StudyPeriod.EVENING),
    ("0010000013", "روناک", "طاهری", 2, RiskLevel.HIGH, 3.0, 5.5, 2.0, StudyPeriod.EVENING),
    ("0010000014", "رضا", "محمدی", 2, RiskLevel.LOW, 6.0, 7.5, 0.0, StudyPeriod.MORNING),
    ("0010000015", "نازنین", "بابایی", 2, RiskLevel.MEDIUM, 5.0, 6.5, 1.5, StudyPeriod.EVENING),
    ("0010000016", "آرمان", "زارعی", 3, RiskLevel.LOW, 6.5, 7.5, 0.0, StudyPeriod.MORNING),
    ("0010000017", "هانیه", "رحیمی", 3, RiskLevel.MEDIUM, 4.5, 6.0, 1.0, StudyPeriod.EVENING),
    ("0010000018", "سام", "نجفی", 3, RiskLevel.HIGH, 3.0, 5.5, 2.0, StudyPeriod.EVENING),
    ("0010000019", "ترانه", "یوسفی", 3, RiskLevel.LOW, 6.0, 7.0, 0.0, StudyPeriod.MORNING),
    ("0010000020", "میلاد", "عباسی", 3, RiskLevel.MEDIUM, 5.0, 6.5, 1.0, StudyPeriod.EVENING),
)


def seed_students(academic_year="1405-1406"):
    classrooms = []
    with db.atomic():
        for grade_level, major, code in MOCK_CLASSROOMS:
            classroom, _ = Classroom.get_or_create(
                grade_level=grade_level,
                major=major,
                code=code,
                academic_year=academic_year,
                defaults={"name": ""},
            )
            classrooms.append(classroom)

        roster: dict[int, list[Student]] = {c.id: [] for c in classrooms}
        band_index: dict[str, int] = {}
        for student_index, (
            national_id,
            first_name,
            last_name,
            classroom_index,
            risk_level,
            daily_active_hours,
            sleep_hours,
            tutoring_hours,
            preferred_study_period,
        ) in enumerate(MOCK_STUDENTS):
            classroom = classrooms[classroom_index]
            student, created = Student.get_or_create(
                national_id=national_id,
                defaults={
                    "first_name": first_name,
                    "last_name": last_name,
                    "classroom": classroom,
                    "major": classroom.major,
                    "risk_level": risk_level,
                    "daily_active_hours": daily_active_hours,
                    "sleep_hours": sleep_hours,
                    "tutoring_hours": tutoring_hours,
                    "preferred_study_period": preferred_study_period,
                },
            )
            if not created:
                student.first_name = first_name
                student.last_name = last_name
                student.classroom = classroom
                student.major = classroom.major
                student.risk_level = risk_level
                student.daily_active_hours = daily_active_hours
                student.sleep_hours = sleep_hours
                student.tutoring_hours = tutoring_hours
                student.preferred_study_period = preferred_study_period
                student.is_active = True
                student.save()
            roster[classroom.id].append(student)
            band_index[student.id] = student_index

        for classroom in classrooms:
            if not ExamClassroom.select().where(ExamClassroom.classroom == classroom).exists():
                _seed_exams(classroom, roster[classroom.id], band_index)

    return [s for students in roster.values() for s in students]


def _make_exam(classroom, name, term, subjects, *, days_ago, max_score=20.0):
    exam = Exam(
        name=name,
        exam_date=date.today() - timedelta(days=days_ago),
        term=term,
        max_score=max_score,
        grade_level=classroom.grade_level,
        major=classroom.major,
    )
    exam.subjects = list(subjects)
    exam.save(force_insert=True)
    ExamClassroom.create(exam=exam, classroom=classroom)
    return exam


def _seed_exams(classroom, students, band_index):
    """A varied current-year snapshot per class: term exams, class quizzes, mock exams.

    ponytail: mock distribution hand-tuned for band spread, not real data (carried over).
    """
    rng = random.Random(f"{classroom.grade_level}-{classroom.major}-{classroom.code}")
    subjects = list(subject_options(classroom.grade_level, classroom.major))
    if not subjects:
        return
    band_bases = (10.5, 13.5, 16.5, 19.0)

    exams: list[tuple[Exam, float]] = []  # (exam, per-exam noise scale)
    exams.append((_make_exam(classroom, "نوبت اول", GradeTerm.NOBAT_1, subjects, days_ago=70), 0.9))
    if rng.random() < 0.7:
        exams.append(
            (_make_exam(classroom, "نوبت دوم", GradeTerm.NOBAT_2, subjects, days_ago=7), 0.9)
        )
    for i in range(rng.randint(3, 6)):
        picked = rng.sample(subjects, rng.randint(1, 2))
        ceiling = 10.0 if i % 3 == 0 else 20.0
        exams.append(
            (
                _make_exam(
                    classroom, f"امتحان کلاسی {i + 1}", GradeTerm.KELASI, picked,
                    days_ago=rng.randint(1, 56), max_score=ceiling,
                ),
                1.6,
            )
        )
    if classroom.grade_level == 12:
        for i in range(rng.randint(1, 2)):
            exams.append(
                (
                    _make_exam(
                        classroom, f"آزمون آزمایشی {i + 1}", GradeTerm.AZMAYESHI, subjects,
                        days_ago=rng.randint(3, 45),
                    ),
                    1.4,
                )
            )

    for student in students:
        base = band_bases[band_index[student.id] % len(band_bases)]
        for exam, noise in exams:
            for subject in exam.subjects:
                if rng.random() < 0.05:  # ~5% absent -> NULL, exercises the null path
                    score = None
                else:
                    ratio = max(0.0, min(1.0, (base + rng.uniform(-noise, noise)) / 20.0))
                    score = round(ratio * exam.max_score, 2)
                AcademicGrade.create(
                    student=student, exam=exam, subject_name=subject, score=score
                )


def seed(academic_year="1405-1406"):
    manager = configure_database_manager()
    manager.initialize_public()
    try:
        return seed_students(academic_year)
    finally:
        manager.close()


if __name__ == "__main__":
    seed()
