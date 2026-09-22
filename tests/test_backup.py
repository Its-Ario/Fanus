import io
import json
import os
import zipfile
from uuid import uuid4

import pytest

import src.storage.db as dbmod
from src.storage import backup_ops
from src.storage.backup_ops import BackupError
from src.storage.db import DatabaseCredentials, DatabaseManager, set_vault_cipher_key
from src.storage.models import Classroom, CounselorNote, Student, User


def _seed(n=5):
    room = Classroom.create(grade_level=10, code="101")
    for i in range(n):
        Student.create(
            national_id=f"200000000{i}", first_name=f"ف{i}", last_name=f"خ{i}", classroom=room
        )
    return room


def _paths(tmp_path):
    return dict(
        fanus_path=tmp_path / "fanus.db",
        vault_path=tmp_path / "counselor_vault.db",
        migrations_dir=tmp_path / "migrations",
    )


@pytest.fixture
def env(tmp_path):
    creds = DatabaseCredentials.from_vault_pin("1234", tmp_path / "database_salts.json")
    manager = DatabaseManager(creds, state_anchor_path=tmp_path / "anchor", **_paths(tmp_path))
    manager.initialize_public()
    dbmod._manager = manager
    actor = User.create(
        username="adm",
        full_name="مدیر",
        role="principal",
        can_manage_users=True,
        is_active=True,
    )
    try:
        yield manager, actor, tmp_path
    finally:
        try:
            manager.close()
        except Exception:
            pass
        dbmod._manager = None
        set_vault_cipher_key(None)


def _make_fanusbak(members: dict, manifest_overrides=None) -> bytes:
    manifest = {
        "format": "fanusbak",
        "format_version": 1,
        "fanus_version": "0.0.1",
        "created_at_fa": "x",
        "created_at_iso": "x",
        "school_name": "s",
        "includes_vault": False,
        "files": {n: {"sha256": backup_ops._sha256_bytes(d)} for n, d in members.items()},
    }
    if manifest_overrides:
        manifest.update(manifest_overrides)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False))
        for name, data in members.items():
            zf.writestr(name, data)
    return backup_ops._seal(buf.getvalue())


def test_round_trip_public_only(env):
    _, actor, tmp = env
    _seed()
    dest = tmp / "b.fanusbak"
    backup_ops.create_backup(dest, actor)
    assert dest.exists()

    Student.delete().execute()
    assert Student.select().count() == 0

    info = backup_ops.restore_backup(dest, actor)
    assert info.includes_vault is False

    reopened = DatabaseManager(**_paths(tmp))
    reopened.initialize_public()
    try:
        assert Student.select().count() == 5
    finally:
        reopened.close()


def test_round_trip_with_vault_and_reanchor(env):
    manager, actor, tmp = env
    manager.unlock_vault(DatabaseCredentials.from_vault_pin("1234", tmp / "database_salts.json"))
    with manager.transaction(vault=True):
        CounselorNote.create(student_id=uuid4(), content="محرمانه")

    dest = tmp / "v.fanusbak"
    backup_ops.create_backup(dest, actor, include_vault=True)
    assert backup_ops.inspect_backup(dest).includes_vault is True

    CounselorNote.delete().execute()
    backup_ops.restore_backup(dest, actor)
    assert (tmp / ".restore_pending").exists()

    reopened = DatabaseManager(
        DatabaseCredentials.from_vault_pin("1234", tmp / "database_salts.json"),
        state_anchor_path=tmp / "anchor2",
        **_paths(tmp),
    )
    reopened.initialize()
    try:
        assert not (tmp / ".restore_pending").exists()
        notes = list(CounselorNote.select())
        assert len(notes) == 1 and notes[0].content == "محرمانه"
    finally:
        reopened.close()


def test_tamper_detected(env):
    _, actor, tmp = env
    _seed()
    dest = tmp / "b.fanusbak"
    backup_ops.create_backup(dest, actor)
    raw = bytearray(dest.read_bytes())
    raw[-1] ^= 0xFF
    dest.write_bytes(bytes(raw))
    with pytest.raises(BackupError):
        backup_ops.restore_backup(dest, actor)
    assert Student.select().count() == 5


def test_truncation_detected(env):
    _, actor, tmp = env
    _seed()
    dest = tmp / "b.fanusbak"
    backup_ops.create_backup(dest, actor)
    dest.write_bytes(dest.read_bytes()[:-500])
    with pytest.raises(BackupError):
        backup_ops.inspect_backup(dest)


def test_checksum_mismatch_named(env):
    _, actor, tmp = env
    _seed()
    dest = tmp / "c.fanusbak"
    dest.write_bytes(
        _make_fanusbak({"fanus.db": b"whatever"}, {"files": {"fanus.db": {"sha256": "00" * 32}}})
    )
    with pytest.raises(BackupError):
        backup_ops.restore_backup(dest, actor)
    assert Student.select().count() == 5


