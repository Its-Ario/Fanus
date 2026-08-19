import sqlite3

import pytest

from src.storage.db import DatabaseConnectionError, DatabaseCredentials, DatabaseManager


def test_passwords_derive_stable_distinct_keys(tmp_path):
    salts_path = tmp_path / "database_salts.json"

    first = DatabaseCredentials.from_passwords("admin-password", "1234", salts_path)
    second = DatabaseCredentials.from_passwords("admin-password", "1234", salts_path)

    assert first == second
    assert first.fanus_key != first.vault_key
    assert len(first.fanus_key) == 64


def test_different_password_does_not_unlock_existing_store(tmp_path):
    salts_path = tmp_path / "database_salts.json"
    expected = DatabaseCredentials.from_passwords("admin-password", "1234", salts_path)
    changed = DatabaseCredentials.from_passwords("different-password", "1234", salts_path)

    assert changed.fanus_key != expected.fanus_key
    assert changed.vault_key == expected.vault_key


def test_manager_creates_two_sqlcipher_databases(tmp_path):
    credentials = DatabaseCredentials.from_passwords(
        "admin-password", "1234", tmp_path / "database_salts.json"
    )
    fanus_path = tmp_path / "fanus.db"
    vault_path = tmp_path / "counselor_vault.db"
    manager = DatabaseManager(
        credentials,
        fanus_path=fanus_path,
        vault_path=vault_path,
        migrations_dir=tmp_path / "migrations",
    )

    try:
        manager.initialize()
        assert manager.initialized
        assert fanus_path.exists()
        assert vault_path.exists()
        assert fanus_path.read_bytes()[:16] != b"SQLite format 3\x00"
        assert vault_path.read_bytes()[:16] != b"SQLite format 3\x00"
        with pytest.raises(sqlite3.DatabaseError):
            sqlite3.connect(fanus_path).execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        manager.close()


def test_manager_rejects_an_incorrect_database_key(tmp_path):
    salts_path = tmp_path / "database_salts.json"
    paths = {"fanus_path": tmp_path / "fanus.db", "vault_path": tmp_path / "counselor_vault.db"}
    migrations_path = tmp_path / "migrations"
    credentials = DatabaseCredentials.from_passwords("admin-password", "1234", salts_path)
    manager = DatabaseManager(credentials, migrations_dir=migrations_path, **paths)
    manager.initialize()
    manager.close()

    wrong_credentials = DatabaseCredentials.from_passwords("wrong-password", "1234", salts_path)
    rejected_manager = DatabaseManager(wrong_credentials, migrations_dir=migrations_path, **paths)
    try:
        with pytest.raises(DatabaseConnectionError):
            rejected_manager.initialize()
    finally:
        rejected_manager.close()
