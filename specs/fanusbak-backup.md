# Spec — `.fanusbak` Full Backup & Restore

Status: agreed design. Ready to turn into an implementation plan.

## Context

FANUS is an offline-first PyQt5 desktop app (Python 3.8, Peewee + SQLite WAL, `peewee-migrate`,
separate AES-256-GCM vault DB for confidential counselor notes, RTL Persian UI). This spec adds
the full-backup capability that `settings-area.md` deferred: a single portable, integrity-checked
file for migrating to a new laptop, carrying school data home on a USB stick, or recovering from
a dead disk.

The unit of backup is **the databases**, not a CSV export — relational links, UUIDs, indexes and
historical timestamps must survive intact.

## Goals

- One-click creation of a `.fanusbak` file containing a clean, consistent snapshot of `fanus.db`
  (and optionally the counselor vault).
- One-click restore that verifies the file completely **before** touching live data, and never
  leaves the app in a half-restored state.
- Portable across machines with no per-file passphrase prompt.

## Non-goals (deferred, not this build)

Scheduled / automatic backups · cloud sync · differential or incremental backups · selective
table / record restore · restoring into a running session without an app restart · moving backup
or restore work to a worker thread · registering the `.fanusbak` extension with Windows.

## Pre-existing conditions this spec must work around

- **SQLite runs in WAL mode.** A raw file copy of `fanus.db` while the app is open can capture a
  torn state, and a stale `fanus.db-wal` next to a freshly restored DB gets replayed on next open
  and corrupts it. Snapshots use `sqlite3`'s online backup API; restore deletes `-wal` / `-shm`
  next to every swapped DB.
- **Windows file locks.** `os.replace()` over `fanus.db` fails with `WinError 32` while Peewee
  holds an open connection. Restore closes **both** `db` and `vault_db` before any swap.
- **The vault integrity anchor is machine + user bound and lives outside the DB**
  (`%LOCALAPPDATA%/Fanus/vault-anchors/<id>/.vault_anchor`, DPAPI-protected). On a new machine it
  does not exist, and `unlock_vault()` currently fails closed ("anchor missing"). Restore must let
  the anchor be rebuilt on the next unlock — see §5.
- **The vault key is derived from the counselor PIN + a salt in `data/database_salts.json`.** That
  salt file must travel in any backup that includes the vault, or the PIN can never re-derive the
  key on another machine.
- **The vault is normally never unlocked.** Only Settings → Security unlocks it on demand. A
  backup can only *include* the vault when it is currently unlocked in that session.
- **`peewee-migrate` records applied migrations in a `migratehistory` table inside each DB.**
  Schema identity therefore travels inside the `.db` files; no schema-version field is needed in
  the manifest.

---

## 1. File format

```
my_school_backup_1403_08_25.fanusbak
└── <8-byte magic "FNSBAK01"> || <16-byte salt> || <12-byte nonce> || <AES-256-GCM ciphertext>

ciphertext, once decrypted, is an uncompressed ZIP:
├── manifest.json
├── fanus.db
├── counselor_vault.db      (only when the counselor opted in)
└── database_salts.json     (only when the counselor opted in)
```

- **Encryption key:** a fixed 32-byte constant `APP_BACKUP_KEY` embedded in the app, identical for
  every install, no prompt. `key = HKDF-SHA256(APP_BACKUP_KEY, salt=salt, info=b"fanus/backup/v1",
  length=32)`; `nonce = os.urandom(12)`; `AESGCM(key).encrypt(nonce, zip_bytes, None)`.
- **Integrity:** the GCM auth tag authenticates every byte of the archive under `APP_BACKUP_KEY` —
  this is the tamper / truncation check. The per-file SHA-256 in the manifest is a **second**,
  narrower check that survives GCM: it tells restore *which* file a bad USB corrupted, and guards
  the post-decrypt extraction. There is no separate manifest HMAC (it would be redundant).
- **Security posture — deliberate and documented.** Because `APP_BACKUP_KEY` ships in the binary
  (`strings` recovers it), `fanus.db` inside the archive is **obfuscated, not confidential**
  against anyone holding a FANUS build plus the file: student records, grades, attendance and the
  audit log are readable. This is an accepted trade for "no prompt", consistent with the existing
  `config.py` `HMAC_SECRET`. The counselor vault stays genuinely protected: its contents are
  per-field AES-256-GCM under the counselor PIN. Caveat: a backup that also carries
  `database_salts.json` makes a short numeric PIN offline-brute-forceable — the counselor opts
  into that explicitly.
