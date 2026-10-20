import asyncio

import pytest
import socketio

from app import main
from app.rooms import RoomManager


@pytest.fixture(autouse=True)
def fresh_rooms(monkeypatch):
    monkeypatch.setattr(main, "rooms", RoomManager())
    monkeypatch.setattr(main, "RECONNECT_GRACE_SECONDS", 0.2)


class Client:
    """Cliente Socket.IO que guarda o último room_state recebido."""

    def __init__(self) -> None:
        self.sio = socketio.AsyncClient()
        self.state: dict | None = None
        self.sio.on("room_state", self._on_state)

    async def _on_state(self, data: dict) -> None:
        self.state = data

    async def connect(self, url: str) -> "Client":
        await self.sio.connect(url, transports=["websocket"])
        return self

    async def call(self, event: str, data: dict | None = None) -> dict:
        return await self.sio.call(event, data) if data is not None else await self.sio.call(event)

    async def wait_for(self, predicate, timeout: float = 2) -> dict:
        async def poll():
            while not (self.state and predicate(self.state)):
                await asyncio.sleep(0.01)
            return self.state

        return await asyncio.wait_for(poll(), timeout)


@pytest.fixture
async def connect(server_url):
    clients: list[Client] = []

    async def factory() -> Client:
        client = await Client().connect(server_url)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        if client.sio.connected:
            await client.sio.disconnect()


def nicknames(state: dict) -> list[str]:
    return [p["nickname"] for p in state["players"]]


async def test_create_and_join_broadcasts_lobby(connect):
    ana, bia = await connect(), await connect()

    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    assert created["ok"]
    code = created["room"]["code"]

    joined = await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})
    assert joined["ok"]

    state = await ana.wait_for(lambda s: len(s["players"]) == 2)
    assert nicknames(state) == ["Ana", "Bia"]
    assert state["host_id"] == created["player_id"]


async def test_invalid_payloads_return_errors(connect):
    ana = await connect()
    bad_avatar = await ana.call("create_room", {"nickname": "Ana", "avatar": "dragao"})
    assert bad_avatar == {"ok": False, "error": "Apelido ou avatar inválido."}
    unknown = await ana.call("join_room", {"code": "ZZZZZ", "nickname": "Ana", "avatar": "gato"})
    assert not unknown["ok"]


async def test_host_leaving_passes_host(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    joined = await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    assert (await ana.call("leave_room"))["ok"]
    state = await bia.wait_for(lambda s: nicknames(s) == ["Bia"])
    assert state["host_id"] == joined["player_id"]


async def test_disconnected_player_can_rejoin(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})

    await ana.sio.disconnect()
    await bia.wait_for(lambda s: not s["players"][0]["connected"])

    ana_again = await connect()
    rejoined = await ana_again.call("rejoin_room", {"code": code, "token": created["token"]})
    assert rejoined["ok"]
    assert rejoined["player_id"] == created["player_id"]
    await bia.wait_for(lambda s: s["players"][0]["connected"])


async def test_player_who_does_not_return_is_removed(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    joined = await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    await ana.sio.disconnect()
    state = await bia.wait_for(lambda s: nicknames(s) == ["Bia"])
    assert state["host_id"] == joined["player_id"]


async def test_host_starts_game(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    assert not (await bia.call("start_game"))["ok"]
    assert (await ana.call("start_game"))["ok"]
    await bia.wait_for(lambda s: s["status"] == "playing")
