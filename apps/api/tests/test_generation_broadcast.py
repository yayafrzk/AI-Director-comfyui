import asyncio

from fastapi.testclient import TestClient

from app.main import app
import app.services.generation_broadcast as broadcast


class Socket:
    def __init__(self, fail=False):
        self.accepted = False
        self.events = []
        self.fail = fail

    async def accept(self):
        self.accepted = True

    async def send_json(self, event):
        if self.fail:
            raise OSError("closed")
        self.events.append(event)


def setup_function():
    broadcast._connections.clear()


def teardown_function():
    broadcast._connections.clear()


def test_generation_websocket_connects_and_receives_running_event():
    event = {"type": "generation.running", "job_id": "job-1", "scene_id": "scene-1", "status": "running"}
    with TestClient(app) as client:
        with client.websocket_connect("/ws/generation") as websocket:
            asyncio.run(broadcast.broadcast_generation_event(event))
            assert websocket.receive_json() == event


def test_broadcast_handles_no_clients_disconnects_and_failed_sockets():
    asyncio.run(broadcast.broadcast_generation_event({"type": "generation.running"}))
    broken, healthy = Socket(fail=True), Socket()
    asyncio.run(broadcast.connect_generation_socket(broken))
    asyncio.run(broadcast.connect_generation_socket(healthy))
    event = {"type": "generation.running", "job_id": "job-1", "scene_id": "scene-1", "status": "running"}
    asyncio.run(broadcast.broadcast_generation_event(event))
    assert healthy.events == [event]
    assert broken not in broadcast._connections
    broadcast.disconnect_generation_socket(healthy)
    assert healthy not in broadcast._connections
