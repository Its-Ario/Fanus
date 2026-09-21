import base64
import hmac
import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Any, Dict

HMAC_SECRET = b"SECRET_HERE"

logger = logging.getLogger(__name__)


@dataclass
class AppConfig:
    version: int = 1
    is_configured: bool = False
    operation_mode: str = "STANDALONE"
    hub: dict = field(default_factory=dict)
    signature: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:

    @staticmethod
    def get_app_dir() -> Path:
        if sys.platform == "win32":
            local_appdata = os.getenv("LOCALAPPDATA")
            if local_appdata:
                base_dir = Path(local_appdata)
            else:
                base_dir = Path.home() / "AppData" / "Local"
        else:
            base_dir = Path.home() / ".config"
        app_dir = base_dir / "Fanus"
        app_dir.mkdir(parents=True, exist_ok=True)
        return app_dir

    @classmethod
    def get_config_path(cls) -> Path:
        return cls.get_app_dir() / "config.json"

    @staticmethod
    def compute_signature(config_dict: Dict[str, Any]) -> str:

        payload = {k: v for k, v in config_dict.items() if k != "signature"}

        formatted_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        digest = hmac.new(HMAC_SECRET, formatted_json.encode("utf-8"), sha256).digest()

        return base64.b64encode(digest).decode("utf-8")

    @classmethod
    def verify_integrity(cls, config_dict: Dict[str, Any]) -> bool:
        stored_sign = config_dict.get("signature", "")

        if not stored_sign:
            return False

        calculated_sign = cls.compute_signature(config_dict)

        return hmac.compare_digest(stored_sign, calculated_sign)

    @classmethod
    def load(cls) -> AppConfig:

        config_path = cls.get_config_path()

        if not config_path.exists():
            default_config = AppConfig()
            cls.save(default_config)
            return default_config

        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data: Dict[str, Any] = json.load(f)

                if not cls.verify_integrity(data):
                    logger.warning("Signature mismatch")
                    default_config = AppConfig()
                    cls._backup_corrupt_file(config_path)
                    cls.save(default_config)
                    return default_config
                return AppConfig(
                    version=data.get("version", 1),
                    operation_mode=data.get("operation_mode", "STANDALONE"),
                    hub=data.get("hub", {}),
                    signature=data.get("signature", ""),
                    is_configured=data.get("is_configured", False),
                )
        except Exception:
            logger.exception("Failed to read config.json")

            default_config = AppConfig()
            cls._backup_corrupt_file(config_path)
            cls.save(default_config)
            return default_config

    @classmethod
    def save(cls, config: AppConfig) -> bool:

        config_path = cls.get_config_path()
        temp_path = config_path.with_name(f"{config_path.name}.{os.getpid()}.tmp")
        try:
            config_dict = config.to_dict()
            config_dict["signature"] = cls.compute_signature(config_dict)

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(config_dict, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, config_path)
            return True
        except Exception:
            logger.exception("Error writing to config.json")
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            return False

    @classmethod
    def mark_configured(cls) -> bool:
        config = cls.load()
        config.is_configured = True
        return cls.save(config)

    @staticmethod
    def _backup_corrupt_file(config_path: Path) -> None:
        try:
            bak_path = config_path.with_suffix(".json.bak")
            if config_path.exists():
                os.replace(config_path, bak_path)
        except Exception:
            logger.exception("Could not backup file")
