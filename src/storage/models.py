from datetime import date, datetime

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
)

from src.storage.db import db


class AcademicMajor:
    MATH = "ریاضی فیزیک"
    EXPERIMENTAL = "تجربی"
    HUMANITIES = "علوم انسانی"
    VOCATIONAL = "فنی و حرفه ای"
    GENERAL = "عمومی"


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
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db

    def save(self, *args, **kwargs):
        self.updated_at = datetime.now()
        return super().save(**args, **kwargs)


class Counselor(BaseModel):
    username = CharField(unique=True, index=True, max_length=50)
    password_hash = CharField(max_length=255)
    full_name = CharField(max_length=100)
    school_name = CharField(max_length=150)

    last_login = DateTimeField(null=True)

    def __str__(self):
        return f"{self.full_name} ({self.school_name})"


class Classroom(BaseModel):
    name = CharField(max_length=50, index=True)
    grade_level = IntegerField(default=10)

    major = CharField(max_length=50, default=AcademicMajor.GENERAL)
    academic_year = CharField(max_length=20, default="1405-1406")

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
        indexes = (("risk_level"), False)
        table_name = "users"

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


class CounselorNote(BaseModel):
    student = ForeignKeyField(Student, backref="notes", on_delete="CASCADE")
    title = CharField(max_length=100, default="یادداشت مشاوره")
    content = TextField()
    is_confidential = BooleanField(default=True)
    tags = CharField(max_length=150, default="عمومی")

    def __str__(self) -> str:
        return f"Note ({self.student.full_name}): {self.title}"


class AcademicGrade(BaseModel):
    student = ForeignKeyField(Student, backref="grades", on_delete="CASCADE")
    subject_name = CharField(max_length=50, index=True)
    score = DoubleField()
    max_score = DoubleField(default=20.0)
    exam_date = DateField(default=datetime.date.today, index=True)
    exam_type = CharField(max_length=30, default="مستمر")

    def get_percentage(self) -> float:
        return round((self.score / self.max_score) * 100, 1)


class AttendanceRecord(BaseModel):
    student = ForeignKeyField(Student, backref="attendance", on_delete="CASCADE")
    date = DateField(default=datetime.date.today, index=True)
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
    date = DateField(default=datetime.date.today, index=True)
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
    target_id = IntegerField(null=True)
    details = TextField(null=True)
