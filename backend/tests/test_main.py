import time

import httpx
import socketio


async def test_health(server_url):
    async with httpx.AsyncClient(base_url=server_url) as client:
        response = await client.get("/health")
    assert response.json() == {"status": "ok"}


async def test_ping_server_returns_server_time(server_url):
    async with socketio.AsyncSimpleClient() as client:
        await client.connect(server_url)
        pong = await client.call("ping_server")
    assert abs(pong["server_time"] - time.time()) < 5
