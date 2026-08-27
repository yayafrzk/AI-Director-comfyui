import asyncio

import httpx
import pytest

import app.api.comfyui as comfyui_api
import app.services.comfyui_client as comfyui_client
from app.main import app
from app.schemas.comfyui import ComfyUIHealthRead


class StubAsyncClient:
    def __init__(self, response: httpx.Response | Exception) -> None:
        self.response = response
        self.urls: list[str] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback) -> None:
        return None

    async def get(self, url: str) -> httpx.Response:
        self.urls.append(url)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def _check_with_response(monkeypatch, response: httpx.Response | Exception) -> tuple[ComfyUIHealthRead, StubAsyncClient]:
    client = StubAsyncClient(response)
    monkeypatch.setattr(comfyui_client.httpx, "AsyncClient", lambda **_: client)
    return asyncio.run(comfyui_client.check_health()), client


def _get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            return await client.get(path)

    return asyncio.run(request())


def test_check_health_returns_online_for_successful_json(monkeypatch) -> None:
    result, _ = _check_with_response(monkeypatch, httpx.Response(200, json={"system": {}}))

    assert result.status == "online"


@pytest.mark.parametrize(
    "response",
    [
        httpx.ConnectError("connection refused"),
        httpx.TimeoutException("timeout"),
        httpx.Response(500, json={}),
        httpx.Response(404, json={}),
        httpx.Response(200, content=b"not json"),
    ],
)
def test_check_health_returns_offline_for_unhealthy_responses(monkeypatch, response) -> None:
    result, _ = _check_with_response(monkeypatch, response)

    assert result.status == "offline"


def test_check_health_uses_configured_url_without_double_slash(monkeypatch) -> None:
    monkeypatch.setenv("COMFYUI_BASE_URL", "http://192.168.1.10:8188/")
    result, client = _check_with_response(monkeypatch, httpx.Response(200, json={}))

    assert result.status == "online"
    assert client.urls == ["http://192.168.1.10:8188/system_stats"]


@pytest.mark.parametrize("status", ["online", "offline"])
def test_comfyui_health_api_returns_envelope(monkeypatch, status: str) -> None:
    async def stub_check_health() -> ComfyUIHealthRead:
        return ComfyUIHealthRead(status=status)

    monkeypatch.setattr(comfyui_api, "check_health", stub_check_health)

    response = _get("/api/v1/comfyui/health")

    assert response.status_code == 200
    assert response.json() == {"data": {"status": status}, "error": None}
