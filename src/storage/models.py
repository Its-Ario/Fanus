from __future__ import annotations

import json
import logging
import math
from datetime import date, datetime
from uuid import uuid4

from peewee import (
    BooleanField,
    CharField,
    DateField,
    DateTimeField,
    DoubleField,
    ForeignKeyField,
    IntegerField,
    Model,
    TextField,
    UUIDField,
)

from src.storage.db import db, decrypt_vault_value, encrypt_vault_value, vault_db

logger = logging.getLogger(__name__)


class EncryptedTextField(TextField):
    """TextField with AES-256GCM"""

    def db_value(self, value):
        if value is None:
            return value
        return encrypt_vault_value(value)

    def python_value(self, value):
        if value is None:
            return value
        return decrypt_vault_value(value)


class AcademicMajor:
    MATH = "ریاضی فیزیک"
    EXPERIMENTAL = "علوم تجربی"
    HUMANITIES = "علوم انسانی"
    VOCATIONAL = "فنی و حرفه ای"
    GENERAL = "عمومی"

    VALUES = (MATH, EXPERIMENTAL, HUMANITIES, VOCATIONAL, GENERAL)


class GradeTerm:
    NOBAT_1 = "نوبت اول"
    NOBAT_2 = "نوبت دوم"
    MOSTAMAR = "مستمر"
    KELASI = "امتحان کلاسی"
    AZMAYESHI = "آزمون آزمایشی"

    VALUES = (NOBAT_1, NOBAT_2, MOSTAMAR, KELASI, AZMAYESHI)


MOADEL_TERMS = (GradeTerm.NOBAT_1, GradeTerm.NOBAT_2)
_TERM_RANK = {GradeTerm.NOBAT_1: 1, GradeTerm.NOBAT_2: 2}
PASS_MARK = 10.0
GPA_ROUNDING = "truncate"  # ponytail: school کارنامه truncates; flip to half_up for a school that rounds


class GradeValidationError(ValueError):
    pass


def _round2(value: float) -> float:
    if GPA_ROUNDING == "half_up":
        return math.floor(value * 100 + 0.5) / 100
    return math.floor(value * 100) / 100


SUBJECTS_BY_GRADE = {
    1: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    2: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    3: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    4: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    5: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    6: ("فارسی", "نگارش فارسی", "ریاضی", "علوم تجربی", "قرآن", "هدیه های آسمان", "مطالعات اجتماعی"),
    7: (
        "فارسی",
        "نگارش",
        "ریاضی",
        "علوم تجربی",
        "مطالعات اجتماعی",
        "پیام های آسمان",
        "قرآن",
        "عربی",
        "انگلیسی",
        "کار و فناوری",
        "فرهنگ و هنر",
        "تفکر و سبک زندگی",
    ),
    8: (
        "فارسی",
        "نگارش",
        "ریاضی",
        "علوم تجربی",
        "مطالعات اجتماعی",
        "پیام های آسمان",
        "قرآن",
        "عربی",
        "انگلیسی",
        "کار و فناوری",
        "فرهنگ و هنر",
        "تفکر و سبک زندگی",
    ),
    9: (
        "فارسی",
        "نگارش",
        "ریاضی",
        "علوم تجربی",
        "مطالعات اجتماعی",
        "پیام های آسمان",
        "قرآن",
        "عربی",
        "انگلیسی",
        "کار و فناوری",
        "فرهنگ و هنر",
        "آمادگی دفاعی",
        "تفکر و سبک زندگی",
    ),
}


