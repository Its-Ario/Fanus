import re
from pathlib import Path


def get_version() -> str:
    pyproject_path = Path(__file__).resolve().parents[2] / "pyproject.toml"

    try:
        content = pyproject_path.read_text(encoding="utf-8")
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
    except Exception:  # noqa: BLE001, S110
        pass

    return "1.0.0"
