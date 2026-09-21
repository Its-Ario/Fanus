import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional, Tuple

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from peewee import DatabaseProxy, SqliteDatabase

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FANUS_DB_PATH = DATA_DIR / "fanus.db"
VAULT_DB_PATH = DATA_DIR / "counselor_vault.db"
KEY_SALTS_PATH = DATA_DIR / "database_salts.json"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

db = DatabaseProxy()
vault_db = DatabaseProxy()

_vault_cipher_key: Optional[bytes] = None
_vault_state_key: Optional[bytes] = None


def set_vault_cipher_key(key_hex: Optional[str]) -> None:
    global _vault_cipher_key, _vault_state_key
    if not key_hex:
        _vault_cipher_key = None
        _vault_state_key = None
        return
    master_key = bytes.fromhex(key_hex)
    _vault_cipher_key = _derive_subkey(master_key, b"fanus/vault/data/v1")
    _vault_state_key = _derive_subkey(master_key, b"fanus/vault/state/v1")


def _derive_subkey(master_key: bytes, context: bytes) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=context).derive(master_key)


def encrypt_vault_value(plaintext: str) -> str:
    if _vault_cipher_key is None:
        raise DatabaseConfigurationError("Vault encryption key is not set.")
    nonce = secrets.token_bytes(12)
    ciphertext = AESGCM(_vault_cipher_key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ciphertext).decode("ascii")


def decrypt_vault_value(stored: str) -> str:
    if _vault_cipher_key is None:
        raise DatabaseConfigurationError("Vault encryption key is not set.")
    raw = base64.b64decode(stored)
    nonce, ciphertext = raw[:12], raw[12:]
    return AESGCM(_vault_cipher_key).decrypt(nonce, ciphertext, None).decode("utf-8")


class DatabaseError(RuntimeError):
    pass


class DatabaseConfigurationError(DatabaseError):
    pass


class DatabaseConnectionError(DatabaseError):
    pass


class DatabaseMigrationError(DatabaseError):
    pass


class VaultIntegrityError(DatabaseError):
    pass


class WindowsDpapiAnchor:
    _ENTROPY = b"Fanus vault state anchor v1"

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    @property
    def available(self) -> bool:
        return sys.platform == "win32"

    def load(self) -> Optional[Tuple[int, str]]:
        if not self.available or not self.path.exists():
            return None
        try:
            raw = self._unprotect(self.path.read_bytes())
            value = json.loads(raw.decode("utf-8"))
            generation = value["generation"]
            commitment = value["commitment"]
            if not isinstance(generation, int) or generation < 0 or not isinstance(commitment, str):
                raise ValueError("invalid anchor structure")
            return generation, commitment
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            raise VaultIntegrityError("The local vault integrity anchor is invalid.") from exc

    def store(self, generation: int, commitment: str) -> None:
        if not self.available:
            return
        payload = json.dumps(
            {"generation": generation, "commitment": commitment},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        protected = self._protect(payload)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        try:
            temporary.write_bytes(protected)
            os.replace(temporary, self.path)
        finally:
            if temporary.exists():
                temporary.unlink()

    @classmethod
    def _protect(cls, plaintext: bytes) -> bytes:
        return cls._crypt(plaintext, protect=True)

    @classmethod
    def _unprotect(cls, ciphertext: bytes) -> bytes:
        return cls._crypt(ciphertext, protect=False)

    @classmethod
    def _crypt(cls, value: bytes, protect: bool) -> bytes:
        if sys.platform != "win32":
            raise VaultIntegrityError("Windows DPAPI is unavailable on this platform.")

        import ctypes
        from ctypes import wintypes

        class DataBlob(ctypes.Structure):
            _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

        value_buffer = ctypes.create_string_buffer(value)
        entropy_buffer = ctypes.create_string_buffer(cls._ENTROPY)
        input_blob = DataBlob(len(value), ctypes.cast(value_buffer, ctypes.POINTER(ctypes.c_byte)))
        entropy_blob = DataBlob(
            len(cls._ENTROPY), ctypes.cast(entropy_buffer, ctypes.POINTER(ctypes.c_byte))
        )
        output_blob = DataBlob()
        crypt32 = ctypes.WinDLL("Crypt32.dll", use_last_error=True)
        kernel32 = ctypes.WinDLL("Kernel32.dll", use_last_error=True)
        if protect:
            operation = crypt32.CryptProtectData
            ok = operation(
                ctypes.byref(input_blob),
                None,
                ctypes.byref(entropy_blob),
                None,
                None,
                1,
                ctypes.byref(output_blob),
            )
        else:
            operation = crypt32.CryptUnprotectData
            description = wintypes.LPWSTR()
            ok = operation(
                ctypes.byref(input_blob),
                ctypes.byref(description),
                ctypes.byref(entropy_blob),
                None,
                None,
                1,
                ctypes.byref(output_blob),
            )
        if not ok:
            raise VaultIntegrityError(f"Windows DPAPI failed (error {ctypes.get_last_error()}).")
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)