HIGH_SCHOOL_SUBJECTS = {
    (10, AcademicMajor.MATH): (
        "فارسی و نگارش ۱",
        "عربی زبان قرآن ۱",
        "دین و زندگی ۱",
        "انگلیسی ۱",
        "ریاضی ۱",
        "هندسه ۱",
        "فیزیک ۱",
        "شیمی ۱",
        "آزمایشگاه علوم تجربی",
        "جغرافیای ایران",
        "آمادگی دفاعی",
        "تفکر و سواد رسانه ای",
        "هنر",
    ),
    (10, AcademicMajor.EXPERIMENTAL): (
        "فارسی و نگارش ۱",
        "عربی زبان قرآن ۱",
        "دین و زندگی ۱",
        "انگلیسی ۱",
        "ریاضی ۱",
        "زیست شناسی ۱",
        "فیزیک ۱",
        "شیمی ۱",
        "آزمایشگاه علوم تجربی",
        "جغرافیای ایران",
        "آمادگی دفاعی",
        "تفکر و سواد رسانه ای",
        "هنر",
    ),
    (10, AcademicMajor.HUMANITIES): (
        "فارسی و نگارش ۱",
        "عربی زبان قرآن ۱",
        "دین و زندگی ۱",
        "انگلیسی ۱",
        "ریاضی و آمار ۱",
        "علوم و فنون ادبی ۱",
        "اقتصاد",
        "جامعه شناسی ۱",
        "تاریخ ۱",
        "جغرافیای ایران",
        "منطق",
        "روان شناسی/دروس مربوط به برنامه رشته",
        "آمادگی دفاعی",
        "تفکر و سواد رسانه ای",
        "هنر",
    ),
    (11, AcademicMajor.MATH): (
        "فارسی و نگارش ۲",
        "عربی زبان قرآن ۲",
        "دین و زندگی ۲",
        "انگلیسی ۲",
        "حسابان ۱",
        "هندسه ۲",
        "آمار و احتمال",
        "فیزیک ۲",
        "شیمی ۲",
        "آزمایشگاه علوم تجربی ۲",
        "تاریخ معاصر ایران",
        "انسان و محیط زیست",
        "زمین شناسی/دروس مربوط به برنامه",
        "آمادگی دفاعی",
    ),
    (11, AcademicMajor.EXPERIMENTAL): (
        "فارسی و نگارش ۲",
        "عربی زبان قرآن ۲",
        "دین و زندگی ۲",
        "انگلیسی ۲",
        "ریاضی ۲",
        "زیست شناسی ۲",
        "فیزیک ۲",
        "شیمی ۲",
        "آزمایشگاه علوم تجربی ۲",
        "زمین شناسی",
        "تاریخ معاصر ایران",
        "انسان و محیط زیست",
        "آمادگی دفاعی",
    ),
    (11, AcademicMajor.HUMANITIES): (
        "فارسی و نگارش ۲",
        "عربی زبان قرآن ۲",
        "دین و زندگی ۲",
        "انگلیسی ۲",
        "ریاضی و آمار ۲",
        "علوم و فنون ادبی ۲",
        "جامعه شناسی ۲",
        "تاریخ ۲",
        "جغرافیا ۲",
        "فلسفه ۱",
        "روان شناسی",
        "انسان و محیط زیست",
        "تاریخ معاصر ایران",
        "آمادگی دفاعی",
    ),
    (12, AcademicMajor.MATH): (
        "فارسی و نگارش ۳",
        "عربی زبان قرآن ۳",
        "دین و زندگی ۳",
        "انگلیسی ۳",
        "حسابان ۲",
        "هندسه ۳",
        "ریاضیات گسسته",
        "فیزیک ۳",
        "شیمی ۳",
        "هویت اجتماعی",
        "سلامت و بهداشت",
        "مدیریت خانواده و سبک زندگی",
        "آمادگی دفاعی",
    ),
    (12, AcademicMajor.EXPERIMENTAL): (
        "فارسی و نگارش ۳",
        "عربی زبان قرآن ۳",
        "دین و زندگی ۳",
        "انگلیسی ۳",
        "ریاضی ۳",
        "زیست شناسی ۳",
        "فیزیک ۳",
        "شیمی ۳",
        "هویت اجتماعی",
        "سلامت و بهداشت",
        "مدیریت خانواده و سبک زندگی",
        "آمادگی دفاعی",
    ),
    (12, AcademicMajor.HUMANITIES): (
        "فارسی و نگارش ۳",
        "عربی زبان قرآن ۳",
        "دین و زندگی ۳",
        "انگلیسی ۳",
        "ریاضی و آمار ۳",
        "علوم و فنون ادبی ۳",
        "جامعه شناسی ۳",
        "تاریخ ۳",
        "جغرافیا ۳",
        "فلسفه ۲",
        "هویت اجتماعی",
        "سلامت و بهداشت",
        "مدیریت خانواده و سبک زندگی",
        "آمادگی دفاعی",
    ),
}


def subject_options(grade_level: int, major: str = AcademicMajor.GENERAL) -> tuple:
    """Return the supplied curriculum subjects for a grade and academic major."""
    if grade_level in SUBJECTS_BY_GRADE:
        return SUBJECTS_BY_GRADE[grade_level]
    return HIGH_SCHOOL_SUBJECTS.get((grade_level, major), ())


GRADE_ORDINALS = {
    1: "اول",
    2: "دوم",
    3: "سوم",
    4: "چهارم",
    5: "پنجم",
    6: "ششم",
    7: "هفتم",
    8: "هشتم",
    9: "نهم",
    10: "دهم",
    11: "یازدهم",
    12: "دوازدهم",
}