- **`zipfile` uses `ZIP_STORED`** (`.db` files barely compress; keeps it simple and fast).
  `ponytail:` switch to `ZIP_DEFLATED` only if archive size is complained about.

### 1.1 `manifest.json`

```json
{
  "format": "fanusbak",
  "format_version": 1,
  "fanus_version": "1.2.0",
  "created_at_fa": "۱۴۰۳/۰۸/۲۵ ۱۴:۳۰",
  "created_at_iso": "2025-11-15T14:30:00",
  "school_name": "…",
  "includes_vault": true,
  "files": {
    "fanus.db":            { "sha256": "…" },
    "counselor_vault.db":  { "sha256": "…" },
    "database_salts.json": { "sha256": "…" }
  }
}
```

`fanus_version` drives only the friendly compatibility check (§6). `created_at_fa` is display-only;
`created_at_iso` is the machine-comparable stamp.

---

## 2. Module & API — new `src/storage/backup_ops.py`

Module-level functions, matching the `settings_ops.py` / `audit.py` style (no class).

```python
APP_BACKUP_KEY = bytes.fromhex("…")            # 32-byte embedded constant
MAGIC = b"FNSBAK01"
ALLOWED_ARCHIVE_FILES = {"manifest.json", "fanus.db",
                         "counselor_vault.db", "database_salts.json"}

class BackupError(RuntimeError):
    """Human-readable (Persian) failure surfaced to the backup panel."""

@dataclass(frozen=True)
class BackupInfo:
    fanus_version: str
    created_at_fa: str
    school_name: str
    includes_vault: bool

def create_backup(dest_path: Path, actor, include_vault: bool = False) -> None
def inspect_backup(src_path: Path) -> BackupInfo          # decrypt + parse manifest only, no writes
def restore_backup(src_path: Path, actor) -> BackupInfo   # verify + stage + swap; caller then quits
def heal_interrupted_restore(data_dir: Path) -> None      # startup self-heal, see §5.3
```

**Guards** (on a freshly loaded `User.get_by_id(actor.id)`, mirroring `settings_ops`):

- `create_backup` — actor must exist and be `is_active`.
- `restore_backup` — actor must be `is_active` **and** `can_manage_users`.
- `include_vault=True` — asserts `get_database_manager().vault_unlocked`; raises `BackupError`
  otherwise (the panel already only offers the checkbox when unlocked; this is the backstop).

Paths come from `src.storage.db` (`FANUS_DB_PATH`, `VAULT_DB_PATH`, `KEY_SALTS_PATH`, and their
parent `DATA_DIR`). No new constants invented here.

---

## 3. Create flow (`create_backup`)

1. Guard actor. Resolve `include_vault`; if true, assert the vault is unlocked.
2. **Snapshot** into temp files under `DATA_DIR` (`*.bkpstage`):
   - `fanus.db`: `sqlite3.connect(FANUS_DB_PATH).backup(sqlite3.connect(stage))`, both closed.
   - if `include_vault`: same for `counselor_vault.db`.
   - if `include_vault`: copy `database_salts.json` bytes directly (plain JSON, not a DB).
3. SHA-256 each staged file.
4. Build `manifest.json` — `school_name` from `SchoolProfile.get_or_none(id=1)` (fallback
   `""` + log), `fanus_version` from `get_version()`, `created_at_fa` from `persian_utils`,
   `created_at_iso` from `datetime.now()`.
5. `zipfile.ZipFile(BytesIO(), "w", ZIP_STORED)` — write `manifest.json` first, then each file.
6. `salt = os.urandom(16)`; `key = HKDF(...)`; `nonce = os.urandom(12)`;
   `ct = AESGCM(key).encrypt(nonce, buf.getvalue(), None)`.
7. Atomic write: `dest_path.with_suffix(dest_path.suffix + ".tmp")` ← `MAGIC + salt + nonce + ct`,
   `f.flush()` + `os.fsync()`, then `os.replace()` to `dest_path`.
8. `finally`: delete every `*.bkpstage` temp.
9. `record_audit(actor, "backup.create", "Backup", None,
   "پشتیبان با گاوصندوق ساخته شد" / "پشتیبان بدون گاوصندوق ساخته شد")`.

Read-only against the live DBs — no `manager.transaction()`. Runs synchronously behind a busy
modal (a few MB, sub-second). `ponytail:` move to a `QThread` only if it proves janky — the same
call `settings-area.md` made for vault re-encryption.

---

## 4. Restore flow (`restore_backup`)

The panel has already called `inspect_backup` and shown a confirm dialog (school name, date,
`includes_vault`, a red "current data will be replaced" warning, and an acknowledge checkbox).

