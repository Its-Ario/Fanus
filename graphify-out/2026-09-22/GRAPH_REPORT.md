# Graph Report - .  (2026-09-03)

## Corpus Check
- Corpus is ~33,178 words - fits in a single context window. You may not need a graph.

## Summary
- 360 nodes · 918 edges · 25 communities (24 shown, 1 thin omitted)
- Extraction: 85% EXTRACTED · 15% INFERRED · 0% AMBIGUOUS · INFERRED: 142 edges (avg confidence: 0.56)
- Token cost: 83,384 input · 14,714 output

## Community Hubs (Navigation)
- UI Kit & Theming
- Data Models & Auth
- Form Fields & Validation
- Title Bar & Main Window
- Sidebar Navigation
- Config Management
- Database Init & Vault Unlock
- App Bootstrap & Wiring
- Database Manager (Dual DB)
- Vault Key Derivation
- Risk Prediction Inference
- Database Errors & Migration
- Windows DPAPI Vault Anchor
- CI Pipeline & Build Deps
- Persian Digit Utilities
- Fanus Logo & Branding
- Vault Anchor Path & Salts
- Model Training & Tuning
- Encrypted Field Type
- Fanus (misc)

## God Nodes (most connected - your core abstractions)
1. `FirstRunWizard` - 39 edges
2. `DatabaseManager` - 34 edges
3. `Colors` - 26 edges
4. `DashboardPage` - 26 edges
5. `LoginDialog` - 24 edges
6. `ConfigManager` - 23 edges
7. `SubjectAverage` - 20 edges
8. `TitleBar` - 19 edges
9. `FormField` - 19 edges
10. `Card` - 19 edges

## Surprising Connections (you probably didn't know these)
- `FakeUser` --uses--> `DatabaseConfigurationError`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/db.py
- `FakeUser` --uses--> `DatabaseManager`  [INFERRED]
  tests/test_auth_and_login.py → src/storage/db.py
- `FakeUser` --uses--> `Avatar`  [INFERRED]
  tests/test_auth_and_login.py → src/views/components/ui_kit.py
- `FakeUser` --uses--> `LoginDialog`  [INFERRED]
  tests/test_auth_and_login.py → src/views/pages/login_dialog.py
- `main()` --calls--> `MainWindow`  [EXTRACTED]
  main.py → src/views/main_window.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Offline-first delivery for old hardware: bundled GUI exe + transpiled ML model** — readme_fanus, requirements_app_gui_stack, github_workflows_build_build_windows_job, requirements_train_m2cgen_transpile [INFERRED 0.75]
- **Dual-database migration regime linked by student_id UUID** — src_storage_migrations_fanus_readme_migration_policy, src_storage_migrations_vault_readme_migration_policy, src_storage_migrations_vault_readme_cross_db_student_id [EXTRACTED 0.75]

## Communities (25 total, 1 thin omitted)

### Community 0 - "UI Kit & Theming"
Cohesion: 0.08
Nodes (41): date, QLineEdit, Colors, generate_profile_color(), AIInsightCard, apply_soft_shadow(), Card, Divider (+33 more)

### Community 1 - "Data Models & Auth"
Cohesion: 0.09
Nodes (29): Model, hash_password(), verify_password(), encrypt_vault_value(), AcademicGrade, AcademicMajor, AttendanceRecord, AuditLog (+21 more)

### Community 2 - "Form Fields & Validation"
Cohesion: 0.11
Nodes (11): QLabel, validate_academic_year(), validate_username(), FormField, A labelled text field shared by focused forms such as setup and settings., Propagate changed helper text size through parent layouts immediately., FirstRunWizard, QDialog (+3 more)

### Community 3 - "Title Bar & Main Window"
Cohesion: 0.11
Nodes (9): QMainWindow, QFrame, Custom title bar replacing the native OS bar. Fully draggable., TitleBar, MainWindow, LoginDialog, QDialog, QFrame (+1 more)

### Community 4 - "Sidebar Navigation"
Cohesion: 0.16
Nodes (8): NavItem, QFrame, QPushButton, A sidebar button that collapses cleanly to icon-only mode., Sidebar, UserFooter, Avatar, test_avatar_uses_an_explicit_account_color()

### Community 5 - "Config Management"
Cohesion: 0.24
Nodes (8): Any, AppConfig, ConfigManager, Path, Saves config using atomic writing, Manages loading, saving and verifying config.json, Computes a Base64 HMAC-SHA256 signature, Loads config.json from disk

### Community 6 - "Database Init & Vault Unlock"
Cohesion: 0.20
Nodes (8): fixture, SqliteDatabase, DatabaseConnectionError, Open and migrate only the public application database., Open and migrate the encrypted vault after its PIN is provided., Raised when a database cannot be opened., in_memory_db(), Provides an isolated, fast, in-memory SQLite database for testing.

### Community 7 - "App Bootstrap & Wiring"
Cohesion: 0.29
Nodes (9): main(), setup_logging(), configure_database_manager(), DatabaseCredentials, get_database_manager(), Key material for encrypted vault fields., Configure the application-wide manager exactly once per process., init_database() (+1 more)