def parse_levels(raw: str) -> list[str]:
    valid = ("elementry", "middle", "high")
    seen = [value.strip() for value in (raw or "").split(",")]
    levels = [
        value for index, value in enumerate(seen) if value in valid and value not in seen[:index]
    ]
    if not levels:
        logger.warning("SchoolProfile.type is empty or unrecognized; falling back to high school.")
        return ["high"]
    return levels


def grade_options(raw_levels: str) -> list[int]:
    ranges = {"elementry": range(1, 7), "middle": range(7, 10), "high": range(10, 13)}
    return sorted({grade for level in parse_levels(raw_levels) for grade in ranges[level]})


class StudyPeriod:
    EVENING = "عصر / بعد از ظهر"
    MORNING = "صبح"


class RiskLevel:
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

    PERSIAN_MAP = {LOW: "کم 🟢", MEDIUM: "متوسط 🟡", HIGH: "زیاد 🔴"}


class PlanStatus:
    DRAFT = "Draft"
    ACTIVE = "Active"
    COMPLETED = "Completed"
    ARCHIVED = "Archived"

    PERSIAN_MAP = {DRAFT: "پیش نویس", ACTIVE: "فعال", COMPLETED: "تکمیل شده", ARCHIVED: "آرشیو"}


class DayOfWeek:
    SATURDAY = 0  # شنبه
    SUNDAY = 1  # یکشنبه
    MONDAY = 2  # دوشنبه
    TUESDAY = 3  # سه شنبه
    WEDNESDAY = 4  # چهارشنبه
    THURSDAY = 5  # پنج شنبه
    FRIDAY = 6  # جمعه

    PERSIAN_NAMES = {
        0: "شنبه",
        1: "یکشنبه",
        2: "دوشنبه",
        3: "سه شنبه",
        4: "چهارشنبه",
        5: "پنج شنبه",
        6: "جمعه",
    }


class BaseModel(Model):
    id = UUIDField(primary_key=True, default=uuid4)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)


class VaultBaseModel(Model):
    id = UUIDField(primary_key=True, default=uuid4)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = vault_db

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(*args, **kwargs)


class SchoolProfile(Model):
    id = IntegerField(primary_key=True, default=1)
    school_name = CharField()
    academic_year = CharField()
    school_start_time = CharField(max_length=5, default="07:30")
    school_end_time = CharField(max_length=5, default="13:30")
    type = CharField(
        choices=[
            (
                "elementry",
                "دبستان",
                "middle",
                "دوره اول دبیرستان(راهنمایی)",
                "high",
                "دوره دوم دبیرستان",
            )
        ]
    )
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db

    @classmethod
    def get_instance(cls) -> "SchoolProfile":
        profile, _ = cls.get_or_create(id=1)
        return profile

    @property
    def school_hours(self):
        return self.school_start_time, self.school_end_time


class PlannerSettings(Model):
    """Singleton tuning knobs for the study-plan engine (soft-constraint weights)."""

    id = IntegerField(primary_key=True, default=1)
    block_minutes = IntegerField(default=90)
    weights_json = TextField(default="{}")
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "plannersettings"

    @classmethod
    def get_instance(cls):
        instance, _ = cls.get_or_create(id=1)
        return instance

    @property
    def weights(self) -> dict:
        import json

        try:
            return dict(json.loads(self.weights_json or "{}"))
        except (ValueError, TypeError):
            return {}

    @weights.setter
    def weights(self, value: dict) -> None:
        import json

        self.weights_json = json.dumps(dict(value or {}), ensure_ascii=False)


class User(BaseModel):
    username = CharField(unique=True, index=True, max_length=50)
    password_hash = CharField(max_length=255, null=True)
    full_name = CharField(max_length=100)
    role = CharField(
        choices=[("counselor", "مشاور"), ("assistant", "معاون"), ("principal", "مدیر مدرسه")],
        default="counselor",
    )
    avatar_color = CharField(default="#0D9488")
    can_manage_users = BooleanField(default=False)

    is_active = BooleanField(default=True)
    last_login = DateTimeField(null=True)

    def __str__(self):
        return f"{self.full_name} ({self.school_name})"


class Classroom(BaseModel):
    name = CharField(max_length=50, index=True)
    code = CharField(max_length=30, default="")
    grade_level = IntegerField(default=10)

    major = CharField(max_length=50, default=AcademicMajor.GENERAL)
    academic_year = CharField(max_length=20, default="1405-1406")

    class Meta:
        indexes = ((("grade_level", "major", "code", "academic_year"), True),)

    def compose_name(self) -> str:
        ordinal = GRADE_ORDINALS.get(self.grade_level, str(self.grade_level))
        if self.major == AcademicMajor.GENERAL:
            return f"{ordinal} - {self.code}"
        return f"{ordinal} {self.major} - {self.code}"

    def save(self, *args, **kwargs):
        self.name = self.compose_name()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} - {self.academic_year}"


