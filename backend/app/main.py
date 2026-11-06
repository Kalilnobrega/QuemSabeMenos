import asyncio
import logging
import os
import secrets
import time
from contextlib import suppress
from functools import wraps
from pathlib import Path

import socketio
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError

from app import game as rules
from app import history as modes
from app.events import (
    ArmPowerUpRequest,
    ChooseRepresentativeRequest,
    ChooseThemeRequest,
    CreateRoomRequest,
    ErrorAck,
    JoinedAck,
    JoinRoomRequest,
    MathStepsRequest,
    OkAck,
    Pong,
    RejoinRoomRequest,
    SetTeamRequest,
    SubmitAnswerRequest,
    SubmitBetRequest,
    SubmitDuelBetRequest,
    SubmitGuessRequest,
    UpdateAvatarRequest,
    UpdateSettingsRequest,
    UsePowerUpRequest,
)
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
    """Cada jogador recebe o próprio estado: os poderes de cada um são secretos."""
    now = time.monotonic()
    for player in room.players:
        if player.sid:
            await sio.emit("room_state", room.view(now, player.id).model_dump(), to=player.sid)


async def joined(sid: str, room: Room, player: Player) -> dict:
    await sio.enter_room(sid, room.code)
    await broadcast(room)
    return JoinedAck(player_id=player.id, token=player.token, room=room.view(viewer=player.id)).model_dump()


def check_round_done(room: Room) -> None:
    if room.estimate:
        estimate, connected = room.estimate, room.connected_ids()
        if (
            (estimate.phase == "answering" and estimate.everyone_answered(connected, time.monotonic()))
            or (estimate.phase == "results" and estimate.everyone_ready(connected))
        ) and (event := round_done.get(room.code)):
            event.set()
        return
    if room.team_match:
        if room.team_match.can_advance(room.connected_ids()) and (event := round_done.get(room.code)):
            event.set()
        return
    if room.hot_potato:
        # Cada resposta muda a fase na hora: acorda o laço para mandar o estado e o prazo novo.
        if event := round_done.get(room.code):
            event.set()
        return
    if room.survival:
        survival, connected = room.survival, room.connected_ids()
        answering = survival.phase in ("answering", "duel_answering") and survival.everyone_answered(connected)
        if (answering or survival.everyone_ready(connected)) and (event := round_done.get(room.code)):
            event.set()
        return
    game = room.game
    if not game:
        return
    connected = [p for p in room.players if p.connected]
    if (
        (game.phase == "theme_pick" and (game.block_theme or game.theme_picker not in room.connected_ids()))
        or (game.phase == "answering" and game.everyone_answered(room.connected_ids()))
        or (game.phase == "betting" and game.everyone_bet(connected))
        or (game.phase == "results" and game.everyone_ready(room.connected_ids()))
        or (game.phase == "duel_betting" and game.everyone_bet_on_duel(room.connected_ids()))
        or (game.phase == "duel_answering" and game.duel.everyone_answered())
    ) and (event := round_done.get(room.code)):
        event.set()


async def leave_current_room(sid: str) -> None:
    found = rooms.session(sid)
    if not found:
        return
    await sio.leave_room(sid, found[0].code)
    if room := rooms.leave(sid):
        check_round_done(room)
        await broadcast(room)
    elif event := round_done.get(found[0].code):
        event.set()  # a sala esvaziou: acorda a partida para ela encerrar (e fechar o histórico) já


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
    roster = modes.roster(room)

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.game is game

    try:
        while alive():
            done.clear()
            if game.phase == "theme_pick":
                await broadcast(room)
                check_round_done(room)  # quem escolhe pode já ter saído
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), game.phase_ends_at + rules.LATE_SECONDS - time.monotonic())
                done.clear()
                if not alive():
                    return
                game.close_theme_pick(time.monotonic())
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
            await run_duels(room, done, alive)
            if not alive():
                return
            game.start_round(time.monotonic(), room.connected_scores())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]
        if match_id:
            status = "finished" if game.phase == "finished" else "abandoned"
            record(history.finish, match_id, room, status, time.time(), modes.score_standings(roster.values()))