@dataclass(frozen=True)
class DatabaseCredentials:

    vault_key: str

    def __post_init__(self) -> None:
        if not self.vault_key:
            raise DatabaseConfigurationError("Vault encryption key must not be empty.")

    @classmethod
    def from_vault_pin(
        cls,
        vault_pin: str,
        salts_path: Path = KEY_SALTS_PATH,
    ) -> "DatabaseCredentials":
        if not vault_pin:
            raise DatabaseConfigurationError("A vault PIN is required.")

        salts = _load_or_create_salts(Path(salts_path))
        return cls(vault_key=_derive_key(vault_pin, salts["vault"]))


class DatabaseManager:

    def __init__(
        self,
        credentials: Optional[DatabaseCredentials] = None,
        fanus_path: Path = FANUS_DB_PATH,
        vault_path: Path = VAULT_DB_PATH,
        migrations_dir: Path = MIGRATIONS_DIR,
        state_anchor_path: Optional[Path] = None,
    ) -> None:
        self._credentials = credentials
        self.fanus_path = Path(fanus_path)
        self.vault_path = Path(vault_path)
        self.migrations_dir = Path(migrations_dir)
        default_anchor = (
            _default_vault_anchor_path(self.vault_path)
            if sys.platform == "win32"
            else self.vault_path.with_name(".vault_anchor")
        )
        self.state_anchor = WindowsDpapiAnchor(state_anchor_path or default_anchor)
        self._public_initialized = False
        self._vault_initialized = False
        self._vault_generation = 0
        self._vault_file_existed = False

    @property
    def initialized(self) -> bool:
        return self._public_initialized

    @property
    def vault_initialized(self) -> bool:
        return self._vault_initialized

    def initialize(self) -> None:
        self.initialize_public()
        if self._credentials is not None:
            self.unlock_vault(self._credentials)

    def initialize_public(self) -> None:
        if self._public_initialized:
            return

        self.fanus_path.parent.mkdir(parents=True, exist_ok=True)
        public_database = self._new_sqlite_database(self.fanus_path)
        db.initialize(public_database)

        try:
            self._open_and_verify(public_database, self.fanus_path)
            self._migrate_public(public_database)
        except DatabaseError:
            self._close_database(db)
            raise
        except Exception as exc:
            self._close_database(db)
            logger.exception("Unexpected public database initialization failure")
            raise DatabaseConnectionError(
                "Could not initialize the application data store."
            ) from exc

        self._public_initialized = True
        logger.info("Fanus public database initialized")

    def unlock_vault(self, credentials: DatabaseCredentials) -> None:
        if self._vault_initialized:
            return

        self.vault_path.parent.mkdir(parents=True, exist_ok=True)
        self._vault_file_existed = self.vault_path.exists()
        private_database = self._new_sqlite_database(self.vault_path)
        vault_db.initialize(private_database)
        set_vault_cipher_key(credentials.vault_key)

        try:
            self._open_and_verify(private_database, self.vault_path)
            self._migrate_vault(private_database)
            self._verify_or_initialize_vault_anchor()
        except DatabaseError:
            self._close_database(vault_db)
            set_vault_cipher_key(None)
            raise
        except Exception as exc:
            self._close_database(vault_db)
            set_vault_cipher_key(None)
            logger.exception("Unexpected vault initialization failure")
            raise DatabaseConnectionError(
                "Could not initialize the confidential data store."
            ) from exc

        self._credentials = credentials
        self._vault_initialized = True
        logger.info("Fanus confidential vault unlocked")

    def _verify_or_initialize_vault_anchor(self) -> None:
        restore_marker = self.vault_path.with_name(".restore_pending")
        if restore_marker.exists():
            if self.state_anchor.available:
                try:
                    self.state_anchor.path.unlink()
                except FileNotFoundError:
                    pass
            self.state_anchor.store(0, self._vault_state_commitment())
            self._vault_generation = 0
            try:
                restore_marker.unlink()
            except FileNotFoundError:
                pass
            logger.info("Re-anchored confidential vault after restore")
            return

        commitment = self._vault_state_commitment()
        anchor = self.state_anchor.load()
        if anchor is None:
            if self.state_anchor.available and self._vault_file_existed:
                raise VaultIntegrityError(
                    "The local vault integrity anchor is missing. Restore it with a valid backup."
                )

            self.state_anchor.store(0, commitment)
            self._vault_generation = 0
            if self.state_anchor.available:
                logger.info("Created Windows-protected vault integrity anchor")
            else:
                logger.warning("Windows DPAPI unavailable; vault rollback detection is disabled")
            return
        generation, expected_commitment = anchor
        if not hmac.compare_digest(commitment, expected_commitment):
            raise VaultIntegrityError(
                "The confidential vault has changed outside the application. Restore a valid backup."
            )
        self._vault_generation = generation

    def _vault_state_commitment(self) -> str:
        if _vault_state_key is None:
            raise DatabaseConfigurationError("Vault encryption key is not set.")
        digest = hmac.new(_vault_state_key, b"fanus/vault-state/v1\x00", hashlib.sha256)
        for model in sorted(self._vault_models(), key=lambda item: item._meta.table_name):
            table_name = model._meta.table_name.replace('"', '""')
            cursor = vault_db.execute_sql(f'SELECT * FROM "{table_name}" ORDER BY id')
            column_names = [item[0] for item in cursor.description]
            for row in cursor.fetchall():
                digest.update(model._meta.table_name.encode("utf-8"))
                for column, value in zip(column_names, row):
                    self._commit_state_value(digest, column)
                    self._commit_state_value(digest, value)
        return digest.hexdigest()

    @staticmethod
    def _vault_models():
        from src.storage.models import VAULT_MODELS

        return VAULT_MODELS

    @staticmethod
    def _commit_state_value(digest, value) -> None:
        if value is None:
            encoded = b"N"
        elif isinstance(value, bytes):
            encoded = b"B" + value
        else:
            encoded = b"T" + str(value).encode("utf-8")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)

    @staticmethod
    def _new_sqlite_database(path: Path):
        return SqliteDatabase(
            str(path),
            pragmas={
                "foreign_keys": 1,
                "journal_mode": "wal",
                "cache_size": -1024 * 64,
                "synchronous": "normal",
                "temp_store": "memory",
            },
        )

    @staticmethod
    def _open_and_verify(database: SqliteDatabase, path: Path) -> None:
        try:
            database.connect(reuse_if_open=True)
            database.execute_sql("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception as exc:
            logger.warning("Could not open database at %s", path)
            raise DatabaseConnectionError(
                "Could not open the database. Restore a valid backup."
            ) from exc

    def _migrate_public(self, public_database) -> None:
        try:
            from peewee_migrate import Router

            from src.storage.models import PUBLIC_MODELS

            public_is_new = not public_database.get_tables()
            public_migrations = self.migrations_dir / "fanus"
            public_migrations.mkdir(parents=True, exist_ok=True)
            Router(public_database, migrate_dir=str(public_migrations)).run()
            if public_is_new:
                public_database.create_tables(PUBLIC_MODELS, safe=False)
            self._verify_schema(public_database, PUBLIC_MODELS)
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "peewee-migrate is required for schema management."
            ) from exc
        except Exception as exc:
            logger.exception("Public database migration failed")
            raise DatabaseMigrationError(
                "The application database schema could not be updated safely."
            ) from exc

    def _migrate_vault(self, private_database) -> None:
        try:
            from peewee_migrate import Router

            from src.storage.models import VAULT_MODELS

            vault_is_new = not private_database.get_tables()
            vault_migrations = self.migrations_dir / "vault"
            vault_migrations.mkdir(parents=True, exist_ok=True)
            Router(private_database, migrate_dir=str(vault_migrations)).run()
            if vault_is_new:
                private_database.create_tables(VAULT_MODELS, safe=False)
            self._verify_schema(private_database, VAULT_MODELS)
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "peewee-migrate is required for schema management."
            ) from exc
        except Exception as exc:
            logger.exception("Database migration failed")
            raise DatabaseMigrationError(
                "The encrypted database schema could not be updated safely."
            ) from exc

    @staticmethod
    def _verify_schema(database, models) -> None:
        actual_tables = set(database.get_tables())
        required_tables = {model._meta.table_name for model in models}
        missing_tables = required_tables - actual_tables
        if missing_tables:
            names = ", ".join(sorted(missing_tables))
            raise DatabaseMigrationError(f"Required database tables are missing: {names}.")

    @contextmanager
    def transaction(self, vault: bool = False) -> Generator[None, None, None]:
        if vault and not self._vault_initialized:
            raise DatabaseConfigurationError("The confidential vault must be unlocked first.")
        if not vault and not self._public_initialized:
            raise DatabaseConfigurationError(
                "DatabaseManager.initialize_public() must be called first."
            )
        database = vault_db if vault else db
        try:
            with database.atomic():
                yield
            if vault:
                self._commit_vault_state()
        except Exception:
            logger.exception("Database transaction rolled back")
            raise

    def _commit_vault_state(self) -> None:
        if not self.state_anchor.available:
            return
        self._vault_generation += 1
        self.state_anchor.store(self._vault_generation, self._vault_state_commitment())

    def rotate_vault_pin(self, old_pin: str, new_pin: str) -> None:
        if not self._vault_initialized:
            raise DatabaseConfigurationError("The confidential vault must be unlocked first.")
        old_credentials = DatabaseCredentials.from_vault_pin(old_pin)
        new_credentials = DatabaseCredentials.from_vault_pin(new_pin)
        old_key_hex = old_credentials.vault_key
        if self._credentials is not None and not hmac.compare_digest(
            old_key_hex, self._credentials.vault_key
        ):
            raise VaultIntegrityError("The supplied vault PIN is invalid.")
        set_vault_cipher_key(old_key_hex)
        try:
            anchor = self.state_anchor.load()
            if anchor is None:
                if self.state_anchor.available:
                    raise VaultIntegrityError("The local vault integrity anchor is missing.")
            else:
                _, expected = anchor
                if not hmac.compare_digest(self._vault_state_commitment(), expected):
                    raise VaultIntegrityError("پین فعلی نادرست است یا گاوصندوق معتبر نیست.")

            from src.storage.models import CounselorNote

            notes = list(CounselorNote.select())
            plaintext = [(note, note.content) for note in notes]
            set_vault_cipher_key(new_credentials.vault_key)
            with self.transaction(vault=True):
                for note, content in plaintext:
                    note.content = content
                    note.save()
            self._credentials = new_credentials
        except Exception:
            set_vault_cipher_key(old_key_hex)
            raise

    def close(self) -> None:
        if self._public_initialized:
            self._close_database(db)
        if self._vault_initialized:
            self._close_database(vault_db)
        set_vault_cipher_key(None)
        self._public_initialized = False
        self._vault_initialized = False

    def lock_vault(self) -> None:
        if self._vault_initialized:
            self._close_database(vault_db)
        set_vault_cipher_key(None)
        self._vault_initialized = False

    @property
    def vault_unlocked(self) -> bool:
        return self._vault_initialized

    @staticmethod
    def _close_database(database) -> None:
        try:
            if not database.is_closed():
                database.close()
        except Exception:
            logger.exception("Could not close database connection cleanly")