class Student(BaseModel):
    national_id = CharField(unique=True, index=True, max_length=10)
    first_name = CharField(max_length=50)

    last_name = CharField(max_length=50, index=True)
    classroom = ForeignKeyField(Classroom, backref="students", on_delete="CASCADE")

    major = CharField(max_length=50, default=AcademicMajor.GENERAL)

    is_active = BooleanField(default=True)

    daily_active_hours = DoubleField(default=5.0)
    sleep_hours = DoubleField(default=7.0)
    tutoring_hours = DoubleField(default=0.0)  # Outside classes
    preferred_study_period = CharField(max_length=20, default=StudyPeriod.EVENING)

    # ML Data
    risk_level = CharField(max_length=10, default=RiskLevel.LOW, index=True)
    burnout_score = DoubleField(default=0.0)
    disengagement_score = DoubleField(default=0.0)
    risk_factors_json = TextField(default="[]")  # json

    class Meta:
        table_name = "students"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def risk_level_persian(self) -> str:
        return RiskLevel.PERSIAN_MAP.get(self.risk_level, "-")

    def calculate_gpa(self) -> float:
        # One row per (subject, exam) enforced by AcademicGrade's unique index; when the
        # same subject appears in several معدل exams the latest/highest term wins.
        latest = {}
        rows = sorted(
            (
                row
                for row in self.grades
                if row.score is not None and row.exam_id and row.exam.term in MOADEL_TERMS
            ),
            key=lambda row: (_TERM_RANK[row.exam.term], row.exam.exam_date, row.created_at),
            reverse=True,
        )
        for row in rows:
            latest.setdefault(row.subject_name, row)
        if not latest:
            return 0.0
        total_weight = sum(row.weight for row in latest.values())
        if not total_weight:
            return 0.0
        return _round2(sum(row.score * row.weight for row in latest.values()) / total_weight)

    @property
    def is_passing(self) -> bool:
        return self.calculate_gpa() >= PASS_MARK


class CounselorNote(VaultBaseModel):
    student_id = UUIDField(index=True)
    # The public User table is deliberately not a foreign key: notes are kept in the
    # separately encrypted vault database.  Missing owners on legacy records fail
    # closed in note_ops and are never shown to a counselor.
    author_id = UUIDField(null=True, index=True)
    title = CharField(max_length=100, default="یادداشت مشاوره")
    content = EncryptedTextField()
    is_confidential = BooleanField(default=True)
    tags = CharField(max_length=150, default="عمومی")

    def __str__(self) -> str:
        return f"Note ({self.student_id}): {self.title}"


class Exam(BaseModel):
    """A teacher-defined assessment: one نوبت/date/سقف نمره over one or more classes and subjects."""

    name = CharField(max_length=100)
    exam_date = DateField(index=True)
    term = CharField(max_length=30)
    max_score = DoubleField(default=20.0)  # one ceiling for every subject column
    grade_level = IntegerField()
    major = CharField(max_length=50)
    subjects_json = TextField(default="[]")  # ordered list of subject_name strings

    @property
    def subjects(self) -> list[str]:
        try:
            return list(json.loads(self.subjects_json or "[]"))
        except (ValueError, TypeError):
            return []

    @subjects.setter
    def subjects(self, value):
        self.subjects_json = json.dumps(list(value or []), ensure_ascii=False)

    def save(self, *args, **kwargs):
        if not (self.name or "").strip():
            raise GradeValidationError("نام آزمون نمی‌تواند خالی باشد.")
        if not self.subjects:
            raise GradeValidationError("حداقل یک درس برای آزمون لازم است.")
        if self.term not in GradeTerm.VALUES:
            raise GradeValidationError("نوبت نامعتبر است.")
        if not (0 < self.max_score <= 20):
            raise GradeValidationError("سقف نمره باید بین ۰ تا ۲۰ باشد.")
        if self.exam_date is None:
            raise GradeValidationError("تاریخ آزمون لازم است.")
        self.name = self.name.strip()
        return super().save(*args, **kwargs)


class ExamClassroom(BaseModel):
    """One row per class an exam covers -> one tab in the grade grid."""

    exam = ForeignKeyField(Exam, backref="exam_classrooms", on_delete="CASCADE")
    classroom = ForeignKeyField(Classroom, on_delete="CASCADE")

    class Meta:
        indexes = ((("exam", "classroom"), True),)


