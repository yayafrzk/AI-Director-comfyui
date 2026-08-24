from __future__ import annotations

import logging
from pathlib import Path

from app.core.config import get_settings


_LOG_FILES = {
    "app": "app.log",
    "comfyui": "comfyui.log",
    "generation": "generation.log",
}
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_HANDLER_MARKER = "_ai_director_logging_handler"


def _resolve_log_dir(log_dir: Path | str | None) -> Path:
    if log_dir is None:
        log_dir = get_settings().app_data_dir.parent / "logs"
    return Path(log_dir).expanduser().resolve()


def _is_same_log_file(handler: logging.Handler, log_file: Path) -> bool:
    if not isinstance(handler, logging.FileHandler):
        return False
    return Path(handler.baseFilename).resolve() == log_file


def _configure_logger(name: str, log_file: Path) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    existing_handler: logging.FileHandler | None = None
    for handler in list(logger.handlers):
        if _is_same_log_file(handler, log_file):
            if existing_handler is None:
                existing_handler = handler
                existing_handler.setLevel(logging.INFO)
                existing_handler.setFormatter(
                    logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)
                )
                setattr(existing_handler, _HANDLER_MARKER, True)
            else:
                logger.removeHandler(handler)
                handler.close()
        elif getattr(handler, _HANDLER_MARKER, False):
            logger.removeHandler(handler)
            handler.close()

    if existing_handler is None:
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)

    return logger


def setup_logging(log_dir: Path | str | None = None) -> dict[str, logging.Logger]:
    """Initialize and return the three AI Director loggers."""
    resolved_log_dir = _resolve_log_dir(log_dir)
    resolved_log_dir.mkdir(parents=True, exist_ok=True)

    return {
        name: _configure_logger(name, resolved_log_dir / filename)
        for name, filename in _LOG_FILES.items()
    }


def get_logger(name: str) -> logging.Logger:
    """Return one of the configured logger names without adding handlers."""
    if name not in _LOG_FILES:
        raise ValueError(f"Unknown AI Director logger: {name}")
    return logging.getLogger(name)