_manager: Optional[DatabaseManager] = None


def configure_database_manager(
    credentials: Optional[DatabaseCredentials] = None,
) -> DatabaseManager:
    global _manager
    if _manager is not None and _manager.initialized:
        raise DatabaseConfigurationError("DatabaseManager is already initialized for this process.")
    _manager = DatabaseManager(credentials)
    return _manager


def get_database_manager() -> DatabaseManager:
    if _manager is None:
        raise DatabaseConfigurationError("DatabaseManager has not been configured.")
    return _manager


def _default_vault_anchor_path(vault_path: Path) -> Path:
    from src.core.config import ConfigManager

    vault_id = hashlib.sha256(str(Path(vault_path).resolve()).encode("utf-8")).hexdigest()
    return ConfigManager.get_app_dir() / "vault-anchors" / vault_id / ".vault_anchor"


def _derive_key(password: str, salt: bytes) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000).hex()


def _load_or_create_salts(path: Path) -> dict:
    if path.exists():
        try:
            encoded_salts = json.loads(path.read_text(encoding="utf-8"))
            salts = {"vault": bytes.fromhex(encoded_salts["vault"])}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DatabaseConfigurationError("Database salt metadata is invalid.") from exc
        if any(len(value) < 16 for value in salts.values()):
            raise DatabaseConfigurationError("Database salt metadata is too weak.")
        return salts

    path.parent.mkdir(parents=True, exist_ok=True)
    salts = {"vault": secrets.token_bytes(32)}
    try:
        path.write_text(
            json.dumps({name: value.hex() for name, value in salts.items()}), encoding="utf-8"
        )
    except OSError as exc:
        raise DatabaseConfigurationError("Could not persist database salt metadata.") from exc
    return salts
