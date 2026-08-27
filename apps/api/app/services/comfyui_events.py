import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.parse import urlencode, urlsplit, urlunsplit

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.generation_job import GenerationJob


_logger = get_logger("comfyui")
_TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


def websocket_url(base_url: str, client_id: str) -> str:
    parsed = urlsplit(base_url)
    scheme = "wss" if parsed.scheme == "https" else "ws"
    return urlunsplit((scheme, parsed.netloc, "/ws", urlencode({"clientId": client_id}), ""))


def parse_event(message: str | bytes) -> dict[str, Any] | None:
    if isinstance(message, bytes):
        return None
    try:
        value = json.loads(message)
    except (TypeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data", event)
    return data if isinstance(data, dict) else {}


def event_prompt_id(event: dict[str, Any]) -> str | None:
    prompt_id = _event_data(event).get("prompt_id")
    return prompt_id if isinstance(prompt_id, str) else None


def apply_event(job_id: str, event: dict[str, Any]) -> None:
    """Apply one matching ComfyUI lifecycle event with a short-lived session."""
    prompt_id = event_prompt_id(event)
    if prompt_id is None:
        return

    session = SessionLocal()
    try:
        job = session.get(GenerationJob, job_id)
        if job is None or job.comfy_prompt_id != prompt_id or job.status in _TERMINAL_STATUSES:
            return

        now = datetime.now(timezone.utc)
        event_type = event.get("type")
        data = _event_data(event)
        if event_type in {"execution_start", "executing"}:
            job.status = "running"
            job.started_at = job.started_at or now
        elif event_type == "execution_success":
            job.status = "completed"
            job.finished_at = now
        elif event_type == "execution_interrupted":
            job.status = "cancelled"
            job.finished_at = now
        elif event_type == "execution_error":
            message = str(data.get("exception_message", "Execution failed"))[:2000]
            job.status = "failed"
            job.error_code = "CUDA_OOM" if "cuda out of memory" in message.lower() else "EXECUTION_FAILED"
            job.error_message = message
            job.finished_at = now
        else:
            return
        session.commit()
    finally:
        session.close()


async def listen_for_generation(
    job_id: str,
    client_id: str,
    prompt_id_future: asyncio.Future[str],
    connect: Callable[[str], Any] | None = None,
) -> None:
    """Listen for one submission without allowing transport failures to change job state."""
    url = websocket_url(get_settings().comfyui_base_url, client_id)
    if connect is None:
        try:
            import websockets
        except ImportError:
            _logger.warning("ComfyUI event listener unavailable: websockets dependency is not installed")
            return
        connect = websockets.connect

    try:
        async with connect(url) as websocket:
            prompt_id = await prompt_id_future
            async for message in websocket:
                event = parse_event(message)
                if event is None or event_prompt_id(event) != prompt_id:
                    continue
                apply_event(job_id, event)
    except asyncio.CancelledError:
        raise
    except Exception as error:
        _logger.warning("ComfyUI event listener disconnected job_id=%s error=%s", job_id, error)