def test_zip_slip_rejected(env):
    _, actor, tmp = env
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "format": "fanusbak",
                    "format_version": 1,
                    "fanus_version": "0.0.1",
                    "includes_vault": False,
                    "files": {"../evil.txt": {"sha256": "x"}},
                }
            ),
        )
        zf.writestr("../evil.txt", b"x")
    dest = tmp / "e.fanusbak"
    dest.write_bytes(backup_ops._seal(buf.getvalue()))
    with pytest.raises(BackupError):
        backup_ops.inspect_backup(dest)
    assert not (tmp.parent / "evil.txt").exists()


def test_version_guard(env):
    _, actor, tmp = env
    too_new = tmp / "n.fanusbak"
    too_new.write_bytes(_make_fanusbak({"fanus.db": b"x"}, {"fanus_version": "999.0.0"}))
    with pytest.raises(BackupError):
        backup_ops.inspect_backup(too_new)

    ok = tmp / "o.fanusbak"
    ok.write_bytes(_make_fanusbak({"fanus.db": b"x"}, {"fanus_version": "0.0.1"}))
    assert backup_ops.inspect_backup(ok).includes_vault is False


def test_includes_vault_consistency(env):
    _, actor, tmp = env
    dest = tmp / "x.fanusbak"
    dest.write_bytes(_make_fanusbak({"fanus.db": b"x"}, {"includes_vault": True}))
    with pytest.raises(BackupError):
        backup_ops.inspect_backup(dest)


def test_rollback_on_swap_failure(env, monkeypatch):
    manager, actor, tmp = env
    _seed()
    manager.unlock_vault(DatabaseCredentials.from_vault_pin("1234", tmp / "database_salts.json"))
    dest = tmp / "v.fanusbak"
    backup_ops.create_backup(dest, actor, include_vault=True)
    Student.delete().execute()

    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("boom")
        return real(src, dst)

    monkeypatch.setattr(backup_ops.os, "replace", flaky)
    with pytest.raises(BackupError):
        backup_ops.restore_backup(dest, actor)
    assert not (tmp / ".restore_journal").exists()
    assert not (tmp / ".restore_pending").exists()

    reopened = DatabaseManager(**_paths(tmp))
    reopened.initialize_public()
    try:
        assert Student.select().count() == 0
    finally:
        reopened.close()


def test_stale_wal_removed(env):
    manager, actor, tmp = env
    _seed()
    dest = tmp / "b.fanusbak"
    backup_ops.create_backup(dest, actor)
    Student.delete().execute()

    manager.close()
    (tmp / "fanus.db-wal").write_bytes(b"garbage")
    (tmp / "fanus.db-shm").write_bytes(b"garbage")

    backup_ops.restore_backup(dest, actor)
    assert not (tmp / "fanus.db-wal").exists()
    assert not (tmp / "fanus.db-shm").exists()

    reopened = DatabaseManager(**_paths(tmp))
    reopened.initialize_public()
    try:
        assert Student.select().count() == 5
    finally:
        reopened.close()


def test_restore_requires_admin(env):
    _, actor, tmp = env
    _seed()
    dest = tmp / "b.fanusbak"
    backup_ops.create_backup(dest, actor)
    weak = User.create(
        username="asst",
        full_name="معاون",
        role="assistant",
        can_manage_users=False,
        is_active=True,
    )
    with pytest.raises(BackupError):
        backup_ops.restore_backup(dest, weak)
    assert Student.select().count() == 5


def test_marker_not_left_on_failure(env, monkeypatch):
    manager, actor, tmp = env
    _seed()
    manager.unlock_vault(DatabaseCredentials.from_vault_pin("1234", tmp / "database_salts.json"))
    dest = tmp / "v.fanusbak"
    backup_ops.create_backup(dest, actor, include_vault=True)

    real = os.replace
    calls = {"n": 0}

    def flaky(src, dst):
        calls["n"] += 1
        if calls["n"] == 7:
            raise OSError("boom")
        return real(src, dst)

    monkeypatch.setattr(backup_ops.os, "replace", flaky)
    with pytest.raises(BackupError):
        backup_ops.restore_backup(dest, actor)
    assert not (tmp / ".restore_pending").exists()


def test_heal_interrupted_restore(tmp_path):
    data = tmp_path
    (data / "fanus.db").write_bytes(b"NEW-half")
    (data / "fanus.db.pre-restore").write_bytes(b"ORIGINAL")
    (data / "fanus.db-wal").write_bytes(b"x")
    (data / "counselor_vault.db.incoming").write_bytes(b"leftover")
    (data / ".restore_pending").write_bytes(b"")
    (data / ".restore_journal").write_text(
        json.dumps({"targets": [str(data / "fanus.db"), str(data / "counselor_vault.db")]})
    )

    backup_ops.heal_interrupted_restore(data)

    assert (data / "fanus.db").read_bytes() == b"ORIGINAL"
    assert not (data / "fanus.db.pre-restore").exists()
    assert not (data / "fanus.db-wal").exists()
    assert not (data / "counselor_vault.db.incoming").exists()
    assert not (data / ".restore_pending").exists()
    assert not (data / ".restore_journal").exists()
