import json

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.comfyui import ComfyUIHealthRead


_logger = get_logger("comfyui")
_HEALTH_TIMEOUT_SECONDS = 3.0


def _system_stats_url() -> str:
    return f"{get_settings().comfyui_base_url.rstrip('/')}/system_stats"


def _offline(url: str, category: str) -> ComfyUIHealthRead:
    _logger.warning("ComfyUI health check offline target=%s category=%s", url, category)
    return ComfyUIHealthRead(status="offline")


async def check_health() -> ComfyUIHealthRead:
    url = _system_stats_url()
    try:
        async with httpx.AsyncClient(timeout=_HEALTH_TIMEOUT_SECONDS) as client:
            response = await client.get(url)
    except httpx.TimeoutException:
        return _offline(url, "timeout")
    except httpx.ConnectError:
        return _offline(url, "connection")
    except httpx.HTTPError:
        return _offline(url, "http_error")

    if not response.is_success:
        return _offline(url, f"http_{response.status_code}")

    try:
        response.json()
    except (json.JSONDecodeError, ValueError):
        return _offline(url, "invalid_json")

    return ComfyUIHealthRead(status="online")
