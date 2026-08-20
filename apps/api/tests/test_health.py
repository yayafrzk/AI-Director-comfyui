import asyncio

import httpx

from app.main import app


def get(path: str) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://testserver",
        ) as client:
            return await client.get(path)

    return asyncio.run(request())


def test_health() -> None:
    response = get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "data": {
            "status": "ok",
        },
        "error": None,
    }


def test_docs() -> None:
    response = get("/docs")

    assert response.status_code == 200
