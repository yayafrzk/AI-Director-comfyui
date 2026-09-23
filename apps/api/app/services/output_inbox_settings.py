import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from uuid import uuid4

from app.core.config import get_settings


class OutputInboxSettingsError(ValueError):
    pass


def _settings_path() -> Path:
    return get_settings().app_data_dir / "settings" / "output_inbox.json"


def validate_output_directory(value: str | None) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise OutputInboxSettingsError("Output directory must be an absolute existing directory")
    raw_path = value.strip()
    if not (Path(raw_path).is_absolute() or PureWindowsPath(raw_path).is_absolute()):
        raise OutputInboxSettingsError("Output directory must be an absolute existing directory")
    # Reject foreign-platform absolute paths rather than interpreting them as local relative paths.
    if PurePosixPath(raw_path).is_absolute() and not Path(raw_path).is_absolute():
        raise OutputInboxSettingsError("Output directory must be an absolute existing directory")
    directory = Path(raw_path)
    if not directory.is_dir():
        raise OutputInboxSettingsError("Output directory must be an absolute existing directory")
    return directory.resolve()


def load_output_inbox_settings() -> str | None:
    path = _settings_path()
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("output_dir"), str):
        raise OutputInboxSettingsError("Output inbox settings are invalid")
    return data["output_dir"]


def save_output_inbox_settings(value: str | None) -> str:
    directory = validate_output_directory(value)
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_name(f"{path.name}.{uuid4().hex}.tmp")
    try:
        temporary_path.write_text(
            json.dumps({"output_dir": str(directory)}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)
    return str(directory)