**Pre-mutation — no side effects, any failure just raises `BackupError`:**

1. Guard: `is_active` + `can_manage_users` on a fresh `User.get_by_id(actor.id)`.
2. Read file; check `MAGIC`; split `salt` / `nonce` / `ct`. `key = HKDF(...)`.
   `AESGCM(key).decrypt(nonce, ct, None)` → zip bytes. Any failure (bad magic, wrong length,
   `InvalidTag`) → `BackupError("بسته پشتیبان آسیب‌دیده یا نامعتبر است.")`. This one message covers
   truncation, tampering, and a file made by a build with a different key.
3. `zipfile.ZipFile(BytesIO(zip_bytes))`. **Zip-slip guard:** every `zf.namelist()` entry must be
   in `ALLOWED_ARCHIVE_FILES`, else `BackupError("فایل ناشناخته در بسته پشتیبان.")`. Read members
   by exact name with `zf.read(name)` — never `extractall`.
4. Parse `manifest.json`: `format == "fanusbak"`; `format_version == 1` (`> 1` →
   `BackupError("ساخته‌شده با نسخهٔ جدیدتر فانوس.")`); version compat (§6).
5. Consistency: `manifest["includes_vault"]` is true **iff** both `counselor_vault.db` and
   `database_salts.json` are present in the zip. Mismatch → `BackupError`.
6. **Stage** every archived file to `DATA_DIR/<name>.incoming`; verify each file's SHA-256 against
   the manifest — mismatch → `BackupError` naming the file (bad-USB bit-rot inside an otherwise
   valid GCM archive). If `includes_vault`, also create the empty marker
   `DATA_DIR/.restore_pending.incoming`.

**Mutation — journalled, rollback-on-failure:**

7. Write `DATA_DIR/.restore_journal` = `{"targets": [<abs paths about to be swapped>]}`
   (`fanus.db`; plus `counselor_vault.db` + `database_salts.json` when `includes_vault`).
8. Close DB engines: `db.close()` / `vault_db.close()` if open; `set_vault_cipher_key(None)`.
   Releases Windows file locks.
9. Per target, in journal order:
   - `os.replace(live, live.with_name(live.name + ".pre-restore"))` if `live` exists.
   - `os.replace(live.with_name(live.name + ".incoming"), live)`.
   - `unlink(missing_ok=True)` on `live + "-wal"` and `live + "-shm"`.
10. If `includes_vault`: `os.replace(".restore_pending.incoming", ".restore_pending")` — the
    anchor-reinit marker activates as part of the same swap sequence.
11. Delete `.restore_journal`.
12. **Audit:** raw `sqlite3.connect(FANUS_DB_PATH)` — one `INSERT` of a `backup.restore` `AuditLog`
    row into the *restored* DB (actor name, timestamp), then close. The ORM engine stays down; the
    schema is known. Failure here is swallowed + logged — the restore itself already succeeded.
13. Return `BackupInfo`. The panel shows "بازیابی کامل شد. برنامه بسته می‌شود؛ دوباره باز کنید."
    then calls `QApplication.quit()`. `.pre-restore` files are left in place as a manual safety net
    (a subsequent restore overwrites them, so at most one generation accumulates).

**Rollback:** any exception during step 9 → move every existing `.pre-restore` back over its target,
delete `.restore_journal` and any staged markers, then re-raise as
`BackupError("بازیابی ناتمام ماند؛ داده‌های قبلی بازگردانده شد.")`.

---

## 5. Vault integrity anchor after restore

### 5.1 The marker

Restore that replaced the vault DB leaves `DATA_DIR/.restore_pending` (activated atomically in
step 10). A restore that did **not** carry a vault never writes it — the local vault, its salts and
its anchor are untouched and stay mutually consistent.

### 5.2 `db.py` change — the only edit to existing storage code

At the top of `DatabaseManager._verify_or_initialize_vault_anchor`:

```python
restore_marker = self.vault_path.with_name(".restore_pending")
if restore_marker.exists():
    if self.state_anchor.available:
        self.state_anchor.path.unlink(missing_ok=True)   # stale / foreign machine anchor
    self.state_anchor.store(0, self._vault_state_commitment())
    self._vault_generation = 0
    restore_marker.unlink()
    logger.info("Re-anchored confidential vault after restore")
    return
```

Fires on the first `unlock_vault()` after a restore: the counselor enters their PIN in Settings →
Security, the key is set, `_vault_state_commitment()` is computable, and a fresh anchor bound to
*this* machine is written.

