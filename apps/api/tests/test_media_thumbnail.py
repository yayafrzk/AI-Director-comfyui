import subprocess
from pathlib import Path

import pytest

import app.services.media_thumbnail as media_thumbnail
from app.services.storage_assets import create_thumbnail_file


@pytest.mark.parametrize(
    ("duration_seconds", "expected"),
    [(10.0, 1.0), (1.0, 0.1), (0.2, 0.02), (0.0, 0.0)],
)
def test_thumbnail_timestamp_is_valid(duration_seconds: float, expected: float) -> None:
    assert media_thumbnail.thumbnail_timestamp(duration_seconds) == pytest.approx(expected)


def test_generate_thumbnail_uses_argv_and_atomically_publishes_output(monkeypatch, tmp_path) -> None:
    captured = {}
    video_path = tmp_path / "视频 文件.mp4"
    output_path = tmp_path / "thumbnail.jpg"

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        Path(command[-1]).write_bytes(b"jpeg-bytes")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media_thumbnail.subprocess, "run", run)
    media_thumbnail.generate_video_thumbnail(video_path, output_path, 10.0)

    assert output_path.read_bytes() == b"jpeg-bytes"
    assert captured["command"][0] == "ffmpeg"
    assert captured["command"][captured["command"].index("-ss") + 1] == "1.000"
    assert captured["command"][-1].endswith(".tmp.jpg")
    assert captured["kwargs"] == {"capture_output": True, "text": True, "timeout": 15, "check": False}


@pytest.mark.parametrize(
    "result",
    [
        subprocess.CompletedProcess(["ffmpeg"], 1, "", ""),
        subprocess.CompletedProcess(["ffmpeg"], 0, "", ""),
    ],
)
def test_generate_thumbnail_rejects_nonzero_or_missing_output(monkeypatch, tmp_path, result) -> None:
    monkeypatch.setattr(media_thumbnail.subprocess, "run", lambda *_args, **_kwargs: result)
    output_path = tmp_path / "thumbnail.jpg"

    with pytest.raises(media_thumbnail.VideoThumbnailError):
        media_thumbnail.generate_video_thumbnail(tmp_path / "video.mp4", output_path, 1.0)
    assert not output_path.exists()


def test_generate_thumbnail_rejects_empty_output(monkeypatch, tmp_path) -> None:
    def run(command, **_kwargs):
        Path(command[-1]).touch()
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(media_thumbnail.subprocess, "run", run)
    output_path = tmp_path / "thumbnail.jpg"

    with pytest.raises(media_thumbnail.VideoThumbnailError):
        media_thumbnail.generate_video_thumbnail(tmp_path / "video.mp4", output_path, 1.0)
    assert not output_path.exists()


@pytest.mark.parametrize("error_type", [FileNotFoundError, subprocess.TimeoutExpired])
def test_generate_thumbnail_converts_process_errors(monkeypatch, tmp_path, error_type) -> None:
    def fail(*_args, **_kwargs):
        if error_type is FileNotFoundError:
            raise FileNotFoundError("ffmpeg")
        raise subprocess.TimeoutExpired("ffmpeg", 15)

    monkeypatch.setattr(media_thumbnail.subprocess, "run", fail)
    expected = media_thumbnail.FFmpegNotFoundError if error_type is FileNotFoundError else media_thumbnail.VideoThumbnailError
    with pytest.raises(expected):
        media_thumbnail.generate_video_thumbnail(tmp_path / "video.mp4", tmp_path / "thumbnail.jpg", 1.0)


def test_create_thumbnail_file_uses_unicode_app_data_and_relative_path(monkeypatch, tmp_path) -> None:
    app_data_dir = tmp_path / "素材 数据"
    monkeypatch.setenv("APP_DATA_DIR", str(app_data_dir))

    thumbnail = create_thumbnail_file("project-id")

    assert thumbnail.relative_path.startswith("thumbnails/")
    assert thumbnail.path.parent == app_data_dir / "projects" / "project-id" / "thumbnails"
    assert thumbnail.path.suffix == ".jpg"
