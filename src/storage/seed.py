from src.storage.db import configure_database_manager, db
from src.storage.models import AcademicMajor, Classroom, RiskLevel, Student, StudyPeriod

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

        students = []
        for (
            national_id,
            first_name,
            last_name,
            classroom_index,
            risk_level,
            daily_active_hours,
            sleep_hours,
            tutoring_hours,
            preferred_study_period,
        ) in MOCK_STUDENTS:
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
            students.append(student)

    return students


def seed(academic_year="1405-1406"):
    manager = configure_database_manager()
    manager.initialize_public()
    try:
        return seed_students(academic_year)
    finally:
        manager.close()


if __name__ == "__main__":
    seed()