class AcademicGrade(BaseModel):
    student = ForeignKeyField(Student, backref="grades", on_delete="CASCADE")
    exam = ForeignKeyField(Exam, backref="grades", null=True, on_delete="CASCADE")
    subject_name = CharField(max_length=50, index=True)
    score = DoubleField(null=True)  # NULL = absent/exempt; never written as 0
    weight = DoubleField(default=1.0)  # معدل weighting escape hatch, still unexposed in the UI

    class Meta:
        indexes = ((("exam", "student", "subject_name"), True),)

    @property
    def ceiling(self) -> float:
        return self.exam.max_score if self.exam_id else 20.0

    def save(self, *args, **kwargs):
        if not (self.subject_name or "").strip():
            raise GradeValidationError("نام درس نمی‌تواند خالی باشد.")
        if self.weight <= 0:
            raise GradeValidationError("ضریب باید بزرگ‌تر از صفر باشد.")
        if self.score is not None and not (0 <= self.score <= self.ceiling):
            raise GradeValidationError("نمره باید بین ۰ و سقف نمره باشد.")
        self.subject_name = self.subject_name.strip()
        return super().save(*args, **kwargs)

    def get_percentage(self) -> float:
        if self.score is None:
            return 0.0
        return round((self.score / self.ceiling) * 100, 1)

    @property
    def is_passing(self) -> bool:
        return self.score is not None and self.score >= PASS_MARK


class AttendanceRecord(BaseModel):
    student = ForeignKeyField(Student, backref="attendance", on_delete="CASCADE")
    date = DateField(default=datetime.today, index=True)
    status = CharField(max_length=20, default="present")
    reason = CharField(max_length=255, null=True)

    class Meta:
        indexes = ((("student", "date"), True),)


class StudyPlan(BaseModel):
    student = ForeignKeyField(Student, backref="study_plans", on_delete="CASCADE")
    title = CharField(max_length=100, default="برنامه مطالعاتی")

    start_date = DateField(default=date.today)
    end_date = DateField()

    status = CharField(max_length=20, default=PlanStatus.ACTIVE, index=True)

    confidence_score = DoubleField(default=85.0)
    is_ai_generated = BooleanField(default=True)
    is_approved = BooleanField(default=False)
    approved_at = DateTimeField(null=True)

    class Meta:
        table_name = "study_plans"

    def get_active_sessions(self):
        """Return this plan's sessions in the order used by the weekly record."""
        return self.sessions.order_by(StudySession.start_time, StudySession.end_time)


class StudySession(BaseModel):
    plan = ForeignKeyField(StudyPlan, backref="sessions", on_delete="CASCADE")
    day_of_week = IntegerField(choices=[(i, DayOfWeek.PERSIAN_NAMES[i]) for i in range(7)])
    start_time = CharField(max_length=5, default="16:00")  # HH:MM
    end_time = CharField(max_length=5, default="17:30")  # HH:MM
    subject_name = CharField(max_length=50)
    session_type = CharField(max_length=30, default="مطالعه")
    duration_minutes = IntegerField(default=90)
    is_locked = BooleanField(default=False)

    @property
    def day_name_persian(self) -> str:
        return DayOfWeek.PERSIAN_NAMES.get(self.day_of_week, "نامشخص")


class DailyCheckIn(BaseModel):
    student = ForeignKeyField(Student, backref="check_ins", on_delete="CASCADE")
    date = DateField(default=datetime.today, index=True)
    completed_sessions = IntegerField(default=0)
    total_sessions = IntegerField(default=0)
    completion_rate = DoubleField(default=0.0)
    status = CharField(max_length=20, default="completed")
    skip_reason = CharField(max_length=100, null=True)
    mood_rating = IntegerField(default=3)

    class Meta:
        indexes = ((("student", "date"), True),)


class AuditLog(BaseModel):
    actor_id = UUIDField(null=True, index=True)
    actor_name = CharField(max_length=100, default="مشاور")
    action = CharField(max_length=50)
    target_entity = CharField(max_length=50)
    target_id = UUIDField(null=True)
    student_id = UUIDField(null=True, index=True)
    details = TextField(null=True)

    class Meta:
        indexes = ((("created_at",), False),)


PUBLIC_MODELS = [
    SchoolProfile,
    PlannerSettings,
    User,
    Classroom,
    Student,
    Exam,
    ExamClassroom,
    AcademicGrade,
    AttendanceRecord,
    StudyPlan,
    StudySession,
    DailyCheckIn,
    AuditLog,
]

VAULT_MODELS = [CounselorNote]
ALL_MODELS = PUBLIC_MODELS + VAULT_MODELS