async def run_duels(room: Room, done: asyncio.Event, alive) -> None:
    """X1 chamados na revelação, um depois do outro: aposta da plateia, perguntas, acerto de contas."""
    game = room.game

    async def wait_phase() -> None:
        done.clear()
        with suppress(TimeoutError):
            await asyncio.wait_for(done.wait(), max(0.0, game.phase_ends_at + rules.LATE_SECONDS - time.monotonic()))
        done.clear()

    while alive() and game.start_duel(
        [p.id for p in room.players], {p.id: p.score for p in room.players}, time.monotonic()
    ):
        await broadcast(room)
        await wait_phase()
        while alive() and game.open_duel_question(time.monotonic()):
            await broadcast(room)
            await wait_phase()
            if not alive():
                return
            game.close_duel_question(time.monotonic())
            await broadcast(room)
            await asyncio.sleep(max(0.0, game.phase_ends_at - time.monotonic()))
        if not alive():
            return
        game.finish_duel(room.players, time.monotonic())
        await broadcast(room)
        await asyncio.sleep(max(0.0, game.phase_ends_at - time.monotonic()))


async def run_survival(room: Room) -> None:
    """Conduz o Último de pé: cada fase dura o seu tempo; as respostas acabam antes se todos responderem."""
    survival = room.survival
    done = round_done[room.code] = asyncio.Event()
    match_id = record(history.start, room, time.time())
    roster = modes.roster(room)

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.survival is survival

    try:
        while alive():
            done.clear()
            await broadcast(room)
            if survival.phase == "finished":
                return
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), max(0.0, survival.deadline() - time.monotonic()))
            if not alive():
                return
            survival.advance(time.monotonic())
            if match_id and survival.phase in ("results", "duel_results"):
                record(history.event, match_id, "question", modes.survival_question(survival, room), time.time())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]
        if match_id:
            status = "finished" if survival.phase == "finished" else "abandoned"
            record(history.finish, match_id, room, status, time.time(), modes.survival_standings(survival, roster))


async def run_estimate(room: Room) -> None:
    """Conduz o Chutômetro: cada fase dura o seu tempo; acaba antes se todos chutaram ou pularam."""
    estimate = room.estimate
    done = round_done[room.code] = asyncio.Event()
    match_id = record(history.start, room, time.time())
    roster = modes.roster(room)

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.estimate is estimate

    try:
        while alive():
            done.clear()
            await broadcast(room)
            if estimate.phase == "finished":
                return
            check_round_done(room)  # quem saiu não segura a fase
            # Com um alvo da Matemática, a pergunta segue depois do tempo dos outros: eles passam a assistir.
            others_up = estimate.others_time_up_at()
            if others_up and time.monotonic() < others_up:
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), others_up - time.monotonic())
                if alive() and not done.is_set():
                    check_round_done(room)
                    await broadcast(room)
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), max(0.0, estimate.deadline() - time.monotonic()))
            if not alive():
                return
            estimate.advance(time.monotonic(), room.players)
            if match_id and estimate.phase == "results":
                record(history.event, match_id, "question", modes.estimate_question(estimate), time.time())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]
        if match_id:
            status = "finished" if estimate.phase == "finished" else "abandoned"
            record(history.finish, match_id, room, status, time.time(), modes.score_standings(roster.values()))


async def run_team_match(room: Room) -> None:
    """Conduz os Times: cada fase dura o seu tempo, e acaba antes quando todo mundo já fez a sua parte."""
    match = room.team_match
    done = round_done[room.code] = asyncio.Event()
    match_id = record(history.start, room, time.time())
    roster, lineup = modes.roster(room), modes.team_lineup(match)

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.team_match is match

    try:
        while alive():
            done.clear()
            await broadcast(room)
            if match.phase == "finished":
                return
            if not match.can_advance(room.connected_ids()):
                with suppress(TimeoutError):
                    await asyncio.wait_for(done.wait(), max(0.0, match.deadline() - time.monotonic()))
            if not alive():
                return
            before = match.phase
            match.advance(time.monotonic(), room.connected_ids())
            if match_id and match.phase != before:
                if match.phase == "results":
                    record(history.event, match_id, "question", modes.team_question(match), time.time())
                elif match.phase == "duel_end":
                    record(history.event, match_id, "duel", modes.team_duel(match), time.time())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]
        if match_id:
            status = "finished" if match.phase == "finished" else "abandoned"
            record(history.finish, match_id, room, status, time.time(), modes.team_standings(match, roster, lineup))


