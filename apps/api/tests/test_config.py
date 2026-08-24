from pathlib import Path

from app.core.config import Settings, get_settings


def _clear_config_environment(monkeypatch) -> None:
    for name in (
        "APP_DATA_DIR",
        "app_data_dir",
        "COMFYUI_BASE_URL",
        "comfyui_base_url",
    ):
        monkeypatch.delenv(name, raising=False)


def test_default_settings(monkeypatch) -> None:
    _clear_config_environment(monkeypatch)

    settings = get_settings()
    expected_data_dir = Path(__file__).resolve().parents[3] / "data"

    assert settings.app_data_dir == expected_data_dir
    assert settings.app_data_dir.is_absolute()
    assert settings.comfyui_base_url == "http://127.0.0.1:8188"


def test_environment_variables_override_defaults(monkeypatch, tmp_path) -> None:
    custom_data_dir = tmp_path / "custom-data"
    monkeypatch.setenv("APP_DATA_DIR", str(custom_data_dir))
    monkeypatch.setenv("COMFYUI_BASE_URL", "http://127.0.0.1:9999")

    settings = Settings()

    assert settings.app_data_dir == custom_data_dir
    assert settings.comfyui_base_url == "http://127.0.0.1:9999"
