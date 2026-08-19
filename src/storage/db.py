import hashlib
import json
import logging
import secrets
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

from peewee import DatabaseProxy

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
FANUS_DB_PATH = DATA_DIR / "fanus.db"
VAULT_DB_PATH = DATA_DIR / "counselor_vault.db"
KEY_SALTS_PATH = DATA_DIR / "database_salts.json"
MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"

db = DatabaseProxy()
vault_db = DatabaseProxy()


class DatabaseError(RuntimeError):
    """Base class for errors safe to present to the application layer."""


class DatabaseConfigurationError(DatabaseError):
    """Raised when database encryption cannot be configured."""


class DatabaseConnectionError(DatabaseError):
    """Raised when an encrypted database cannot be opened."""


class DatabaseMigrationError(DatabaseError):
    """Raised when the on-disk schema cannot be brought to the new version."""


@dataclass(frozen=True)
class DatabaseCredentials:
    """Independent passphrase by the authentication flow."""

    fanus_key: str
    vault_key: str

    def __post_init__(self) -> None:
        if not self.fanus_key or not self.vault_key:
            raise DatabaseConfigurationError("Database encryption keys must not be empty.")

    @classmethod
    def from_passwords(
        cls,
        admin_password: str,
        vault_pin: str,
        salts_path: Path = KEY_SALTS_PATH,
    ) -> "DatabaseCredentials":
        if not admin_password or not vault_pin:
            raise DatabaseConfigurationError("An admin password and vault PIN are required.")

        salts = _load_or_create_salts(Path(salts_path))
        return cls(
            fanus_key=_derive_key(admin_password, salts["fanus"]),
            vault_key=_derive_key(vault_pin, salts["vault"]),
        )


