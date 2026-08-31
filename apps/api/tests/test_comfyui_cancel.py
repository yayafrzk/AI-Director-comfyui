import asyncio

import httpx
import pytest

import app.services.comfyui_client as comfyui_client
from app.services.comfyui_client import ComfyUIClientError, cancel_prompt


class StubAsyncClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, url, json=None):
        self.calls.append((url, json))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def test_cancel_prompt_uses_prompt_specific_jobs_endpoint(monkeypatch):
    client = StubAsyncClient(httpx.Response(200, json={"cancelled": True}))
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_kwargs: client)

    asyncio.run(cancel_prompt("prompt-1", allow_queue_fallback=False))

    assert client.calls == [("http://127.0.0.1:8188/api/jobs/prompt-1/cancel", None)]


def test_queued_cancel_falls_back_to_exact_queue_delete(monkeypatch):
    jobs_client = StubAsyncClient(httpx.Response(404))
    queue_client = StubAsyncClient(httpx.Response(200, json={}))
    clients = [jobs_client, queue_client]
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_kwargs: clients.pop(0))

    asyncio.run(cancel_prompt("prompt-1", allow_queue_fallback=True))

    assert jobs_client.calls == [("http://127.0.0.1:8188/api/jobs/prompt-1/cancel", None)]
    assert queue_client.calls == [("http://127.0.0.1:8188/queue", {"delete": ["prompt-1"]})]


def test_running_cancel_never_falls_back_to_global_interrupt(monkeypatch):
    client = StubAsyncClient(httpx.Response(404))
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(ComfyUIClientError) as error:
        asyncio.run(cancel_prompt("prompt-1", allow_queue_fallback=False))

    assert error.value.code == "COMFYUI_RUNNING_CANCEL_UNSUPPORTED"
    assert client.calls == [("http://127.0.0.1:8188/api/jobs/prompt-1/cancel", None)]

def test_targeted_cancel_false_is_not_success(monkeypatch):
    client = StubAsyncClient(httpx.Response(200, json={"cancelled": False}))
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(ComfyUIClientError) as error:
        asyncio.run(cancel_prompt("prompt-1", allow_queue_fallback=True))

    assert error.value.code == "COMFYUI_CANCEL_NOT_APPLIED"
    assert client.calls == [("http://127.0.0.1:8188/api/jobs/prompt-1/cancel", None)]


@pytest.mark.parametrize("response", [httpx.Response(500), httpx.TimeoutException("timeout")])
def test_queued_cancel_failures_never_fall_back_to_queue(monkeypatch, response):
    client = StubAsyncClient(response)
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_kwargs: client)

    with pytest.raises(ComfyUIClientError):
        asyncio.run(cancel_prompt("prompt-1", allow_queue_fallback=True))

    assert client.calls == [("http://127.0.0.1:8188/api/jobs/prompt-1/cancel", None)]


def test_cancel_client_has_no_global_interrupt_fallback():
    source = __import__("pathlib").Path(comfyui_client.__file__).read_text(encoding="utf-8")
    assert '"interrupt"' not in source
    assert '"/interrupt"' not in source