**Accepted gap:** that single first unlock cannot detect a vault DB tampered with in transit. The
`.fanusbak` GCM tag already authenticates the whole archive on restore, so the residual exposure
is "plaintext vault DB altered on disk after a legitimate restore but before the first unlock" —
negligible for this threat model.

### 5.3 Self-healing startup — `heal_interrupted_restore(data_dir)`

Called from `main.py` **before** `configure_database_manager()` (nothing has opened a DB yet):

```python
journal = data_dir / ".restore_journal"
if not journal.exists():
    return
for raw in json.loads(journal.read_text(encoding="utf-8"))["targets"]:
    target = Path(raw)
    pre = target.with_name(target.name + ".pre-restore")
    if pre.exists():
        os.replace(pre, target)                       # deterministic: back to pre-restore state
    for suffix in ("-wal", "-shm"):
        target.with_name(target.name + suffix).unlink(missing_ok=True)
    target.with_name(target.name + ".incoming").unlink(missing_ok=True)
for stray in (".restore_pending", ".restore_pending.incoming"):
    data_dir.joinpath(stray).unlink(missing_ok=True)
journal.unlink()
logger.warning("Rolled back an interrupted restore on startup")
```

**Rule: if `.restore_journal` exists at startup, always roll back.** A partly-applied restore is
never trusted; `.pre-restore` is the user's known-good original. The user simply re-runs Restore.
No "did it finish?" heuristic, no roll-forward path. The one tiny window — last target swapped,
power lost before `journal.unlink()` — costs the user a re-run, never data.

---

## 6. Version compatibility

- **Newer → older** (`manifest["fanus_version"]` parses to a higher int-tuple than `get_version()`):
  refuse — `BackupError("این پشتیبان با نسخهٔ جدیدتر فانوس ساخته شده و قابل بازیابی نیست.")`.
- **Unparseable version** on either side: log a warning and allow.
- **Older → newer** and **equal**: allowed. On the post-restore restart, `_migrate_public` /
  `_migrate_vault` run any pending migrations forward on the restored files (migration head travels
  inside each `.db`).
- **Partial restore: not supported.** Restore replaces exactly the files the archive contains and
  nothing else.

---

## 7. Failure matrix