class DatabaseManager:
    """Owns both databases, schema setup, connections, and transactions."""

    def __init__(
        self,
        credentials: DatabaseCredentials,
        fanus_path: Path = FANUS_DB_PATH,
        vault_path: Path = VAULT_DB_PATH,
        migrations_dir: Path = MIGRATIONS_DIR,
    ) -> None:
        self._credentials = credentials
        self.fanus_path = Path(fanus_path)
        self.vault_path = Path(vault_path)
        self.migrations_dir = Path(migrations_dir)
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    def initialize(self) -> None:
        """Open both encrypted stores and bring their schemas up to date."""
        if self._initialized:
            return

        self.fanus_path.parent.mkdir(parents=True, exist_ok=True)
        self.vault_path.parent.mkdir(parents=True, exist_ok=True)

        public_database = self._new_cipher_database(self.fanus_path, self._credentials.fanus_key)
        private_database = self._new_cipher_database(self.vault_path, self._credentials.vault_key)
        db.initialize(public_database)
        vault_db.initialize(private_database)

        try:
            self._open_and_verify(public_database, self.fanus_path)
            self._open_and_verify(private_database, self.vault_path)
            self._migrate(public_database, private_database)
        except DatabaseError:
            self.close()
            raise
        except Exception as exc:
            self.close()
            logger.exception("Unexpected database initialization failure")
            raise DatabaseConnectionError("Could not initialize the encrypted data stores.") from exc

        self._initialized = True
        logger.info("Encrypted Fanus databases initialized")

    @staticmethod
    def _new_cipher_database(path: Path, passphrase: str):
        try:
            from playhouse.sqlcipher_ext import SqlCipherDatabase
        except ImportError as exc:
            raise DatabaseConfigurationError(
                "SQLCipher support is unavailable. Install the pysqlcipher3-binary runtime."
            ) from exc

        return SqlCipherDatabase(
            str(path),
            passphrase=passphrase,
            pragmas={
                "foreign_keys": 1,
                "journal_mode": "wal",
                "cache_size": -1024 * 64,
                "synchronous": "normal",
                "temp_store": "memory",
                "cipher_memory_security": "on",
            },
        )

    @staticmethod
    def _open_and_verify(database, path: Path) -> None:
        try:
            database.connect(reuse_if_open=True)
            database.execute_sql("SELECT count(*) FROM sqlite_master").fetchone()
        except Exception as exc:
            logger.warning("Could not open encrypted database at %s", path)
            raise DatabaseConnectionError(
                "Could not open an encrypted database. Check the key or restore a valid backup."
            ) from exc

    def _migrate(self, public_database, private_database) -> None:
        try:
            from peewee_migrate import Router

            from src.storage.models import PUBLIC_MODELS, VAULT_MODELS

            public_is_new = not public_database.get_tables()
            vault_is_new = not private_database.get_tables()
            public_migrations = self.migrations_dir / "fanus"
            vault_migrations = self.migrations_dir / "vault"
            public_migrations.mkdir(parents=True, exist_ok=True)
            vault_migrations.mkdir(parents=True, exist_ok=True)
            Router(public_database, migrate_dir=str(public_migrations)).run()
            Router(private_database, migrate_dir=str(vault_migrations)).run()
            # Bootstrap only
            if public_is_new:
                public_database.create_tables(PUBLIC_MODELS, safe=False)
            if vault_is_new:
                private_database.create_tables(VAULT_MODELS, safe=False)
            self._verify_schema(public_database, PUBLIC_MODELS)
            self._verify_schema(private_database, VAULT_MODELS)
        except ImportError as exc:
            raise DatabaseConfigurationError("peewee-migrate is required for schema management.") from exc
        except Exception as exc:
            logger.exception("Database migration failed")
            raise DatabaseMigrationError("The encrypted database schema could not be updated safely.") from exc

    @staticmethod
    def _verify_schema(database, models) -> None:
        actual_tables = set(database.get_tables())
        required_tables = {model._meta.table_name for model in models}
        missing_tables = required_tables - actual_tables
        if missing_tables:
            names = ", ".join(sorted(missing_tables))
            raise DatabaseMigrationError(f"Required database tables are missing: {names}.")

    @contextmanager
    def transaction(self, vault: bool = False) -> Generator[None]:
        if not self._initialized:
            raise DatabaseConfigurationError("DatabaseManager.initialize() must be called first.")
        database = vault_db if vault else db
        try:
            with database.atomic():
                yield
        except Exception:
            logger.exception("Database transaction rolled back")
            raise

    def close(self) -> None:
        for database in (db, vault_db):
            try:
                if not database.is_closed():
                    database.close()
            except Exception:
                logger.exception("Could not close database connection cleanly")
        self._initialized = False


_manager: Optional[DatabaseManager] = None


def configure_database_manager(credentials: DatabaseCredentials) -> DatabaseManager:
    """Configure the application-wide manager exactly once per process."""
    global _manager
    if _manager is not None and _manager.initialized:
        raise DatabaseConfigurationError("DatabaseManager is already initialized for this process.")
    _manager = DatabaseManager(credentials)
    return _manager


def get_database_manager() -> DatabaseManager:
    if _manager is None:
        raise DatabaseConfigurationError("DatabaseManager has not been configured.")
    return _manager


def _derive_key(password: str, salt: bytes) -> str:
    # 32-byte key
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600_000).hex()


def _load_or_create_salts(path: Path) -> dict:
    if path.exists():
        try:
            encoded_salts = json.loads(path.read_text(encoding="utf-8"))
            salts = {name: bytes.fromhex(encoded_salts[name]) for name in ("fanus", "vault")}
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise DatabaseConfigurationError("Database salt metadata is invalid.") from exc
        if any(len(value) < 16 for value in salts.values()):
            raise DatabaseConfigurationError("Database salt metadata is too weak.")
        return salts

    path.parent.mkdir(parents=True, exist_ok=True)
    salts = {"fanus": secrets.token_bytes(32), "vault": secrets.token_bytes(32)}
    try:
        path.write_text(
            json.dumps({name: value.hex() for name, value in salts.items()}), encoding="utf-8"
        )
    except OSError as exc:
        raise DatabaseConfigurationError("Could not persist database salt metadata.") from exc
    return salts
