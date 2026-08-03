from datetime import datetime

from peewee import (
    BooleanField,
    CharField,
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
    GENERAL ="عمومی"

class StudyPeriod:
    EVENING = "عصر / بعد از ظهر"
    MORNING = "صبح"

class RiskLevel:
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

    PERSIAN_MAP = {
        LOW: "کم 🟢",
        MEDIUM: "متوسط 🟡",
        HIGH: "زیاد 🔴"
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
    first_name = CharField(
        max_length=50
    )

    last_name = CharField(
        max_length=50,
        index=True
    )
    classroom = ForeignKeyField(Classroom, backref="students", on_delete="CASCADE")

    major = CharField(max_length=50, default=AcademicMajor.GENERAL)

    is_active = BooleanField(default=True)

    daily_active_hours = DoubleField(default=5.0)
    sleep_hours = DoubleField(default=7.0)
    tutoring_hours = DoubleField(default=0.0) # Outside classes
    preferred_study_period = CharField(max_length=20, default=StudyPeriod.EVENING)

    # ML Data
    risk_level = CharField(max_length=10, default=RiskLevel.LOW, index=True)
    burnout_score = DoubleField(default=0.0)
    disengagement_score = DoubleField(default=0.0)
    risk_factors_json = TextField(default="[]") # json

    class Meta:
        indexes = (
        (("risk_level"), False)
        )
        table_name = "users"

class StudyPlan(BaseModel):

    student = ForeignKeyField(
        Student,
        backref="study_plans",
        on_delete="CASCADE"
    )

    subject = CharField(
        max_length=50
    )

    hours = IntegerField()


    class Meta:
        table_name = "study_plans"
