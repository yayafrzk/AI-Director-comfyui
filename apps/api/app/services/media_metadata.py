from __future__ import annotations

import json
import math
import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.logging import get_logger


FFPROBE_TIMEOUT_SECONDS = 15
_logger = get_logger("app")


@dataclass(frozen=True)
class VideoMetadata:
    width: int
    height: int
    duration_seconds: float


class VideoMetadataProbeError(RuntimeError):
    """Raised when ffprobe cannot provide valid video metadata."""


class FFprobeNotFoundError(VideoMetadataProbeError):
    """Raised when ffprobe is not available on PATH."""


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _duration(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) and parsed >= 0 else None


def _probe_error(category: str) -> VideoMetadataProbeError:
    _logger.warning("ffprobe metadata probe failed: category=%s", category)
    return VideoMetadataProbeError(category)


def probe_video_metadata(path: Path) -> VideoMetadata:
    """Read the minimum required video metadata from a finalized asset file."""
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "stream=codec_type,width,height,duration",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=FFPROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError as error:
        _logger.error("ffprobe metadata probe unavailable: category=not_found")
        raise FFprobeNotFoundError("ffprobe is not available") from error
    except subprocess.TimeoutExpired as error:
        raise _probe_error("timeout") from error
    except OSError as error:
        raise _probe_error("execution_error") from error
    if result.returncode != 0:
        raise _probe_error("nonzero_exit")
    try:
        payload = json.loads(result.stdout)
    except (TypeError, json.JSONDecodeError) as error:
        raise _probe_error("invalid_json") from error
    streams = payload.get("streams") if isinstance(payload, dict) else None
    if not isinstance(streams, list):
        raise _probe_error("missing_streams")
    selected_stream = next(
        (
            stream for stream in streams
            if isinstance(stream, dict) and stream.get("codec_type") == "video"
            and _positive_int(stream.get("width")) is not None
            and _positive_int(stream.get("height")) is not None
        ),
        None,
    )
    if selected_stream is None:
        raise _probe_error("missing_valid_video_stream")
    format_data = payload.get("format") if isinstance(payload, dict) else None
    duration_seconds = _duration(format_data.get("duration") if isinstance(format_data, dict) else None)
    if duration_seconds is None:
        duration_seconds = _duration(selected_stream.get("duration"))
    if duration_seconds is None:
        raise _probe_error("missing_valid_duration")
    return VideoMetadata(
        width=_positive_int(selected_stream["width"]),
        height=_positive_int(selected_stream["height"]),
        duration_seconds=duration_seconds,
    )
