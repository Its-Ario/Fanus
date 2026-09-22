from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pytest

import src.storage.settings_ops as settings_ops
from src.core.auth import hash_password, verify_password
from src.storage.db import (
    DatabaseConfigurationError,
    DatabaseManager,
    encrypt_vault_value,
)
from src.storage.models import (
    AcademicGrade,
    Classroom,
    DailyCheckIn,
    Exam,
    ExamClassroom,
    PlanStatus,
    Student,
    StudyPlan,
    User,
)
from src.storage.settings_ops import change_own_password
from src.views.components.ui_kit import Avatar
from src.views.pages.dashboard_page import load_dashboard_data
from src.views.pages.login_dialog import LoginDialog


def test_password_hash_round_trip_and_invalid_values_fail_safely():
    encoded = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", encoded)
    assert not verify_password("wrong password", encoded)
    assert not verify_password("correct horse battery staple", "not-a-valid-hash")
    assert not verify_password("correct horse battery staple", None)


def test_public_database_initializes_without_creating_or_unlocking_vault(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "counselor_vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        User.create(username="active", full_name="کاربر فعال", is_active=True)
        User.create(username="inactive", full_name="کاربر غیرفعال", is_active=False)

        active_users = list(User.select().where(User.is_active))
        assert manager.initialized
        assert not manager.vault_initialized
        assert [user.username for user in active_users] == ["active"]
        assert not (tmp_path / "counselor_vault.db").exists()

        with pytest.raises(DatabaseConfigurationError):
            with manager.transaction(vault=True):
                pass
        with pytest.raises(DatabaseConfigurationError):
            encrypt_vault_value("نباید بدون بازگشایی ذخیره شود")
    finally:
        manager.close()


def test_active_non_manager_can_change_own_password(tmp_path, monkeypatch):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "counselor_vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    try:
        manager.initialize_public()
        monkeypatch.setattr(settings_ops, "get_database_manager", lambda: manager)
        user = User.create(
            username="assistant",
            full_name="کاربر عادی",
            role="assistant",
            can_manage_users=False,
            password_hash=hash_password("old-password"),
        )

        change_own_password(user, "old-password", "new-password")

        user = User.get_by_id(user.id)
        assert verify_password("new-password", user.password_hash)
    finally:
        manager.close()


def test_dashboard_data_is_derived_from_public_records(tmp_path):
    manager = DatabaseManager(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "counselor_vault.db",
        migrations_dir=tmp_path / "migrations",
    )
    today = date(2026, 8, 20)
    try:
        manager.initialize_public()
        classroom = Classroom.create(name="دهم الف", grade_level=10)
        first_student = Student.create(
            national_id="1000000001",
            first_name="سارا",
            last_name="احمدی",
            classroom=classroom,
        )
        second_student = Student.create(
            national_id="1000000002",
            first_name="رضا",
            last_name="کریمی",
            classroom=classroom,
        )
        Student.create(
            national_id="1000000003",
            first_name="غیرفعال",
            last_name="دانش آموز",
            classroom=classroom,
            is_active=False,
        )
        StudyPlan.create(
            student=first_student,
            title="برنامه فعال",
            end_date=today + timedelta(days=7),
            status=PlanStatus.ACTIVE,
        )
        StudyPlan.create(
            student=second_student,
            title="پیش نویس",
            end_date=today + timedelta(days=7),
            status=PlanStatus.DRAFT,
        )
        DailyCheckIn.create(
            student=first_student,
            date=today,
            completed_sessions=3,
            total_sessions=4,
        )
        DailyCheckIn.create(
            student=second_student,
            date=today,
            completed_sessions=2,
            total_sessions=2,
        )
        exam = Exam(
            name="نوبت اول",
            exam_date=today,
            term="نوبت اول",
            max_score=20.0,
            grade_level=10,
            major=classroom.major,
        )
        exam.subjects = ["ریاضی", "فیزیک"]
        exam.save(force_insert=True)
        ExamClassroom.create(exam=exam, classroom=classroom)
        AcademicGrade.create(student=first_student, exam=exam, subject_name="ریاضی", score=16)
        AcademicGrade.create(student=second_student, exam=exam, subject_name="ریاضی", score=18)
        AcademicGrade.create(student=first_student, exam=exam, subject_name="فیزیک", score=10)

        data = load_dashboard_data(today)

        assert data.active_student_count == 2
        assert data.active_plan_count == 1
        assert data.weekly_completion_rate == 83
        assert data.subject_averages[0].name == "ریاضی"
        assert data.subject_averages[0].percentage == 85
    finally:
        manager.close()


@dataclass
class FakeUser:
    username: str
    full_name: str
    role: str = "counselor"
    avatar_color: str = "#A855F7"
    password_hash: str | None = None
    is_active: bool = True
    last_login: object = None
    save_calls: int = 0

    def save(self):
        self.save_calls += 1


def test_login_dialog_bypasses_passwordless_account_and_records_login(qtbot):
    user = FakeUser(username="no-password", full_name="نگار احمدی")
    dialog = LoginDialog([user])
    qtbot.addWidget(dialog)

    dialog._choose_account(user)

    assert dialog.authenticated_user is user
    assert user.last_login is not None
    assert user.save_calls == 1


def test_login_dialog_rejects_bad_password_then_accepts_correct_one(qtbot):
    user = FakeUser(
        username="protected",
        full_name="مریم کریمی",
        password_hash=hash_password("a secure password"),
    )
    dialog = LoginDialog([user])
    qtbot.addWidget(dialog)
    dialog._choose_account(user)

    dialog.password_field.input.setText("wrong")
    dialog._submit_password()
    assert dialog.authenticated_user is None
    assert not dialog.password_field.message.isHidden()

    dialog.password_field.input.setText("a secure password")
    dialog._submit_password()
    assert dialog.authenticated_user is user
    assert user.save_calls == 1


def test_avatar_uses_an_explicit_account_color(qtbot):
    avatar = Avatar("سارا احمدی", color="#A855F7")
    qtbot.addWidget(avatar)

    assert "#A855F7" in avatar.styleSheet()
