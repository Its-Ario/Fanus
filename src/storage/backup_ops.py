"""Full-backup packaging and restore for the ``.fanusbak`` format.

A ``.fanusbak`` file is::

    b"FNSBAK01" || salt(16) || nonce(12) || AES-256-GCM(zip_bytes)

The plaintext is an uncompressed ZIP of ``manifest.json`` + ``fanus.db`` and,
when a counselor opts in, ``counselor_vault.db`` + ``database_salts.json``.

Design and rationale live in ``specs/fanusbak-backup.md``. Key points enforced
here: all validation happens before any live file is touched; the swap is
journalled with ``.pre-restore`` rollback copies; an interrupted swap is rolled
back on next startup by :func:`heal_interrupted_restore`.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import os
import sqlite3
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import jdatetime
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from src.storage.audit import record_audit
from src.storage.db import FANUS_DB_PATH, get_database_manager
from src.utils.get_version import get_version
from src.utils.persian_utils import to_persian_digits

logger = logging.getLogger(__name__)

# Obfuscation key, identical in every install and recoverable from the binary.
# `fanus.db` inside an archive is therefore NOT confidential against anyone
# holding a FANUS build; the counselor vault stays protected by its per-field
# encryption under the counselor PIN. This trade is deliberate — see the spec.
# Derived from a fixed label (not stored as a raw key blob) so it is stable and
# obvious; secrecy is explicitly not a property of this value.
APP_BACKUP_KEY = hashlib.sha256(b"fanus/fanusbak/app-key/v1").digest()
MAGIC = b"FNSBAK01"
_HKDF_INFO = b"fanus/backup/v1"

ALLOWED_ARCHIVE_FILES = {
    "manifest.json",
    "fanus.db",
    "counselor_vault.db",
    "database_salts.json",
}
_VAULT_FILES = {"counselor_vault.db", "database_salts.json"}

_CORRUPT = "بسته پشتیبان آسیب‌دیده یا نامعتبر است."
_TOO_NEW = "این پشتیبان با نسخهٔ جدیدتر فانوس ساخته شده و قابل بازیابی نیست."


class BackupError(RuntimeError):
    """A restore/backup failure with a Persian message safe to show the user."""


@dataclass(frozen=True)
class BackupInfo:
    fanus_version: str
    created_at_fa: str
    school_name: str
    includes_vault: bool


# --------------------------------------------------------------------------- #
# paths & guards                                                             #
# --------------------------------------------------------------------------- #

def _paths():
    manager = get_database_manager()
    fanus = Path(manager.fanus_path)
    data_dir = fanus.parent
    return manager, data_dir, fanus, Path(manager.vault_path), data_dir / "database_salts.json"


def _reload_actor(actor):
    from src.storage.models import User

    try:
        fresh = User.get_or_none(User.id == getattr(actor, "id", None))
    except Exception:  # noqa: BLE001 - a broken query must not mask the guard
        fresh = None
    return fresh or actor


def _require_active(actor):
    fresh = _reload_actor(actor)
    if not getattr(fresh, "is_active", False):
        raise BackupError("حساب شما فعال نیست.")
    return fresh


def _require_admin(actor):
    fresh = _require_active(actor)
    if not getattr(fresh, "can_manage_users", False):
        raise BackupError("برای بازیابی به دسترسی «مدیریت کاربران» نیاز دارید.")
    return fresh


# --------------------------------------------------------------------------- #
# crypto helpers                                                             #
# --------------------------------------------------------------------------- #

def _derive(salt: bytes) -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(), length=32, salt=salt, info=_HKDF_INFO
    ).derive(APP_BACKUP_KEY)


def _seal(plaintext: bytes) -> bytes:
    salt = os.urandom(16)
    nonce = os.urandom(12)
    ciphertext = AESGCM(_derive(salt)).encrypt(nonce, plaintext, None)
    return MAGIC + salt + nonce + ciphertext


def _unseal(raw: bytes) -> bytes:
    if len(raw) < len(MAGIC) + 16 + 12 + 16 or raw[: len(MAGIC)] != MAGIC:
        raise BackupError(_CORRUPT)
    body = raw[len(MAGIC):]
    salt, nonce, ciphertext = body[:16], body[16:28], body[28:]
    try:
        return AESGCM(_derive(salt)).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise BackupError(_CORRUPT) from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------- #
# create                                                                     #
# --------------------------------------------------------------------------- #

def _sqlite_snapshot(src_path: Path, dest_path: Path) -> None:
    """Consistent, WAL-safe copy of a live SQLite file."""
    dest_path.unlink(missing_ok=True)
    src = sqlite3.connect(str(src_path))
    try:
        dst = sqlite3.connect(str(dest_path))
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()


def _build_manifest(members: dict, include_vault: bool) -> dict:
    from src.storage.models import SchoolProfile

    try:
        school = SchoolProfile.get_or_none(id=1)
        school_name = school.school_name if school and school.school_name else ""
    except Exception:  # noqa: BLE001
        logger.warning("Could not read school name for backup manifest", exc_info=True)
        school_name = ""

    now = datetime.now().replace(microsecond=0)
    jnow = jdatetime.datetime.fromgregorian(datetime=now)
    return {
        "format": "fanusbak",
        "format_version": 1,
        "fanus_version": get_version(),
        "created_at_fa": to_persian_digits(jnow.strftime("%Y/%m/%d %H:%M")),
        "created_at_iso": now.isoformat(),
        "school_name": school_name,
        "includes_vault": include_vault,
        "files": {name: {"sha256": _sha256_bytes(data)} for name, data in members.items()},
    }


def create_backup(dest_path, actor, include_vault: bool = False) -> None:
    """Write a ``.fanusbak`` at ``dest_path``. Read-only against the live DBs."""
    _require_active(actor)
    manager, data_dir, fanus, vault, salts = _paths()
    if include_vault and not manager.vault_unlocked:
        raise BackupError("برای گنجاندن گاوصندوق، ابتدا آن را باز کنید.")

    dest_path = Path(dest_path)
    stages = []
    try:
        fanus_stage = data_dir / "fanus.db.bkpstage"
        _sqlite_snapshot(fanus, fanus_stage)
        stages.append(fanus_stage)
        members = {"fanus.db": fanus_stage.read_bytes()}
        if include_vault:
            vault_stage = data_dir / "counselor_vault.db.bkpstage"
            _sqlite_snapshot(vault, vault_stage)
            stages.append(vault_stage)
            members["counselor_vault.db"] = vault_stage.read_bytes()
            members["database_salts.json"] = salts.read_bytes()

        manifest = _build_manifest(members, include_vault)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
            zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            for name, data in members.items():
                zf.writestr(name, data)

        tmp = dest_path.with_name(dest_path.name + ".tmp")
        with open(tmp, "wb") as fh:
            fh.write(_seal(buf.getvalue()))
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, dest_path)
    except BackupError:
        raise
    except OSError as exc:
        raise BackupError("نوشتن فایل پشتیبان ممکن نشد.") from exc
    finally:
        for stage in stages:
            stage.unlink(missing_ok=True)

    record_audit(
        actor, "backup.create", "Backup", None,
        "پشتیبان با گاوصندوق ساخته شد" if include_vault else "پشتیبان بدون گاوصندوق ساخته شد",
    )


# --------------------------------------------------------------------------- #
# inspect                                                                    #
# --------------------------------------------------------------------------- #

def _parse_version(value):
    try:
        return tuple(int(part) for part in str(value).split("."))
    except (TypeError, ValueError):
        return None


def _read_manifest(zf: zipfile.ZipFile) -> dict:
    names = set(zf.namelist())
    if names - ALLOWED_ARCHIVE_FILES:
        raise BackupError("فایل ناشناخته در بسته پشتیبان شناسایی شد.")
    if "manifest.json" not in names:
        raise BackupError(_CORRUPT)
    try:
        manifest = json.loads(zf.read("manifest.json"))
    except ValueError as exc:
        raise BackupError(_CORRUPT) from exc
    if not isinstance(manifest, dict):
        raise BackupError(_CORRUPT)
    if manifest.get("format") != "fanusbak" or manifest.get("format_version") != 1:
        raise BackupError(_TOO_NEW)

    files = manifest.get("files")
    if not isinstance(files, dict) or set(files) != names - {"manifest.json"}:
        raise BackupError(_CORRUPT)

    includes_vault = bool(manifest.get("includes_vault"))
    present_vault = _VAULT_FILES & names
    if includes_vault and present_vault != _VAULT_FILES:
        raise BackupError(_CORRUPT)
    if not includes_vault and present_vault:
        raise BackupError(_CORRUPT)

    backup_v = _parse_version(manifest.get("fanus_version"))
    current_v = _parse_version(get_version())
    if backup_v is None or current_v is None:
        logger.warning(
            "Skipping backup version check: backup=%s current=%s",
            manifest.get("fanus_version"), get_version(),
        )
    elif backup_v > current_v:
        raise BackupError(_TOO_NEW)

    return manifest


def _info(manifest: dict) -> BackupInfo:
    return BackupInfo(
        fanus_version=str(manifest.get("fanus_version", "")),
        created_at_fa=str(manifest.get("created_at_fa", "")),
        school_name=str(manifest.get("school_name", "")),
        includes_vault=bool(manifest.get("includes_vault")),
    )


def inspect_backup(src_path) -> BackupInfo:
    """Decrypt and validate the manifest only. No writes, needs no open DB."""
    blob = _unseal(Path(src_path).read_bytes())
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            return _info(_read_manifest(zf))
    except zipfile.BadZipFile as exc:
        raise BackupError(_CORRUPT) from exc


# --------------------------------------------------------------------------- #
# restore                                                                    #
# --------------------------------------------------------------------------- #

def _close_databases(manager) -> None:
    """Release every OS handle on the live DBs before swapping their files.

    Closes the peewee proxies directly (peewee autoconnect can reopen one after
    ``manager.close()`` thinks it is done) and then the manager for bookkeeping.
    No peewee query may run between here and the file swaps, or it reconnects.
    """
    from src.storage.db import db, set_vault_cipher_key, vault_db

    for proxy in (db, vault_db):
        try:
            if not proxy.is_closed():
                proxy.close()
        except Exception:  # noqa: BLE001 - uninitialised proxy or already gone
            pass
    set_vault_cipher_key(None)
    try:
        manager.close()
    except Exception:  # noqa: BLE001
        logger.exception("Could not close database manager before restore")


def _apply_restore(manager, data_dir: Path, staged: dict, includes_vault: bool) -> None:
    """Journalled swap of every staged ``.incoming`` onto its live file."""
    journal = data_dir / ".restore_journal"
    journal.write_text(
        json.dumps({"targets": [str(p) for p in staged]}), encoding="utf-8"
    )
    done = []  # (live_path, existed_before)
    try:
        _close_databases(manager)

        for live, incoming in staged.items():
            existed = live.exists()
            if existed:
                os.replace(live, live.with_name(live.name + ".pre-restore"))
            os.replace(incoming, live)
            done.append((live, existed))
            for suffix in ("-wal", "-shm"):
                live.with_name(live.name + suffix).unlink(missing_ok=True)

        if includes_vault:
            os.replace(data_dir / ".restore_pending.incoming", data_dir / ".restore_pending")

        journal.unlink(missing_ok=True)
    except Exception as exc:
        for live, existed in done:
            pre = live.with_name(live.name + ".pre-restore")
            if existed and pre.exists():
                os.replace(pre, live)
            elif not existed:
                live.unlink(missing_ok=True)
        journal.unlink(missing_ok=True)
        (data_dir / ".restore_pending.incoming").unlink(missing_ok=True)
        raise BackupError("بازیابی ناتمام ماند؛ داده‌های قبلی بازگردانده شد.") from exc


def _write_restore_audit(actor, includes_vault: bool, fanus_path: Path) -> None:
    """Best-effort audit row into the freshly restored DB (ORM engine is down)."""
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
    details = "بازیابی از نسخهٔ پشتیبان" + (" (با گاوصندوق)" if includes_vault else "")
    try:
        conn = sqlite3.connect(str(fanus_path))
        try:
            conn.execute(
                "INSERT INTO auditlog "
                "(id, created_at, updated_at, actor_id, actor_name, action, "
                " target_entity, target_id, student_id, details) "
                "VALUES (?, ?, ?, ?, ?, 'backup.restore', 'Backup', NULL, NULL, ?)",
                (
                    str(uuid4()), stamp, stamp,
                    str(getattr(actor, "id", "")) or None,
                    getattr(actor, "full_name", "") or "—",
                    details,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:  # noqa: BLE001 - the restore already succeeded
        logger.exception("Could not write restore audit row")


def restore_backup(src_path, actor) -> BackupInfo:
    """Verify a ``.fanusbak`` completely, then swap it in. Caller then quits."""
    _require_admin(actor)
    manager, data_dir, fanus, vault, salts = _paths()
    blob = _unseal(Path(src_path).read_bytes())

    name_to_live = {"fanus.db": fanus, "counselor_vault.db": vault, "database_salts.json": salts}
    staged: dict = {}
    try:
        with zipfile.ZipFile(io.BytesIO(blob)) as zf:
            manifest = _read_manifest(zf)
            includes_vault = bool(manifest["includes_vault"])
            for name, meta in manifest["files"].items():
                content = zf.read(name)
                if _sha256_bytes(content) != meta.get("sha256"):
                    raise BackupError(f"فایل «{name}» در بستهٔ پشتیبان خراب است.")
                live = name_to_live[name]
                incoming = live.with_name(live.name + ".incoming")
                incoming.write_bytes(content)
                staged[live] = incoming
        if includes_vault:
            (data_dir / ".restore_pending.incoming").write_bytes(b"")

        _apply_restore(manager, data_dir, staged, includes_vault)
    except BackupError:
        for incoming in staged.values():
            incoming.unlink(missing_ok=True)
        (data_dir / ".restore_pending.incoming").unlink(missing_ok=True)
        raise
    except (zipfile.BadZipFile, OSError) as exc:
        for incoming in staged.values():
            incoming.unlink(missing_ok=True)
        (data_dir / ".restore_pending.incoming").unlink(missing_ok=True)
        raise BackupError(_CORRUPT) from exc

    _write_restore_audit(actor, includes_vault, fanus)
    return _info(manifest)


def heal_interrupted_restore(data_dir=None) -> None:
    """Roll an interrupted restore back to its ``.pre-restore`` state.

    Called from startup before any database is opened. If the journal exists the
    restore is never trusted — always roll back; the user re-runs Restore.
    """
    if data_dir is None:
        try:
            data_dir = Path(get_database_manager().fanus_path).parent
        except Exception:  # noqa: BLE001 - manager not configured yet at startup
            data_dir = FANUS_DB_PATH.parent
    data_dir = Path(data_dir)

    journal = data_dir / ".restore_journal"
    if not journal.exists():
        return
    try:
        targets = json.loads(journal.read_text(encoding="utf-8")).get("targets", [])
    except (ValueError, OSError):
        targets = []

    for raw in targets:
        target = Path(raw)
        pre = target.with_name(target.name + ".pre-restore")
        if pre.exists():
            os.replace(pre, target)
        for suffix in ("-wal", "-shm"):
            target.with_name(target.name + suffix).unlink(missing_ok=True)
        target.with_name(target.name + ".incoming").unlink(missing_ok=True)

    for stray in (".restore_pending", ".restore_pending.incoming"):
        (data_dir / stray).unlink(missing_ok=True)
    journal.unlink(missing_ok=True)
    logger.warning("Rolled back an interrupted restore on startup")