async def run_hot_potato(room: Room) -> None:
    """Conduz a Batata quente: espera o prazo da fase (no asking, o pavio) ou uma resposta."""
    potato = room.hot_potato
    done = round_done[room.code] = asyncio.Event()
    match_id = record(history.start, room, time.time())
    roster = modes.roster(room)

    def save_events() -> None:
        events = modes.hot_potato_events(potato)
        if match_id:
            for kind, data in events:
                record(history.event, match_id, kind, data, time.time())

    def alive() -> bool:
        return rooms.rooms.get(room.code) is room and room.hot_potato is potato

    try:
        while alive():
            done.clear()
            save_events()
            await broadcast(room)
            if potato.phase == "finished":
                return
            with suppress(TimeoutError):
                await asyncio.wait_for(done.wait(), max(0.0, potato.deadline() - time.monotonic()))
            if alive() and time.monotonic() >= potato.deadline():
                potato.advance(time.monotonic())
    finally:
        if round_done.get(room.code) is done:
            del round_done[room.code]
        save_events()
        if match_id:
            status = "finished" if potato.phase == "finished" else "abandoned"
            record(history.finish, match_id, room, status, time.time(), modes.hot_potato_standings(potato, roster))


INVALID_DATA = "Dados inválidos."
INVALID_PROFILE = "Apelido ou avatar inválido."


def action(model: type[BaseModel] | None = None, invalid: str = INVALID_DATA):
    """Handler de um pedido do jogador: valida os dados e transforma erros esperados em resposta."""

    def decorate(handler):
        @wraps(handler)
        async def run(sid: str, *args) -> dict:
            try:
                if model is None:
                    return await handler(sid, *args)
                try:
                    request = model.model_validate(*args)
                except ValidationError:
                    return error(invalid)
                return await handler(sid, request)
            except RoomError as e:
                return error(str(e))

        return run

    return decorate


async def publish(room: Room) -> dict:
    await broadcast(room)
    return OkAck().model_dump()


async def publish_move(room: Room) -> dict:
    """Depois de uma jogada, que pode ter sido a última que a fase esperava."""
    check_round_done(room)
    return await publish(room)


@sio.event
async def ping_server(sid: str) -> dict:
    return Pong(server_time=time.time()).model_dump()


@sio.event
@action(CreateRoomRequest, invalid=INVALID_PROFILE)
async def create_room(sid: str, request: CreateRoomRequest) -> dict:
    await leave_current_room(sid)
    room, player = rooms.create(sid, request)
    return await joined(sid, room, player)


@sio.event
@action(JoinRoomRequest, invalid=INVALID_PROFILE)
async def join_room(sid: str, request: JoinRoomRequest) -> dict:
    await leave_current_room(sid)
    room, player = rooms.join(sid, request.code, request)
    return await joined(sid, room, player)


@sio.event
@action(RejoinRoomRequest)
async def rejoin_room(sid: str, request: RejoinRoomRequest) -> dict:
    current = rooms.session(sid)
    if current and current[1].token != request.token:
        await leave_current_room(sid)
    room, player, old_sid = rooms.rejoin(sid, request.code, request.token)
    if old_sid:
        await sio.leave_room(old_sid, room.code)
    return await joined(sid, room, player)


@sio.event
async def leave_room(sid: str) -> dict:
    await leave_current_room(sid)
    return OkAck().model_dump()


