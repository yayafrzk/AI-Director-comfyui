import re
from pathlib import Path
from types import SimpleNamespace

import app.core.logging as logging_system


def _close_loggers(loggers) -> None:
    for logger in loggers.values():
        for handler in list(logger.handlers):
            if getattr(handler, "_ai_director_logging_handler", False):
                logger.removeHandler(handler)
                handler.close()


def test_loggers_write_utf8_files_with_metadata(tmp_path) -> None:
    log_dir = tmp_path / "logs"
    loggers = logging_system.setup_logging(log_dir)
    messages = {
        "app": ("应用启动", "INFO"),
        "comfyui": ("ComfyUI 连接配置已加载", "WARNING"),
        "generation": ("生成任务失败", "ERROR"),
    }

    try:
        loggers["app"].info(messages["app"][0])
        loggers["comfyui"].warning(messages["comfyui"][0])
        loggers["generation"].error(
            messages["generation"][0],
            extra={
                "job_id": "job-1",
                "project_id": "project-1",
                "scene_id": "scene-1",
                "comfyui_prompt_id": "prompt-1",
            },
        )

        for name, (message, level) in messages.items():
            log_file = log_dir / f"{name}.log"
            assert log_file.exists()
            content = log_file.read_text(encoding="utf-8")
            line = next(line for line in content.splitlines() if message in line)

            assert re.match(
                rf"^\d{{4}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}}:\d{{2}} {level} {name} ",
                line,
            )
            assert loggers[name].propagate is False
            for other_name, (other_message, _) in messages.items():
                if other_name != name:
                    assert other_message not in content
    finally:
        _close_loggers(loggers)


def test_default_log_dir_uses_configured_data_parent(monkeypatch, tmp_path) -> None:
    fake_settings = SimpleNamespace(app_data_dir=tmp_path / "data")
    monkeypatch.setattr(logging_system, "get_settings", lambda: fake_settings)
    loggers = logging_system.setup_logging()

    try:
        loggers["app"].info("默认日志目录")
        assert (tmp_path / "logs" / "app.log").exists()
    finally:
        _close_loggers(loggers)


def test_repeated_setup_does_not_duplicate_handlers(tmp_path) -> None:
    log_dir = Path(tmp_path) / "logs"
    first_loggers = logging_system.setup_logging(log_dir)

    try:
        second_loggers = logging_system.setup_logging(log_dir)
        second_loggers["app"].info("只写一次")
        second_loggers["app"].handlers[0].flush()

        content = (log_dir / "app.log").read_text(encoding="utf-8")
        assert content.count("只写一次") == 1
        managed_handlers = [
            handler
            for handler in second_loggers["app"].handlers
            if getattr(handler, "_ai_director_logging_handler", False)
        ]
        assert len(managed_handlers) == 1
        assert logging_system.get_logger("app") is second_loggers["app"]
    finally:
        _close_loggers(first_loggers)
