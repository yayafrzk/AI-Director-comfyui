import asyncio
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

import app.services.comfyui_client as comfyui_client
from app.services.comfyui_client import ComfyUIClientError, submit_prompt


class StubAsyncClient:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.url: str | None = None
        self.payload: dict[str, object] | None = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def post(self, url: str, json: dict[str, object]) -> httpx.Response:
        self.url = url
        self.payload = json
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _workflow() -> dict[str, object]:
    return {
        "12": {
            "class_type": "CLIPTextEncode",
            "inputs": {"text": "一二和布布在湖边"},
        }
    }


def _submit_with_response(monkeypatch, response: httpx.Response | Exception) -> tuple[str, StubAsyncClient]:
    client = StubAsyncClient(response)
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_: client)
    return asyncio.run(submit_prompt(_workflow())), client


def _assert_error(code: str, monkeypatch, response: httpx.Response | Exception) -> None:
    client = StubAsyncClient(response)
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_: client)

    with pytest.raises(ComfyUIClientError) as error:
        asyncio.run(submit_prompt(_workflow()))
    assert error.value.code == code


def test_submit_prompt_posts_workflow_and_returns_prompt_id(monkeypatch) -> None:
    workflow = _workflow()
    original_workflow = deepcopy(workflow)
    client = StubAsyncClient(httpx.Response(200, json={"prompt_id": "abc-123"}))
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_: client)

    prompt_id = asyncio.run(submit_prompt(workflow))

    assert prompt_id == "abc-123"
    assert client.url == "http://127.0.0.1:8188/prompt"
    assert client.payload == {"prompt": workflow}
    assert workflow == original_workflow


def test_submit_prompt_includes_client_id_only_when_supplied(monkeypatch) -> None:
    workflow = _workflow()
    client = StubAsyncClient(httpx.Response(200, json={"prompt_id": "id"}))
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_: client)

    asyncio.run(submit_prompt(workflow, client_id="client-1"))

    assert client.payload == {"prompt": workflow, "client_id": "client-1"}

def test_submit_prompt_uses_configured_url_without_double_slash(monkeypatch) -> None:
    monkeypatch.setenv("COMFYUI_BASE_URL", "http://192.168.1.10:8188/")
    _, client = _submit_with_response(monkeypatch, httpx.Response(200, json={"prompt_id": "id"}))

    assert client.url == "http://192.168.1.10:8188/prompt"


@pytest.mark.parametrize(
    ("code", "response"),
    [
        ("COMFYUI_OFFLINE", httpx.ConnectError("connection refused")),
        ("COMFYUI_TIMEOUT", httpx.TimeoutException("timeout")),
        ("COMFYUI_SUBMIT_FAILED", httpx.Response(400, json={})),
        ("COMFYUI_SUBMIT_FAILED", httpx.Response(500, json={})),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, content=b"not json")),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, json={})),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, json={"prompt_id": None})),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, json={"prompt_id": ""})),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, json={"prompt_id": 1})),
        ("COMFYUI_INVALID_RESPONSE", httpx.Response(200, json=[])),
    ],
)
def test_submit_prompt_normalizes_unhealthy_responses(monkeypatch, code: str, response) -> None:
    _assert_error(code, monkeypatch, response)


def test_submit_prompt_rejects_non_json_compatible_workflow() -> None:
    workflow = {"12": {"inputs": {"path": Path("input.png")}}}

    with pytest.raises(ComfyUIClientError) as error:
        asyncio.run(submit_prompt(workflow))

    assert error.value.code == "COMFYUI_REQUEST_INVALID"