@sio.event
@action(UpdateSettingsRequest)
async def update_settings(sid: str, request: UpdateSettingsRequest) -> dict:
    room = rooms.update_settings(
        sid,
        request.rounds,
        request.themes,
        request.answer_seconds,
        request.speed_grace_seconds,
        request.mode,
        request.powerup_max,
        request.survival_kind,
        request.powers,
        request.team_count,
        request.team_pick,
    )
    return await publish(room)


@sio.event
@action(UpdateAvatarRequest)
async def update_avatar(sid: str, request: UpdateAvatarRequest) -> dict:
    return await publish(rooms.update_avatar(sid, request.avatar))


@sio.event
@action(SetTeamRequest)
async def set_team(sid: str, request: SetTeamRequest) -> dict:
    return await publish(rooms.set_team(sid, request.player_id, request.team))


@sio.event
@action(ChooseRepresentativeRequest)
async def choose_representative(sid: str, request: ChooseRepresentativeRequest) -> dict:
    return await publish_move(rooms.choose_representative(sid, request.choice))


@sio.event
@action()
async def start_game(sid: str) -> dict:
    room = rooms.start(sid)
    runner = (
        run_estimate
        if room.estimate
        else run_team_match
        if room.team_match
        else run_hot_potato
        if room.hot_potato
        else run_survival
        if room.survival
        else run_game
    )
    sio.start_background_task(runner, room)
    return OkAck().model_dump()


@sio.event
@action(SubmitAnswerRequest)
async def submit_answer(sid: str, request: SubmitAnswerRequest) -> dict:
    return await publish_move(rooms.answer(sid, request.option, time.monotonic(), request.team, request.potato))


@sio.event
@action(SubmitBetRequest)
async def submit_bet(sid: str, request: SubmitBetRequest) -> dict:
    return await publish_move(rooms.bet(sid, request.amount, time.monotonic()))


@sio.event
@action(SubmitDuelBetRequest)
async def submit_duel_bet(sid: str, request: SubmitDuelBetRequest) -> dict:
    return await publish_move(rooms.duel_bet(sid, request.choice, time.monotonic()))


@sio.event
@action(ArmPowerUpRequest)
async def arm_powerup(sid: str, request: ArmPowerUpRequest) -> dict:
    # Quem arma já conta como pronto: pode ter sido o último.
    return await publish_move(
        rooms.arm_powerup(sid, request.kind, request.target, request.legendary, request.theme, request.target_team)
    )


@sio.event
@action()
async def disarm_powerup(sid: str) -> dict:
    return await publish(rooms.disarm_powerup(sid))


@sio.event
@action(UsePowerUpRequest)
async def use_powerup(sid: str, request: UsePowerUpRequest) -> dict:
    room = rooms.use_powerup(sid, request.kind, time.monotonic(), request.target_team, request.potato, request.option)
    if room.hot_potato or room.team_match:
        return await publish_move(room)  # o poder pode mudar o pavio, passar a batata ou travar um time
    return await publish(room)


@sio.event
@action(MathStepsRequest)
async def math_steps(sid: str, request: MathStepsRequest) -> dict:
    return await publish(rooms.math_steps(sid, request.steps))


@sio.event
@action(SubmitGuessRequest)
async def submit_guess(sid: str, request: SubmitGuessRequest) -> dict:
    return await publish_move(rooms.guess(sid, request.value, time.monotonic()))


@sio.event
@action(ChooseThemeRequest)
async def choose_theme(sid: str, request: ChooseThemeRequest) -> dict:
    return await publish_move(rooms.choose_theme(sid, request.theme))


@sio.event
@action()
async def skip_results(sid: str) -> dict:
    return await publish_move(rooms.ready(sid))


@sio.event
@action()
async def play_again(sid: str) -> dict:
    return await publish(rooms.play_again(sid))


@sio.event
async def disconnect(sid: str, reason: str | None = None) -> None:
    if found := rooms.disconnect(sid):
        room, player, seq = found
        check_round_done(room)
        await broadcast(room)
        sio.start_background_task(expire_later, room.code, player.id, seq)


app = socketio.ASGIApp(sio, other_asgi_app=api)
