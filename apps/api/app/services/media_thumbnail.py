from __future__ import annotations

import math
import os
import subprocess
from pathlib import Path

from app.core.logging import get_logger


FFMPEG_TIMEOUT_SECONDS = 15
THUMBNAIL_WIDTH = 480
_logger = get_logger("app")


class VideoThumbnailError(RuntimeError):
    """Raised when FFmpeg cannot create a usable video thumbnail."""


class FFmpegNotFoundError(VideoThumbnailError):
    """Raised when ffmpeg is not available on PATH."""


def thumbnail_timestamp(duration_seconds: float) -> float:
    if not math.isfinite(duration_seconds) or duration_seconds <= 0:
        return 0.0
    return min(1.0, duration_seconds * 0.1)


def _cleanup(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _failure(category: str, temporary_path: Path, output_path: Path) -> VideoThumbnailError:
    _cleanup(temporary_path)
    _cleanup(output_path)
    _logger.warning("ffmpeg thumbnail generation failed: category=%s", category)
    return VideoThumbnailError(category)


def generate_video_thumbnail(
    video_path: Path,
    output_path: Path,
    duration_seconds: float,
) -> None:
    """Extract one scaled JPEG frame and atomically publish it at output_path."""
    temporary_path = output_path.with_name(f"{output_path.stem}.tmp{output_path.suffix}")
    timestamp = thumbnail_timestamp(duration_seconds)
    command = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-vf",
        f"scale={THUMBNAIL_WIDTH}:-2",
        "-q:v",
        "2",
        str(temporary_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=FFMPEG_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:
        _cleanup(temporary_path)
        _cleanup(output_path)
        _logger.error("ffmpeg thumbnail generation unavailable: category=not_found")
        raise FFmpegNotFoundError("ffmpeg is not available") from error
    except subprocess.TimeoutExpired as error:
        raise _failure("timeout", temporary_path, output_path) from error
    except OSError as error:
        raise _failure("execution_error", temporary_path, output_path) from error

    if result.returncode != 0:
        raise _failure("nonzero_exit", temporary_path, output_path)
    if not temporary_path.is_file():
        raise _failure("output_missing", temporary_path, output_path)
    if temporary_path.stat().st_size <= 0:
        raise _failure("output_empty", temporary_path, output_path)

    try:
        os.replace(temporary_path, output_path)
    except OSError as error:
        raise _failure("output_publish_failed", temporary_path, output_path) from error
