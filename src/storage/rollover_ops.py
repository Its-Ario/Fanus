from src.storage.audit import record_audit
from src.storage.db import db, vault_db
from src.storage.models import (
    AcademicGrade,
    AttendanceRecord,
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

ROLLOVER_MODELS = [
    DailyCheckIn,
    StudySession,
    StudyPlan,
    AttendanceRecord,
    AcademicGrade,
    ExamClassroom,
    Exam,
    Student,
]


def roll_over_year(new_year, *, keep_classrooms, wipe_vault, actor):
    counts = {}
    with db.atomic():
        for model in ROLLOVER_MODELS:
            counts[model.__name__] = model.delete().execute()
        if keep_classrooms:
            Classroom.update(academic_year=new_year).execute()
        else:
            counts["Classroom"] = Classroom.delete().execute()
        profile = SchoolProfile.get_instance()
        profile.academic_year = new_year
        profile.save()

    if wipe_vault:
        with vault_db.atomic():
            counts["CounselorNote"] = CounselorNote.delete().execute()

    record_audit(
        actor,
        "school.year_rollover",
        "SchoolProfile",
        None,
        details=(
            f"سال جدید: {new_year} · کلاس‌ها {'نگه داشته شد' if keep_classrooms else 'پاک شد'}"
        ),
    )
    return counts
