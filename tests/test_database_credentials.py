import sqlite3

from src.storage.db import DatabaseCredentials, DatabaseManager, decrypt_vault_value, encrypt_vault_value


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


def test_manager_creates_two_plain_sqlite_databases(tmp_path):
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
        sqlite3.connect(fanus_path).execute("SELECT name FROM sqlite_master").fetchall()
        sqlite3.connect(vault_path).execute("SELECT name FROM sqlite_master").fetchall()
    finally:
        manager.close()


def test_vault_value_round_trips_and_is_not_stored_as_plaintext(tmp_path):
    credentials = DatabaseCredentials.from_passwords(
        "admin-password", "1234", tmp_path / "database_salts.json"
    )
    from src.storage.db import set_vault_cipher_key

    set_vault_cipher_key(credentials.vault_key)
    try:
        secret = "این یک یادداشت محرمانه است"
        encrypted = encrypt_vault_value(secret)

        assert secret not in encrypted
        assert decrypt_vault_value(encrypted) == secret
    finally:
        set_vault_cipher_key(None)
