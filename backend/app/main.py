import asyncio
import os
import time

import socketio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.events import (
    CreateRoomRequest,
    ErrorAck,
    JoinedAck,
    JoinRoomRequest,
    OkAck,
    Pong,
    RejoinRoomRequest,
)
from app.rooms import Player, Room, RoomError, RoomManager

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
# Tempo que um jogador desconectado continua na sala esperando voltar.
RECONNECT_GRACE_SECONDS = float(os.getenv("RECONNECT_GRACE_SECONDS", "30"))

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ORIGINS)
rooms = RoomManager()

api = FastAPI(title="Quem Sabe Menos?")
api.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def error(message: str) -> dict:
    return ErrorAck(error=message).model_dump()


async def broadcast(room: Room) -> None:
    await sio.emit("room_state", room.view().model_dump(), to=room.code)


async def joined(sid: str, room: Room, player: Player) -> dict:
    await sio.enter_room(sid, room.code)
    await broadcast(room)
    return JoinedAck(player_id=player.id, token=player.token, room=room.view()).model_dump()


async def leave_current_room(sid: str) -> None:
    found = rooms.session(sid)
    if not found:
        return
    await sio.leave_room(sid, found[0].code)
    if room := rooms.leave(sid):
        await broadcast(room)


async def expire_later(code: str, player_id: str, disconnect_seq: int) -> None:
    await asyncio.sleep(RECONNECT_GRACE_SECONDS)
    if room := rooms.expire(code, player_id, disconnect_seq):
        await broadcast(room)


@sio.event
async def ping_server(sid: str) -> dict:
    return Pong(server_time=time.time()).model_dump()


@sio.event
async def create_room(sid: str, data: dict) -> dict:
    try:
        request = CreateRoomRequest.model_validate(data)
        await leave_current_room(sid)
        room, player = rooms.create(sid, request)
    except ValidationError:
        return error("Apelido ou avatar inválido.")
    except RoomError as e:
        return error(str(e))
    return await joined(sid, room, player)


@sio.event
async def join_room(sid: str, data: dict) -> dict:
    try:
        request = JoinRoomRequest.model_validate(data)
        await leave_current_room(sid)
        room, player = rooms.join(sid, request.code, request)
    except ValidationError:
        return error("Apelido ou avatar inválido.")
    except RoomError as e:
        return error(str(e))
    return await joined(sid, room, player)


@sio.event
async def rejoin_room(sid: str, data: dict) -> dict:
    try:
        request = RejoinRoomRequest.model_validate(data)
        current = rooms.session(sid)
        if current and current[1].token != request.token:
            await leave_current_room(sid)
        room, player, old_sid = rooms.rejoin(sid, request.code, request.token)
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    if old_sid:
        await sio.leave_room(old_sid, room.code)
    return await joined(sid, room, player)


@sio.event
async def leave_room(sid: str) -> dict:
    await leave_current_room(sid)
    return OkAck().model_dump()


@sio.event
async def start_game(sid: str) -> dict:
    try:
        room = rooms.start(sid)
    except RoomError as e:
        return error(str(e))
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def disconnect(sid: str, reason: str | None = None) -> None:
    if found := rooms.disconnect(sid):
        room, player, seq = found
        await broadcast(room)
        sio.start_background_task(expire_later, room.code, player.id, seq)


app = socketio.ASGIApp(sio, other_asgi_app=api)
