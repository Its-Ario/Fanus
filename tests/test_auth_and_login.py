from __future__ import annotations

from dataclasses import dataclass

import pytest

from src.core.auth import hash_password, verify_password
from src.storage.db import (
    DatabaseConfigurationError,
    DatabaseManager,
    encrypt_vault_value,
)
from src.storage.models import User
from src.views.components.ui_kit import Avatar
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
