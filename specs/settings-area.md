# Spec — Settings Area (Administrative & Structural Setup)

Status: agreed design + Codex review folded in. **One open decision remains** — see §7.2
(password reset). Everything else is ready to implement.

## Context

FANUS is an offline-first PyQt5 desktop app (Python 3.8, Peewee + SQLite WAL, peewee-migrate,
separate AES-256-GCM vault DB for confidential counselor notes, RTL Persian UI). Settings is a
new primary destination reached from the existing `⚙️ تنظیمات` sidebar item, currently
`print("TODO")` in `main_window._setup_navigation`.

Four tabs: عمومی و اطلاعات مدرسه · مدیریت کلاس‌ها و پایه‌ها · مدیریت کاربران و دسترسی‌ها · امنیت و گاوصندوق.

## Goals

- In-app CRUD for the structural data the app runs on: school name, classes, users.
- Self-service login-password change for every user; vault-PIN rotation for counselors.
- An audit trail of structural changes, viewable by administrators.

## Non-goals (deferred, not this build)

Year rollover / grade promotion / class archiving · export ·
CSV import · custom/editable major list · moving vault re-encryption to a worker thread.

## Pre-existing conditions this spec must work around

- **The vault is never unlocked after first run.** `main.py` normal startup calls only
  `initialize_public()`; it never derives credentials or calls `unlock_vault()`. Anything in
  Settings that touches `CounselorNote` must unlock the vault itself first (see §8.2).
