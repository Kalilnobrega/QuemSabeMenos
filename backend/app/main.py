import asyncio
import os
import time
from contextlib import suppress

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
    SubmitAnswerRequest,
    UpdateSettingsRequest,
)
from app import game as rules
from app.rooms import Player, Room, RoomError, RoomManager

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
# Tempo que um jogador desconectado continua na sala esperando voltar.
RECONNECT_GRACE_SECONDS = float(os.getenv("RECONNECT_GRACE_SECONDS", "30"))

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ORIGINS)
rooms = RoomManager()
# Sinaliza que todos os conectados já responderam, para encerrar a rodada antes do tempo.
round_done: dict[str, asyncio.Event] = {}

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


def check_round_done(room: Room) -> None:
    game = room.game
    if game and game.phase == "answering" and game.everyone_answered(room.connected_ids()):
        if event := round_done.get(room.code):
            event.set()


async def leave_current_room(sid: str) -> None:
    found = rooms.session(sid)
    if not found:
        return
    await sio.leave_room(sid, found[0].code)
    if room := rooms.leave(sid):
        check_round_done(room)
        await broadcast(room)


async def expire_later(code: str, player_id: str, disconnect_seq: int) -> None:
    await asyncio.sleep(RECONNECT_GRACE_SECONDS)
    if room := rooms.expire(code, player_id, disconnect_seq):
        check_round_done(room)
        await broadcast(room)


async def run_game(room: Room) -> None:
    """Conduz a partida: leitura → respostas → resultado, rodada a rodada.

    A primeira rodada já vem iniciada por rooms.start.
    """
    game = room.game
    done = round_done[room.code] = asyncio.Event()

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.game is game

    try:
        while alive():
            done.clear()
            await broadcast(room)
            if game.phase in rules.PREPARATION_PHASES:
                await asyncio.sleep(game.phase_ends_at - time.monotonic())
                if not alive():
                    return
                game.begin_reading(time.monotonic())
                await broadcast(room)
            await asyncio.sleep(game.phase_ends_at - time.monotonic())
            if not alive():
                return

            game.open_answers(time.monotonic())
            await broadcast(room)
            if not game.everyone_answered(room.connected_ids()):
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), game.answer_seconds)
            if not alive():
                return

            game.close_round(room.players, time.monotonic())
            await broadcast(room)
            await asyncio.sleep(game.phase_ends_at - time.monotonic())
            if not alive():
                return
            if not game.has_next_round:
                game.finish(time.monotonic())
                await broadcast(room)
                return
            game.start_round(time.monotonic())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]


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
async def update_settings(sid: str, data: dict) -> dict:
    try:
        request = UpdateSettingsRequest.model_validate(data)
        room = rooms.update_settings(
            sid, request.rounds, request.themes, request.answer_seconds, request.speed_grace_seconds
        )
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def start_game(sid: str) -> dict:
    try:
        room = rooms.start(sid)
    except RoomError as e:
        return error(str(e))
    sio.start_background_task(run_game, room)
    return OkAck().model_dump()


@sio.event
async def submit_answer(sid: str, data: dict) -> dict:
    try:
        request = SubmitAnswerRequest.model_validate(data)
        room = rooms.answer(sid, request.option, time.monotonic())
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    check_round_done(room)
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def play_again(sid: str) -> dict:
    try:
        room = rooms.play_again(sid)
    except RoomError as e:
        return error(str(e))
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def disconnect(sid: str, reason: str | None = None) -> None:
    if found := rooms.disconnect(sid):
        room, player, seq = found
        check_round_done(room)
        await broadcast(room)
        sio.start_background_task(expire_later, room.code, player.id, seq)


app = socketio.ASGIApp(sio, other_asgi_app=api)
