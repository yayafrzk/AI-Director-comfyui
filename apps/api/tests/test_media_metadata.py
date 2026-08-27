import json
import subprocess

import pytest

import app.services.media_metadata as media_metadata


def _completed(payload: object, returncode: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["ffprobe"], returncode, json.dumps(payload), "")


def test_probe_video_metadata_reads_video_dimensions_and_format_duration(monkeypatch, tmp_path) -> None:
    captured = {}

    def run(command, **kwargs):
        captured["command"] = command
        captured["kwargs"] = kwargs
        return _completed({"streams": [{"codec_type": "video", "width": 1920, "height": 1080}], "format": {"duration": "5.125"}})

    monkeypatch.setattr(media_metadata.subprocess, "run", run)
    path = tmp_path / "含 空格" / "视频.mp4"

    assert media_metadata.probe_video_metadata(path) == media_metadata.VideoMetadata(1920, 1080, 5.125)
    assert captured["command"][-1] == str(path)
    assert captured["command"][:2] == ["ffprobe", "-v"]
    assert captured["kwargs"] == {"capture_output": True, "text": True, "timeout": 15, "check": False}


def test_probe_video_metadata_skips_audio_and_uses_stream_duration(monkeypatch, tmp_path) -> None:
    payload = {"streams": [{"codec_type": "audio"}, {"codec_type": "video", "width": 1280, "height": 720, "duration": "2.5"}], "format": {"duration": "invalid"}}
    monkeypatch.setattr(media_metadata.subprocess, "run", lambda *_args, **_kwargs: _completed(payload))

    assert media_metadata.probe_video_metadata(tmp_path / "clip.mp4") == media_metadata.VideoMetadata(1280, 720, 2.5)


@pytest.mark.parametrize("result", [
    _completed({}, returncode=1),
    subprocess.CompletedProcess(["ffprobe"], 0, "not json", ""),
    _completed({"streams": [{"codec_type": "audio"}], "format": {"duration": "1"}}),
    _completed({"streams": [{"codec_type": "video", "width": 0, "height": 720}], "format": {"duration": "1"}}),
    _completed({"streams": [{"codec_type": "video", "width": 1280, "height": 720}], "format": {"duration": "bad"}}),
])
def test_probe_video_metadata_rejects_invalid_results(monkeypatch, tmp_path, result) -> None:
    monkeypatch.setattr(media_metadata.subprocess, "run", lambda *_args, **_kwargs: result)
    with pytest.raises(media_metadata.VideoMetadataProbeError):
        media_metadata.probe_video_metadata(tmp_path / "invalid.mp4")


@pytest.mark.parametrize("error_type", [FileNotFoundError, subprocess.TimeoutExpired])
def test_probe_video_metadata_converts_process_errors(monkeypatch, tmp_path, error_type) -> None:
    def fail(*_args, **_kwargs):
        if error_type is FileNotFoundError:
            raise FileNotFoundError("ffprobe")
        raise subprocess.TimeoutExpired("ffprobe", 15)

    monkeypatch.setattr(media_metadata.subprocess, "run", fail)
    expected = media_metadata.FFprobeNotFoundError if error_type is FileNotFoundError else media_metadata.VideoMetadataProbeError
    with pytest.raises(expected):
        media_metadata.probe_video_metadata(tmp_path / "clip.mp4")
