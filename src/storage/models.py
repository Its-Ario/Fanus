from __future__ import annotations

import logging
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
    """TextField encrypted with AES-256-GCM with vault key."""

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
    VOCATIONAL = "فنی و حرفه‌ای"
    GENERAL = "عمومی"

    VALUES = (MATH, EXPERIMENTAL, HUMANITIES, VOCATIONAL, GENERAL)


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
    """Iranian calendar week order (Starts on Saturday)."""

    SATURDAY = 0  # شنبه
    SUNDAY = 1  # یکشنبه
    MONDAY = 2  # دوشنبه
    TUESDAY = 3  # سه‌شنبه
    WEDNESDAY = 4  # چهارشنبه
    THURSDAY = 5  # پنج‌شنبه
    FRIDAY = 6  # جمعه

    PERSIAN_NAMES = {
        0: "شنبه",
        1: "یکشنبه",
        2: "دوشنبه",
        3: "سه‌شنبه",
        4: "چهارشنبه",
        5: "پنج‌شنبه",
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
    def get_instance(cls):
        profile, _ = cls.get_or_create(id=1)
        return profile


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
        scores = [record.score for record in self.grades]
        if not scores:
            return 0.0
        return round(sum(scores) / len(scores), 2)


class CounselorNote(VaultBaseModel):
    student_id = UUIDField(index=True)
    title = CharField(max_length=100, default="یادداشت مشاوره")
    content = EncryptedTextField()
    is_confidential = BooleanField(default=True)
    tags = CharField(max_length=150, default="عمومی")

    def __str__(self) -> str:
        return f"Note ({self.student.full_name}): {self.title}"


class AcademicGrade(BaseModel):
    student = ForeignKeyField(Student, backref="grades", on_delete="CASCADE")
    subject_name = CharField(max_length=50, index=True)
    score = DoubleField()
    max_score = DoubleField(default=20.0)
    exam_date = DateField(default=datetime.today, index=True)
    exam_type = CharField(max_length=30, default="مستمر")

    def get_percentage(self) -> float:
        return round((self.score / self.max_score) * 100, 1)


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

    def get_active_sessions(self): ...


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
    actor_name = CharField(max_length=100, default="مشاور")
    action = CharField(max_length=50)
    target_entity = CharField(max_length=50)
    target_id = UUIDField(null=True)
    details = TextField(null=True)

    class Meta:
        indexes = ((("created_at",), False),)


PUBLIC_MODELS = [
    SchoolProfile,
    User,
    Classroom,
    Student,
    AcademicGrade,
    AttendanceRecord,
    StudyPlan,
    StudySession,
    DailyCheckIn,
    AuditLog,
]

VAULT_MODELS = [CounselorNote]
ALL_MODELS = PUBLIC_MODELS + VAULT_MODELS
