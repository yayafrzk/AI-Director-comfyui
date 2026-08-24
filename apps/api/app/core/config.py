from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


_REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_APP_DATA_DIR = _REPOSITORY_ROOT / "data"


class Settings(BaseSettings):
    app_data_dir: Path = _DEFAULT_APP_DATA_DIR
    comfyui_base_url: str = "http://127.0.0.1:8188"

    model_config = SettingsConfigDict(
        env_file=None,
        env_prefix="",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()