- **`seed.py` is stale/broken** (`User.age`, `StudyPlan.subject` don't exist) and creates **no
  classrooms**. There is no 25-row class seed; migrations must not assume one.
- **There are no executable migrations yet** — `src/storage/migrations/fanus/` holds only a
  README. `_migrate_public` runs `Router(...).run()` then `create_tables` for a fresh DB, so an
  existing DB needs a hand-authored migration file.
- **Passwordless accounts log in with no prompt**: `login_dialog.py` does
  `if not user.password_hash: self._authenticate(user)`. Nulling a hash = removing auth.
- **Non-counselor first-run makes a throwaway vault PIN** (`first_run_wizard.py`), so on such
  installs the vault DB can never be reopened. Tab 4's vault section is counselor-only, which
  sidesteps this — do not expose vault operations to non-counselors.

---

## 1. Shell & integration

- New `SettingsPage(QWidget)` added to `MainWindow`'s `QStackedWidget` at a new index; the
  `⚙️ تنظیمات` nav item switches to it. `current_user` passed to the constructor.
- Layout: a right-anchored `QListWidget` rail selecting a nested `QStackedWidget` of four panel
  widgets. Not `QTabWidget` (its RTL tab strip fights the app's custom QSS).
- All four rail entries visible to every user.
- Files:

  ```
  src/views/pages/settings/
  ├── __init__.py
  ├── settings_page.py     # shell + rail + nested stack
  ├── school_panel.py      # Tab 1
  ├── classes_panel.py     # Tab 2
  ├── users_panel.py       # Tab 3
  ├── security_panel.py    # Tab 4
  └── dialogs.py           # ClassDialog, UserDialog, PasswordChangeDialog, VaultPinDialog
  ```

- Reused: `FormField`, `PrimaryButton`, `SecondaryButton`, `SearchInput`, `EmptyState`, `Card`
  from `ui_kit.py`; the `QTableView` styling from `students_page.py`.

## 2. Access & authorization

| User | Tabs 1–3 | Tab 4 vault section | Tab 4 password | Tab 4 audit log |
|---|---|---|---|---|
| `can_manage_users` | edit | hidden unless also counselor | yes | yes |
| `role == "counselor"` (no admin) | read-only | edit | yes | hidden |
| other | read-only | hidden | yes | hidden |

Read-only panels (1–3): data shown, inputs `setEnabled(False)`, action column + Add button +
empty-state CTA hidden, and a slim neutral info bar on top:

> برای ویرایش تنظیمات به دسترسی «مدیریت کاربران» نیاز دارید.

**UI enablement is presentation only.** Every settings mutation goes through a single guarded
mutation function in the storage layer — new `src/storage/settings_ops.py` — which, inside the
mutation's `manager.transaction()`:

1. reloads the acting user fresh (`User.get_by_id(actor.id)`),
2. asserts `is_active` and the capability the operation needs (`can_manage_users`, or
   `role == "counselor"` for vault ops),
3. applies self-target restrictions (§7.3),
4. performs the write and the audit row.

A stray slot, keyboard path, or direct model call cannot skip it. This is one helper, not a
general authorization framework.

## 3. Save semantics

- **Tab 1** is the only tab with a hybrid Save/Cancel footer: dirty-tracked, prompt on
  navigate-away-while-dirty («تغییرات ذخیره‌نشده دارید»).
- **Tabs 2 & 3** are list + modal: each dialog commits immediately on save (mirrors
  `students_page.NewStudentDialog`).
- **Tab 4** is button→dialog driven: no footer, no dirty-tracking.

## 4. Audit

- New `src/storage/audit.py` → `record_audit(actor, action, entity, target_id=None, details=None)`.
  Writes one `AuditLog` row: `actor_name=actor.full_name` (a mutable-string snapshot — accepted
  for this build), `action`, `target_entity=entity`, `target_id`, `details`.
- `AuditLog.target_id` is `UUIDField(null=True)`. `SchoolProfile.id` is the integer `1`, so
  `school.update` passes `target_id=None` and puts the identifier in `details`.
- **Cross-DB atomicity**: `AuditLog` lives in `fanus.db`, `CounselorNote` in `vault_db`, and
  `manager.transaction()` binds exactly one database. For vault operations (`vault.pin_change`),
  the vault write and the audit row **cannot** be one atomic unit. Order: complete and verify
  the vault operation first, then write the audit row in a separate public transaction. A
  crash in the gap leaves a rotated PIN with no audit row — acceptable, and preferable to the
  reverse.
- For all public-DB mutations, `record_audit` runs inside the same transaction as the mutation
  and rolls back with it.
- `details` is a short Persian string, e.g. «کلاس «دهم - ۱۰۱» ایجاد شد».
- Actions (stored ASCII): `school.update` · `class.create` · `class.update` · `class.delete` ·
  `user.create` · `user.update` · `user.role_change` · `user.activate` · `user.deactivate` ·
  `user.password_reset` · `vault.pin_change` · `password.self_change`.
- Persian display labels live in a local dict in `security_panel.py`, viewer-only.

---

## 5. Tab 1 — عمومی و اطلاعات مدرسه

`SchoolProfile` is a singleton (`id=1`). **Do not** load it via `get_instance()` — that
`get_or_create` silently inserts an incomplete row. Use `SchoolProfile.get_or_none(id=1)`;
if it's `None` the app isn't set up and Settings shouldn't be reachable anyway.

`type` is a comma-joined string of level keys, written by `first_run_wizard._complete_setup`.
**Parse it defensively** (used here and in §6.3):

```python
def parse_levels(raw: str) -> list[str]:
    valid = ("elementry", "middle", "high")  # note: repo misspells "elementary"
    seen = [t.strip() for t in (raw or "").split(",")]
    return [t for i, t in enumerate(seen) if t in valid and t not in seen[:i]]
```

Empty / all-unrecognized → treat as `["high"]` (the common case) and log a warning.

**Layout:**

1. Read-only summary card: `نام مدرسه`, `سال تحصیلی`, `مقاطع` (Persian labels for parsed
   levels), counts — `کلاس‌ها` = all `Classroom` rows · `دانش‌آموزان` = `Student.is_active`
   count · `کاربران` = active `User` count.
2. One editable field `نام مدرسه` (`school_name`) + Save/Cancel footer.

`academic_year` and `type` are **display-only** this build.

**Save** (via `settings_ops`, `can_manage_users` required): validate
`2 < len(school_name) < 50`; fetch `id=1`, set, save; `record_audit(user, "school.update",
"SchoolProfile", None, "نام مدرسه به «…» تغییر کرد")`.

## 6. Tab 2 — مدیریت کلاس‌ها و پایه‌ها

### 6.1 Schema change — model layer **and** one migration file

`Classroom` today: `name`, `grade_level` (int, default 10), `major` (str), `academic_year`
(str). `Student.classroom` is `ForeignKeyField(..., on_delete="CASCADE")`.

**In `src/storage/models.py`** (so fresh DBs and `_verify_schema` stay in sync):

- add `code = CharField(max_length=30)`
- add `class Meta: indexes = ((("grade_level", "major", "code", "academic_year"), True),)`
- update `AcademicMajor` constants to the new stored values (table below)
- change `Student.major` / `Classroom.major` field defaults to `"عمومی/معارف"`
- add a `Classroom.compose_name()` returning the display string (§6.3) and call it from a
  `save()` override

**In a new hand-authored migration `src/storage/migrations/fanus/001_settings_structural.py`**,
in this exact order:

1. `ADD COLUMN code` (nullable), then `UPDATE classroom SET code = name`.
2. **Relabel `major` first** (recompose in step 4 reads it):

   | old | new |
   |---|---|
   | `ریاضی فیزیک` | `ریاضی فیزیک` (unchanged) |
   | `تجربی` | `علوم تجربی` |
   | `علوم انسانی` | `علوم انسانی` (unchanged) |
   | `فنی و حرفه ای` | `فنی و حرفه‌ای` (ZWNJ `‌`, not a space) |
   | `عمومی` | `عمومی/معارف` |

   Apply to **both** `student.major` and `classroom.major`. All mappings are 1:1, no
   collisions. `Student.major` snapshots are relabeled too — it's a pure label change,
   historical meaning is unchanged, and leaving them stale would break major-based filters.
3. **Detect duplicates before the unique index**: `SELECT grade_level, major, code,
   academic_year, COUNT(*) ... GROUP BY 1,2,3,4 HAVING COUNT(*) > 1`. If any, abort the
   migration with a clear message naming the offending classes (there is no seed to collide,
   so on a clean dev DB this is a no-op; a real deployment gets told what to fix).
4. `UPDATE classroom SET name = <recomposed>` per row (§6.3 format).
5. `CREATE UNIQUE INDEX` on `(grade_level, major, code, academic_year)`.

Write an upgrade + restore test for this migration.

### 6.2 Classes list

- Single `QTableView`, **no pagination**. Reuses `students_page` table styling + `EmptyState`.
- Columns: `نام کلاس` · `پایه` · `رشته` · `تعداد دانش‌آموز` (active only) · action column
  (✏️ edit, 🗑️ delete) — action column visible only with `can_manage_users`.
- Sorted by `grade_level` then `name`. Empty-state CTA «کلاس جدید» hidden for non-admins.

### 6.3 `ClassDialog(instance=None)`

| Field | Widget | Rules |
|---|---|---|
| `پایه تحصیلی` | dropdown | strictly the grade set from `parse_levels(SchoolProfile.type)`: high→10/11/12, middle→7/8/9, elementry→1..6, multi→union. Stored as `grade_level` int. |
| `رشته تحصیلی` | dropdown | the 5 `AcademicMajor` values. For `grade_level < 10` forced to `عمومی/معارف` and disabled. |
| `عنوان/کد کلاس` | text | free text, required; digits normalized to Persian on save (`to_persian_digits`). |

`name` is auto-composed and **stored** on `save()` via `compose_name()`:

```
«{grade_ordinal_fa} {رشته} - {کد}»      e.g. «دهم علوم تجربی - ۱۰۱»
«{grade_ordinal_fa} - {کد}»             when رشته == "عمومی/معارف"  → «هفتم - ۱۰۱»
```

Ordinal map: 1 اول · 2 دوم · 3 سوم · 4 چهارم · 5 پنجم · 6 ششم · 7 هفتم · 8 هشتم · 9 نهم ·
10 دهم · 11 یازدهم · 12 دوازدهم.

**Uniqueness:** reject duplicate `(grade_level, major, code, academic_year)` — inline error,
backed by the DB unique index (catch `IntegrityError` like `NewStudentDialog`).

**`academic_year`:** auto from `SchoolProfile` `id=1`, read-only.

**Editing a class with ≥1 active student** — guard query
`Student.select().where((Student.classroom == room) & Student.is_active).exists()`: `پایه` and
`رشته` disabled (inline note); `کد` editable, `name` recomposes from locked grade/major.

`Student.major` is snapshot-copied at student creation and is **not** propagated on a class
major change.

### 6.4 Delete

- Blocked while `Student.select().where((Student.classroom == room) & Student.is_active).exists()`
  — show the active count, tell the user to move/deactivate students first. This guard is why
  the `CASCADE` never silently fires.
- Empty: plain confirm → delete via `settings_ops` + `record_audit(user, "class.delete",
  "Classroom", room.id, "…")`.

## 7. Tab 3 — مدیریت کاربران و دسترسی‌ها

`User`: `username` (unique), `password_hash` (nullable), `full_name`, `role`
(`counselor`/`assistant`/`principal`), `avatar_color`, `can_manage_users` (bool), `is_active`,
`last_login`. Nothing FK-references `User`.

### 7.1 Users list

- `QTableView`; deactivated users in the same list, row greyed + «غیرفعال» badge.
- Top filter «نمایش کاربران غیرفعال» (default off).
- Action column (`can_manage_users` only): ✏️ edit + a فعال/غیرفعال toggle. **No hard delete.**
- Empty-state CTA hidden for non-admins.

### 7.2 `UserDialog(instance=None)`

| Field | Rules |
|---|---|
| `نام و نام خانوادگی` | required |
| `نام کاربری` | `validate_username` (`^[A-Za-z0-9]{3,20}$`), **lowercased on save** (SQLite unique is case-sensitive — normalize so `Ali`/`ali` can't both exist); editable on create only, read-only on edit |
| `نقش` | assistant / counselor / principal — buttons like the wizard |
| `مدیریت کاربران و تنظیمات` | checkbox → `can_manage_users` |
| password | see decision below |

Uniqueness also enforced at DB level (`User.username` unique); catch `IntegrityError`.

**OPEN DECISION — password reset.** The Round-4 answer was "reset clears `password_hash` to
NULL". Codex blocker: `login_dialog.py` authenticates any account with no hash **without a
prompt**, so that's not a reset — it's removing authentication, and anyone can then open that
account. Pick one:

- **(A) Admin sets an explicit temporary password** in the edit dialog (≥8, wizard rules,
  hashed). Simplest safe option, no schema change; the user was previously cool on it but it's
  the low-risk path. The temp password is shown once to the admin to relay.
- **(B) Add a `must_change_password` boolean** (migration) + force a change on next login
  (new branch in `login_dialog`). Cleaner UX, more surface area.
- **(C) Drop password reset from this build.**

Recommendation: **(A)**. Nothing else in Tab 3 is blocked on this.

### 7.3 Rules (enforced in `settings_ops`, inside the transaction, on freshly-reloaded rows)

1. **Gatekeeper** — only `can_manage_users == True` may open `UserDialog` or create / edit /
   deactivate any user.
2. **Job-role freedom** — an admin may set any target's role to any of the three. No rank
   hierarchy. `can_manage_users` is independent of `role`.
3. **Self-deactivation protection** — cannot set `is_active = False` on your own account.
4. **Last-admin guard** — the system must always keep ≥1 user with
   `can_manage_users == True AND is_active == True`. Reject (error dialog) any deactivation or
   `can_manage_users`-clear that would empty that set. Query the set immediately before the
   write, in the transaction — never from a cached model or the table view. Changing the last
   admin's **role** is allowed: it doesn't touch `can_manage_users`, so the guard still holds.
5. **Vault isolation** — user administration never reads, writes, or resets a vault secret.
   `UserDialog` has no vault field. A password reset touches `password_hash` only.

**Your own row:** ✏️ opens the dialog but only `full_name` is editable; `نقش`,
`can_manage_users`, and the active toggle are disabled on yourself.

### 7.4 Audit

`user.create` · `user.update` (name/flags) · `user.role_change` (when `role` changes) ·
`user.activate` / `user.deactivate` (toggle) · `user.password_reset` (reset).

## 8. Tab 4 — امنیت و گاوصندوق

Button→dialog driven. No Save footer.

### 8.1 Personal password — `PasswordChangeDialog` (all users)

- Fields: current password (shown only if `current_user.password_hash` is set), new (≥8),
  confirm.
- Verify current with `auth.verify_password`; set new with `auth.hash_password`.
- On success: `record_audit(current_user, "password.self_change", "User", current_user.id)`.

### 8.2 Vault section (`role == "counselor"` only — hidden entirely otherwise)

**Unlock prerequisite.** The vault DB is not open (see "Pre-existing conditions"). The panel
starts in a **locked** state showing only an "unlock" prompt:

1. Counselor enters their current vault PIN.
2. `creds = DatabaseCredentials.from_vault_pin(pin)` → `manager.unlock_vault(creds)`.
   `unlock_vault` already verifies the DPAPI anchor and fails closed on a wrong PIN / tampered
   vault.
3. On success the panel reveals the status card + "change PIN" button. The vault stays
   unlocked for the rest of the session (matches how a counselor would use notes elsewhere).

**Status card:** active `CounselorNote` count (plain `.count()`, vault already unlocked — no
PBKDF2), and the date of the last `vault.pin_change` audit row (else «تاکنون تغییر نکرده»).
No "lock vault" button.

**`VaultPinDialog` → `DatabaseManager.rotate_vault_pin(old_pin, new_pin)`** (new method).
Exact sequence, all owned by the method:

1. Derive old + new keys from the **raw PINs** (`from_vault_pin` takes a raw PIN, not a
   pre-derived key). Keep the same salt from `data/database_salts.json`.
2. **Verify the old PIN even when there are zero notes**: derive the old state key, recompute
   `_vault_state_commitment()`, `hmac.compare_digest` against the stored anchor commitment.
   Do **not** "accept any PIN and re-anchor" — that would let any entered PIN become
   authoritative. First-time initialization is permitted only when no vault file / anchor
   exists at all.
3. Materialize **every** `CounselorNote` plaintext into memory while the **old** key is still
   the active global (`EncryptedTextField.python_value` decrypts on hydration).
4. `set_vault_cipher_key(new_key_hex)` — switches **both** the data subkey and the state
   subkey globals.
5. In one `manager.transaction(vault=True)`: save every note row back (re-encrypts under the
   new key); on commit, `_commit_vault_state()` advances the DPAPI anchor **under the new
   state key**.
6. `finally`: if the transaction or the anchor write raised, call
   `set_vault_cipher_key(old_key_hex)` to restore the working key and surface a
   recovery-critical error («عملیات ناتمام ماند؛ از نسخه پشتیبان معتبر بازیابی کنید»).
7. After the vault work succeeds, write the `vault.pin_change` audit row in a **separate**
   public transaction (§4).

**Known durability gap** (pre-existing in `transaction()`): SQLite commits before
`state_anchor.store()`. A crash in that window leaves a DB whose anchor won't verify on next
launch. Document it in the dialog's help text; a real fix is out of scope.

**Known limitation — main thread.** Steps 1–5 run synchronously behind a modal: 2× 600k-iter
PBKDF2 (~0.6–1s) plus decrypt/encrypt per note plus a full-table commitment scan. For
realistic note counts that's a ~1–3s freeze during an explicit admin action, which is
acceptable behind a busy modal. `ponytail:` move to a `QThread` (DB/key ownership serialized,
no Qt calls from the worker) only if it proves janky in practice.

New PIN rules: ≥12 chars, must differ from the user's login password (reuse the wizard check),
unrecoverable-acknowledgement checkbox. A forgotten PIN is permanently unrecoverable — no
admin override.

### 8.3 Audit log viewer (`can_manage_users` only)

- `QTableView`, columns `تاریخ` / `کاربر` / `عملیات` / `جزئیات`.
- Order `AuditLog.created_at.desc(), AuditLog.id.desc()` (deterministic ties). Add an index on
  `created_at` in the migration.
- Paginated at 25. `عملیات` via the local Persian label dict. No filters, no pruning.
- Render from fields only — do **not** call `str()` on ORM rows that reference relations that
  don't exist (`CounselorNote.__str__` touches a missing `self.student`).

---

## 9. Touch list

- `src/storage/models.py` — `Classroom.code` + `Meta.indexes`; `Classroom.compose_name()` +
  `save()` override; `AcademicMajor` relabel; `Student`/`Classroom` `major` default;
  `parse_levels` + `grade_options()` helper + `type→grades` map near `AcademicMajor`;
  `AuditLog` `created_at` index. (If decision 7.2-B: `User.must_change_password`.)
- `src/storage/db.py` — `DatabaseManager.rotate_vault_pin(old_pin, new_pin)`.
- `src/storage/audit.py` — new, `record_audit`.
- `src/storage/settings_ops.py` — new, the guarded mutation functions for every settings write.
- `src/storage/migrations/fanus/001_settings_structural.py` — new, hand-authored; upgrade +
  restore test.
- `src/views/main_window.py` — wire the real `SettingsPage` into `_setup_navigation`, pass
  `current_user`.
- `src/views/pages/settings/` — new package, 7 files.
- (If decision 7.2-B: a `must_change_password` branch in `src/views/pages/login_dialog.py`.)

## 10. Codex review — disposition

| # | Finding | Resolution |
|---|---|---|
| 1 | Vault never unlocked in app lifecycle | §8.2 unlock prerequisite |
| 2 | Re-encryption key-switch ordering | §8.2 steps 1–6 |
| 3 | Zero-note "re-anchor" unsafe | §8.2 step 2 — verify old PIN against anchor commitment |
| 4 | Password reset → passwordless login | §7.2 OPEN DECISION (rec. A) |
| 5 | Audit not atomic across DBs; `target_id` UUID-only | §4 |
| 6 | Migration: model layer + dup-index + no seed | §6.1 |
| 7 | Major relabel mappings + snapshots | §6.1 step 2 (relabel both tables, 1:1) |
| 8 | Last-admin stale reads / role changes | §7.3 rule 4 |
| 9 | Inline UI checks don't secure mutations | §2 `settings_ops` guard |
| 10 | Main-thread freeze | §8.2 known limitation |
| minor | school-type parse, active-student query, username case, `get_instance`, viewer order | folded into §5, §6.3–6.4, §7.2, §8.3 |