| Failure point | On-disk state | User sees | Recovery |
|---|---|---|---|
| Create: snapshot / zip / encrypt fails | no `.fanusbak` (atomic `.tmp` → `replace` only on full success); temps cleaned in `finally` | `BackupError` | none needed |
| Restore steps 1–6 (guard, decrypt, allowlist, manifest, consistency, checksum) | nothing touched | `BackupError` naming the cause | retry with a good file |
| Restore step 9, mid-swap (exception) | some `.pre-restore` copies exist | `BackupError("بازیابی ناتمام ماند…")` | automatic: every `.pre-restore` moved back before the error propagates |
| Crash / power-loss anywhere in steps 7–11 | half-swapped set + stray `.incoming` / `.pre-restore` / journal | next launch: nothing (heal runs first) | automatic: `heal_interrupted_restore` rolls every target back to `.pre-restore`, clears `-wal` / `-shm` / `.incoming` / markers, deletes journal |
| Audit `INSERT` fails (step 12) | DBs swapped fine | success dialog | swallowed + logged — restore already succeeded |
| `include_vault` requested but vault locked | no backup made | `BackupError` (panel shouldn't allow it) | unlock the vault, retry |

**Guiding rule:** all validation before any mutation; mutation is journalled swap-with-rollback-copy;
nothing partial is ever reported as success.

---

## 8. UI — new `src/views/pages/settings/backup_panel.py`

A 5th entry in the Settings rail, "پشتیبان‌گیری و بازیابی", visible to every user. Follows the rail /
nested-stack pattern already in `settings_page.py`; reuses `PrimaryButton`, `SecondaryButton`,
`FormField`, `Card` from `ui_kit.py`.

### 8.1 Create section — all users

- `PrimaryButton` "ساخت نسخهٔ پشتیبان" → `QFileDialog.getSaveFileName`, default file name
  `<school>_backup_<jalali>.fanusbak` (school slug from `SchoolProfile`, date from `persian_utils`),
  filter `فایل پشتیبان فانوس (*.fanusbak)`.
- If `actor.role == "counselor"` **and** `get_database_manager().vault_unlocked`: a
  `[ ] گنجاندن گاوصندوق محرمانه` checkbox above the button.
- If `actor.role == "counselor"` and the vault is **locked**: a slim hint —
  «برای گنجاندن گاوصندوق، ابتدا آن را در بخش «امنیت» باز کنید».
- On click → busy modal → `create_backup(path, actor, include_vault)` → success toast /
  `BackupError` message box.

### 8.2 Restore section — `can_manage_users` only (hidden entirely otherwise)

- `SecondaryButton` "بازیابی از نسخهٔ پشتیبان" → `QFileDialog.getOpenFileName` (`*.fanusbak`).
- `inspect_backup(path)` → confirm dialog: school name, `created_at_fa`, "شامل گاوصندوق: بله/خیر",
  a red warning that all current data will be replaced, and a required acknowledge checkbox.
- Confirmed → busy modal → `restore_backup(path, actor)` → info dialog
  «بازیابی کامل شد. برنامه بسته می‌شود؛ لطفاً دوباره باز کنید.» → `QApplication.quit()`.
- `BackupError` anywhere → message box with its Persian text; nothing has changed.

### 8.3 Audit action labels

Add to the `ACTION_LABELS` dict in `security_panel.py` (viewer-only):
`"backup.create": "ساخت نسخهٔ پشتیبان"`, `"backup.restore": "بازیابی از نسخهٔ پشتیبان"`.

---

## 9. Touch list

- **new** `src/storage/backup_ops.py` — `create_backup`, `inspect_backup`, `restore_backup`,
  `heal_interrupted_restore`, `BackupInfo`, `BackupError`, `APP_BACKUP_KEY`, `MAGIC`,
  `ALLOWED_ARCHIVE_FILES`.
- **edit** `src/storage/db.py` — `.restore_pending` branch at the top of
  `_verify_or_initialize_vault_anchor` (~10 lines).
- **edit** `main.py` — `backup_ops.heal_interrupted_restore(DATA_DIR)` before
  `configure_database_manager()`.
- **new** `src/views/pages/settings/backup_panel.py` — the panel.
- **edit** `src/views/pages/settings/settings_page.py` — register the 5th rail entry.
- **edit** `src/views/pages/settings/security_panel.py` — two new `ACTION_LABELS` entries.
- **new** `tests/test_backup.py`.
- **edit** `specs/settings-area.md` — remove "encrypted backup & restore" from the deferred /
  non-goals list.

---

## 10. Test plan — `tests/test_backup.py`

pytest, `tmp_path`, real SQLite files (no mocking of crypto or the swap):

1. **Round-trip, public-only** — seed `fanus.db`, `create_backup(include_vault=False)`, wipe,
   `restore_backup`, assert row counts + a sample record; assert `counselor_vault.db` untouched.
2. **Round-trip, with vault** — vault unlocked, `include_vault=True`; after restore assert
   `.restore_pending` exists, drive one `unlock_vault`, assert anchor re-created + marker gone +
   a `CounselorNote` decrypts.
3. **Tamper** — flip one ciphertext byte → `restore_backup` raises `BackupError`, live DBs
   untouched.
4. **Truncation** — drop the last 500 bytes → `BackupError`, untouched.
5. **Checksum mismatch** — hand-built archive whose manifest hash is wrong → `BackupError` naming
   the file, untouched.
6. **Zip-slip** — hand-built archive with a `../evil.txt` member → `BackupError`, nothing written
   outside `DATA_DIR`.
7. **Version guard** — manifest `fanus_version` above `get_version()` → refuse; below → allowed.
8. **`includes_vault` consistency** — manifest says vault, zip has no `counselor_vault.db` →
   `BackupError`.
9. **Rollback** — monkeypatch `os.replace` to raise on the 2nd target → every `.pre-restore`
   restored, `BackupError` raised.
10. **WAL ghost** — leave a stale `fanus.db-wal` before restore → gone afterward, restored data
    intact.
11. **Access guard** — `restore_backup` with a non-`can_manage_users` actor → `BackupError`,
    nothing touched.
12. **`db.py` anchor branch** — marker present + stale foreign anchor file → after
    `_verify_or_initialize_vault_anchor`, anchor rewritten from current state, marker consumed.
    (Lives near the existing db tests.)
13. **Interrupted-restore heal** — hand-write a `.restore_journal` + `.pre-restore` + half-swapped
    state, call `heal_interrupted_restore`, assert every target back to pre-restore content;
    journal / markers / WAL ghosts gone.
14. **Marker atomicity** — monkeypatch `os.replace` to raise right after the `.db` swaps but
    before the marker swap → rollback leaves no `.restore_pending`.

Not covered (accepted): real power-loss mid-swap (matrix row 4 — heal is automatic, but the
physical event isn't unit-testable), `QThread` behaviour (not threaded in this build).
