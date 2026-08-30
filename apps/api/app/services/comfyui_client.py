import json

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger
from app.schemas.comfyui import ComfyUIHealthRead


_logger = get_logger("comfyui")
_HEALTH_TIMEOUT_SECONDS = 3.0
_SUBMIT_TIMEOUT_SECONDS = 15.0


class ComfyUIClientError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _endpoint_url(path: str) -> str:
    return f"{get_settings().comfyui_base_url.rstrip('/')}/{path.lstrip('/')}"


def _offline(url: str, category: str) -> ComfyUIHealthRead:
    _logger.warning("ComfyUI health check offline target=%s category=%s", url, category)
    return ComfyUIHealthRead(status="offline")


async def check_health() -> ComfyUIHealthRead:
    url = _endpoint_url("system_stats")
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


async def submit_prompt(workflow: dict[str, object], client_id: str | None = None) -> str:
    url = _endpoint_url("prompt")
    payload = {"prompt": workflow}
    if client_id is not None:
        payload["client_id"] = client_id
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as error:
        raise ComfyUIClientError(
            "COMFYUI_REQUEST_INVALID",
            "ComfyUI prompt request is not JSON-compatible",
        ) from error

    try:
        async with httpx.AsyncClient(timeout=_SUBMIT_TIMEOUT_SECONDS) as client:
            response = await client.post(url, json=payload)
    except httpx.TimeoutException as error:
        _logger.warning("ComfyUI prompt submit failed target=%s category=timeout", url)
        raise ComfyUIClientError("COMFYUI_TIMEOUT", "ComfyUI prompt submission timed out") from error
    except httpx.ConnectError as error:
        _logger.warning("ComfyUI prompt submit failed target=%s category=connection", url)
        raise ComfyUIClientError("COMFYUI_OFFLINE", "ComfyUI is offline") from error
    except httpx.HTTPError as error:
        _logger.warning("ComfyUI prompt submit failed target=%s category=http_error", url)
        raise ComfyUIClientError(
            "COMFYUI_SUBMIT_FAILED",
            "ComfyUI prompt submission failed",
        ) from error

    if not response.is_success:
        _logger.warning(
            "ComfyUI prompt submit failed target=%s category=http_%s",
            url,
            response.status_code,
        )
        raise ComfyUIClientError(
            "COMFYUI_SUBMIT_FAILED",
            "ComfyUI prompt submission failed",
        )

    try:
        response_data = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise ComfyUIClientError(
            "COMFYUI_INVALID_RESPONSE",
            "ComfyUI returned an invalid response",
        ) from error

    prompt_id = response_data.get("prompt_id") if isinstance(response_data, dict) else None
    if not isinstance(prompt_id, str) or not prompt_id.strip():
        raise ComfyUIClientError(
            "COMFYUI_INVALID_RESPONSE",
            "ComfyUI response is missing a valid prompt_id",
        )

    _logger.info("ComfyUI prompt submitted prompt_id=%s", prompt_id)
    return prompt_id

async def get_history(prompt_id: str) -> dict[str, object]:
    try:
        async with httpx.AsyncClient(timeout=_SUBMIT_TIMEOUT_SECONDS) as client:
            response = await client.get(_endpoint_url(f"history/{prompt_id}"))
    except httpx.TimeoutException as error:
        raise ComfyUIClientError("COMFYUI_TIMEOUT", "ComfyUI history request timed out") from error
    except httpx.ConnectError as error:
        raise ComfyUIClientError("COMFYUI_OFFLINE", "ComfyUI is offline") from error
    except httpx.HTTPError as error:
        raise ComfyUIClientError("COMFYUI_SUBMIT_FAILED", "ComfyUI history request failed") from error
    if not response.is_success:
        raise ComfyUIClientError("COMFYUI_SUBMIT_FAILED", "ComfyUI history request failed")
    try:
        value = response.json()
    except (json.JSONDecodeError, ValueError) as error:
        raise ComfyUIClientError("COMFYUI_INVALID_RESPONSE", "ComfyUI returned invalid history") from error
    if not isinstance(value, dict):
        raise ComfyUIClientError("COMFYUI_INVALID_RESPONSE", "ComfyUI returned invalid history")
    return value


async def download_output(filename: str, subfolder: str, output_type: str) -> bytes:
    try:
        async with httpx.AsyncClient(timeout=_SUBMIT_TIMEOUT_SECONDS) as client:
            response = await client.get(_endpoint_url("view"), params={"filename": filename, "subfolder": subfolder, "type": output_type})
    except httpx.TimeoutException as error:
        raise ComfyUIClientError("COMFYUI_TIMEOUT", "ComfyUI output download timed out") from error
    except httpx.HTTPError as error:
        raise ComfyUIClientError("COMFYUI_SUBMIT_FAILED", "ComfyUI output download failed") from error
    if not response.is_success:
        raise ComfyUIClientError("COMFYUI_SUBMIT_FAILED", "ComfyUI output download failed")
    return response.content
