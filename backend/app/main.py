import asyncio
import logging
import os
import secrets
import time
from contextlib import suppress
from pathlib import Path

import socketio
from fastapi import FastAPI, Header, HTTPException, Response
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
    ArmPowerUpRequest,
    SubmitAnswerRequest,
    SubmitBetRequest,
    UpdateSettingsRequest,
    UsePowerUpRequest,
)
from app import game as rules
from app.history import MatchHistory
from app.rooms import Player, Room, RoomError, RoomManager

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
# Tempo que um jogador desconectado continua na sala esperando voltar.
RECONNECT_GRACE_SECONDS = float(os.getenv("RECONNECT_GRACE_SECONDS", "30"))
# No Railway, apontar para um Volume (ex.: /data/matches.db): o disco comum some a cada deploy.
HISTORY_DB = os.getenv("HISTORY_DB", str(Path(__file__).resolve().parents[1] / "matches.db"))
# Sem token, a rota de download do histórico fica desligada.
HISTORY_TOKEN = os.getenv("HISTORY_TOKEN", "")

logger = logging.getLogger(__name__)

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins=CORS_ORIGINS)
rooms = RoomManager()
history = MatchHistory(HISTORY_DB)
# Sinaliza que todos os conectados já responderam (ou apostaram, ou pularam a revelação),
# para encerrar a fase antes do tempo.
round_done: dict[str, asyncio.Event] = {}

api = FastAPI(title="Quem Sabe Menos?")
api.add_middleware(CORSMiddleware, allow_origins=CORS_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@api.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@api.get("/history.db")
async def download_history(authorization: str = Header("")) -> Response:
    """O banco do histórico inteiro. Pede `Authorization: Bearer <HISTORY_TOKEN>`."""
    if not HISTORY_TOKEN or not secrets.compare_digest(authorization, f"Bearer {HISTORY_TOKEN}"):
        raise HTTPException(status_code=404)
    return Response(history.snapshot(), media_type="application/vnd.sqlite3")


def record(action, *args):
    """Grava no histórico sem deixar um erro de disco derrubar a partida."""
    try:
        return action(*args)
    except Exception:
        logger.exception("Falha ao gravar o histórico da partida")
        return None


def error(message: str) -> dict:
    return ErrorAck(error=message).model_dump()


async def broadcast(room: Room) -> None:
    """Cada jogador recebe o próprio estado: as habilidades de cada um são secretas."""
    now = time.monotonic()
    for player in room.players:
        if player.sid:
            await sio.emit("room_state", room.view(now, player.id).model_dump(), to=player.sid)


async def joined(sid: str, room: Room, player: Player) -> dict:
    await sio.enter_room(sid, room.code)
    await broadcast(room)
    return JoinedAck(player_id=player.id, token=player.token, room=room.view(viewer=player.id)).model_dump()


def check_round_done(room: Room) -> None:
    game = room.game
    if not game:
        return
    connected = [p for p in room.players if p.connected]
    if (
        (game.phase == "answering" and game.everyone_answered(room.connected_ids()))
        or (game.phase == "betting" and game.everyone_bet(connected))
        or (game.phase == "results" and game.everyone_ready(room.connected_ids()))
    ):
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
    match_id = record(history.start, room, time.time())

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.game is game

    try:
        while alive():
            done.clear()
            if game.phase == "betting" and game.everyone_bet([p for p in room.players if p.connected]):
                game.begin_reading(time.monotonic())  # ninguém tem QI para apostar: nem mostra a aposta
            await broadcast(room)
            if game.phase == "betting":
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), game.phase_ends_at + rules.LATE_SECONDS - time.monotonic())
                done.clear()
                if not alive():
                    return
                game.begin_reading(time.monotonic())
                await broadcast(room)
            elif game.phase in rules.PREPARATION_PHASES:
                await asyncio.sleep(game.phase_ends_at - time.monotonic())
                if not alive():
                    return
                game.begin_reading(time.monotonic())
                await broadcast(room)
            reading_at = time.time()
            await asyncio.sleep(game.phase_ends_at - time.monotonic())
            if not alive():
                return

            game.open_answers(time.monotonic())
            answers_at = time.time()
            await broadcast(room)
            # Cada um tem o seu prazo (Tempo extra, Acelerador): espera até o último de quem falta.
            while (close_at := game.answers_close_at(room.connected_ids())) and close_at > time.monotonic():
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), close_at - time.monotonic())
                done.clear()
                if not alive():
                    return
            if not alive():
                return

            done.clear()
            game.close_round(room.players, time.monotonic())
            if match_id:
                record(history.round_closed, match_id, room, reading_at, answers_at, time.time())
            await broadcast(room)
            skipped = False
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), game.phase_ends_at - time.monotonic())
                skipped = True
            if match_id:
                record(history.round_ended, match_id, game.round + 1, time.time(), skipped)
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
        if match_id:
            record(history.finish, match_id, room, "finished" if game.phase == "finished" else "abandoned", time.time())


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
            sid, request.rounds, request.themes, request.answer_seconds, request.speed_grace_seconds, request.mode, request.powerup_max
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
async def submit_bet(sid: str, data: dict) -> dict:
    try:
        request = SubmitBetRequest.model_validate(data)
        room = rooms.bet(sid, request.amount, time.monotonic())
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    check_round_done(room)
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def arm_powerup(sid: str, data: dict) -> dict:
    try:
        request = ArmPowerUpRequest.model_validate(data)
        room = rooms.arm_powerup(sid, request.kind, request.target, request.legendary)
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def use_powerup(sid: str, data: dict) -> dict:
    try:
        request = UsePowerUpRequest.model_validate(data)
        room = rooms.use_powerup(sid, request.kind)
    except ValidationError:
        return error("Dados inválidos.")
    except RoomError as e:
        return error(str(e))
    await broadcast(room)
    return OkAck().model_dump()


@sio.event
async def skip_results(sid: str) -> dict:
    try:
        room = rooms.ready(sid)
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