### Community 8 - "Database Manager (Dual DB)"
Cohesion: 0.21
Nodes (4): DatabaseManager, Owns both databases, schema setup, connections, and transactions., Advance the locally protected state after a committed vault mutation., Close the confidential database and discard derived keys from this process.

### Community 9 - "Vault Key Derivation"
Cohesion: 0.23
Nodes (11): decrypt_vault_value(), _derive_key(), _derive_subkey(), Set (or clear) subkeys from the vault key., Keep encryption and integrity keys cryptographically independent., set_vault_cipher_key(), test_different_vault_pin_derives_a_different_key(), test_manager_creates_two_plain_sqlite_databases() (+3 more)

### Community 10 - "Risk Prediction Inference"
Cohesion: 0.26
Nodes (6): Runs instant (< 1ms) inference using exported m2cgen code. Returns:…, RiskPredictor, test_burnout_candidate_prediction(), test_failing_student_prediction(), test_more_absences_increases_risk(), test_perfect_student_prediction()

### Community 11 - "Database Errors & Migration"
Cohesion: 0.25
Nodes (7): RuntimeError, DatabaseConfigurationError, DatabaseError, DatabaseMigrationError, Base class for errors safe to present to the application layer., Raised when database encryption cannot be configured., Raised when the on-disk schema cannot be brought to the new version.

### Community 12 - "Windows DPAPI Vault Anchor"
Cohesion: 0.31
Nodes (4): Fail closed when a Windows-protected anchor disagrees with vault state., Raised when the vault does not match its Windows-protected state anchor., VaultIntegrityError, WindowsDpapiAnchor

### Community 13 - "CI Pipeline & Build Deps"
Cohesion: 0.24
Nodes (10): Build Windows Executable job (PyInstaller onefile), CI Build Pipeline (GitHub Actions), Lint & Test job (Ruff + pytest, Python 3.8, uv), Fanus - offline-first study manager & planner for old hardware, App runtime dependencies (PyQt5, PyInstaller), m2cgen model-to-native-code transpilation, Training dependencies (numpy, pandas, scikit-learn, joblib, m2cgen), Fanus DB migration policy (numbered peewee-migrate, restore-path test) (+2 more)

### Community 14 - "Persian Digit Utilities"
Cohesion: 0.48
Nodes (5): Converts any number or string containing numbers into Persian digits., to_persian_digits(), test_already_persian_digits_unchanged(), test_convert_english_digits_to_persian(), test_mixed_strings()

### Community 15 - "Fanus Logo & Branding"
Cohesion: 0.47
Nodes (6): Navy and Amber Brand Palette, Circuit Board Traces and Nodes, Fanus Logo, Fanus Project, Glowing Four-Pointed Star / Sparkle, Circuit-Style Lantern Motif

### Community 16 - "Vault Anchor Path & Salts"
Cohesion: 0.40
Nodes (4): _default_vault_anchor_path(), _load_or_create_salts(), Path, Keep the DPAPI-protected anchor outside portable database files.

### Community 17 - "Model Training & Tuning"
Cohesion: 0.60
Nodes (4): load_and_harmonize_datasets(), train_and_export(), benchmark_combination(), main()

### Community 18 - "Encrypted Field Type"
Cohesion: 0.40
Nodes (3): EncryptedTextField, TextField encrypted with AES-256-GCM with vault key., TextField

## Knowledge Gaps
- **6 isolated node(s):** `fanus`, `AcademicMajor`, `StudyPeriod`, `App runtime dependencies (PyQt5, PyInstaller)`, `Training dependencies (numpy, pandas, scikit-learn, joblib, m2cgen)` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FirstRunWizard` connect `Form Fields & Validation` to `UI Kit & Theming`, `Data Models & Auth`, `Title Bar & Main Window`, `Config Management`, `App Bootstrap & Wiring`?**
  _High betweenness centrality (0.137) - this node is a cross-community bridge._
- **Why does `DatabaseManager` connect `Database Manager (Dual DB)` to `UI Kit & Theming`, `Data Models & Auth`, `Config Management`, `Database Init & Vault Unlock`, `App Bootstrap & Wiring`, `Vault Key Derivation`, `Database Errors & Migration`, `Windows DPAPI Vault Anchor`, `Vault Anchor Path & Salts`?**
  _High betweenness centrality (0.126) - this node is a cross-community bridge._
- **Why does `ConfigManager` connect `Config Management` to `UI Kit & Theming`, `Form Fields & Validation`, `Database Init & Vault Unlock`, `App Bootstrap & Wiring`, `Database Manager (Dual DB)`, `Database Errors & Migration`, `Windows DPAPI Vault Anchor`?**
  _High betweenness centrality (0.108) - this node is a cross-community bridge._
- **Are the 11 inferred relationships involving `FirstRunWizard` (e.g. with `ConfigManager` and `DatabaseCredentials`) actually correct?**
  _`FirstRunWizard` has 11 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `DatabaseManager` (e.g. with `ConfigManager` and `FakeUser`) actually correct?**
  _`DatabaseManager` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Colors` (e.g. with `AIInsightCard` and `Avatar`) actually correct?**
  _`Colors` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `DashboardPage` (e.g. with `MainWindow` and `AcademicGrade`) actually correct?**
  _`DashboardPage` has 18 INFERRED edges - model-reasoned connections that need verification._