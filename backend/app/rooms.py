"""Salas e jogadores, sem nada de rede: o main.py liga isto ao Socket.IO.

O estado vive em memória no processo do servidor (uma instância no Railway).
"""

import random
import secrets
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from app.events import (
    ANSWER_OPTIONS,
    GRACE_OPTIONS,
    MODE_OPTIONS,
    POWERUP_MAX_OPTIONS,
    ROUND_OPTIONS,
    Avatar,
    GameMode,
    PlayerView,
    PowerUp,
    Profile,
    RoomSettings,
    RoomState,
)
from app.game import (
    SPEED_GRACE_SECONDS,
    STARTING_IQ,
    Game,
    GameError,
    Question,
    load_bank,
    pick_questions,
    point_scale,
)
from app.powerups import MAX_HELD

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sem I e O, que confundem com 1 e 0
CODE_LENGTH = 5
MAX_PLAYERS = 12
MIN_PLAYERS = 2
DEFAULT_ROUNDS = 25
ANSWER_SECONDS = 15.0


class RoomError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


@dataclass
class Player:
    nickname: str
    avatar: Avatar
    sid: str | None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    token: str = field(default_factory=lambda: secrets.token_urlsafe(16))
    score: int = STARTING_IQ
    answer_ms: int = 0
    streak: int = 0
    # Muda a cada desconexão, para um timer antigo não expulsar quem já voltou.
    disconnect_seq: int = 0

    @property
    def connected(self) -> bool:
        return self.sid is not None

    def view(self) -> PlayerView:
        return PlayerView(
            id=self.id,
            nickname=self.nickname,
            avatar=self.avatar,
            connected=self.connected,
            score=self.score,
            answer_ms=self.answer_ms,
            streak=self.streak,
        )


@dataclass
class Room:
    code: str
    host_id: str
    players: list[Player]  # em ordem de chegada
    status: Literal["lobby", "playing"] = "lobby"
    mode: GameMode = "classic"
    powerup_max: int = MAX_HELD
    rounds: int = DEFAULT_ROUNDS
    answer_seconds: float = ANSWER_SECONDS
    speed_grace_seconds: float = SPEED_GRACE_SECONDS
    theme_options: list[str] = field(default_factory=list)  # temas do banco
    themes: list[str] = field(default_factory=list)  # escolhidos pelo anfitrião; começam todos
    game: Game | None = None
    # Perguntas já sorteadas nesta sala, para "jogar de novo" trazer perguntas novas.
    used_questions: set[str] = field(default_factory=set)

    def player(self, player_id: str) -> Player | None:
        return next((p for p in self.players if p.id == player_id), None)

    def connected_ids(self) -> list[str]:
        return [p.id for p in self.players if p.connected]

    def view(self, now: float | None = None, viewer: str | None = None) -> RoomState:
        """`viewer`: o jogador que vai receber, para mostrar só as habilidades dele."""
        now = time.monotonic() if now is None else now
        return RoomState(
            code=self.code,
            status=self.status,
            host_id=self.host_id,
            max_players=MAX_PLAYERS,
            min_players=MIN_PLAYERS,
            settings=RoomSettings(
                mode=self.mode,
                mode_options=list(MODE_OPTIONS),
                powerup_max=self.powerup_max,
                powerup_max_options=list(POWERUP_MAX_OPTIONS),
                rounds=self.rounds,
                answer_seconds=self.answer_seconds,
                speed_grace_seconds=self.speed_grace_seconds,
                round_options=list(ROUND_OPTIONS),
                answer_options=list(ANSWER_OPTIONS),
                grace_options=list(GRACE_OPTIONS),
                themes=self.themes,
                theme_options=self.theme_options,
            ),
            players=[p.view() for p in self.players],
            game=self.game.view(now, viewer) if self.game else None,
        )


def normalize_code(code: str) -> str:
    return code.strip().upper()


def normalize_nickname(nickname: str) -> str:
    nickname = " ".join(nickname.split())
    if not nickname:
        raise RoomError("Escolha um apelido.")
    return nickname


class RoomManager:
    def __init__(self, bank: list[Question] | None = None, rng: random.Random | None = None) -> None:
        self.bank = load_bank() if bank is None else bank
        self.theme_options = sorted({q.theme for q in self.bank})
        self.rng = rng or random.Random()
        self.rooms: dict[str, Room] = {}
        self._sessions: dict[str, tuple[str, str]] = {}  # sid -> (código da sala, id do jogador)

    def session(self, sid: str) -> tuple[Room, Player] | None:
        code, player_id = self._sessions.get(sid, (None, None))
        room = self.rooms.get(code) if code else None
        player = room.player(player_id) if room and player_id else None
        return (room, player) if room and player else None

    def create(self, sid: str, profile: Profile) -> tuple[Room, Player]:
        player = Player(nickname=normalize_nickname(profile.nickname), avatar=profile.avatar, sid=sid)
        room = Room(
            code=self._new_code(),
            host_id=player.id,
            players=[player],
            answer_seconds=ANSWER_SECONDS,
            theme_options=self.theme_options,
            themes=list(self.theme_options),
        )
        self.rooms[room.code] = room
        self._sessions[sid] = (room.code, player.id)
        return room, player

    def join(self, sid: str, code: str, profile: Profile) -> tuple[Room, Player]:
        room = self._get(code)
        if room.status != "lobby":
            raise RoomError("A partida dessa sala já começou.")
        if len(room.players) >= MAX_PLAYERS:
            raise RoomError(f"A sala está cheia ({MAX_PLAYERS} jogadores).")
        nickname = normalize_nickname(profile.nickname)
        if any(p.nickname.casefold() == nickname.casefold() for p in room.players):
            raise RoomError("Já tem alguém com esse apelido na sala.")
        player = Player(nickname=nickname, avatar=profile.avatar, sid=sid)
        room.players.append(player)
        self._sessions[sid] = (room.code, player.id)
        return room, player

    def rejoin(self, sid: str, code: str, token: str) -> tuple[Room, Player, str | None]:
        """Devolve também o sid antigo do jogador, se ele ainda estava conectado (outra aba)."""
        room = self._get(code)
        player = next((p for p in room.players if secrets.compare_digest(p.token, token)), None)
        if player is None:
            raise RoomError("Você não está mais nessa sala.")
        old_sid = player.sid if player.sid != sid else None
        if old_sid:
            self._sessions.pop(old_sid, None)
        player.sid = sid
        self._sessions[sid] = (room.code, player.id)
        return room, player, old_sid

    def leave(self, sid: str) -> Room | None:
        """Tira o jogador da sala. Devolve a sala se ela ainda existir."""
        found = self.session(sid)
        self._sessions.pop(sid, None)
        if not found:
            return None
        room, player = found
        return self._remove(room, player)

    def disconnect(self, sid: str) -> tuple[Room, Player, int] | None:
        """Marca o jogador como desconectado; ele continua na sala até `expire`."""
        found = self.session(sid)
        self._sessions.pop(sid, None)
        if not found:
            return None
        room, player = found
        player.sid = None
        player.disconnect_seq += 1
        return room, player, player.disconnect_seq

    def expire(self, code: str, player_id: str, disconnect_seq: int) -> Room | None:
        """Remove o jogador se ele não voltou desde a desconexão `disconnect_seq`.

        Devolve a sala se ela mudou e ainda existe.
        """
        room = self.rooms.get(code)
        player = room.player(player_id) if room else None
        if not room or not player or player.connected or player.disconnect_seq != disconnect_seq:
            return None
        return self._remove(room, player)

    def update_settings(
        self,
        sid: str,
        rounds: int | None = None,
        themes: list[str] | None = None,
        answer_seconds: float | None = None,
        speed_grace_seconds: float | None = None,
        mode: GameMode | None = None,
        powerup_max: int | None = None,
    ) -> Room:
        room = self._host_room(sid, "mudar as configurações")
        if room.status != "lobby":
            raise RoomError("A partida já começou.")
        if rounds is not None and rounds not in ROUND_OPTIONS:
            raise RoomError("Número de perguntas inválido.")
        if answer_seconds is not None and answer_seconds not in ANSWER_OPTIONS:
            raise RoomError("Tempo de resposta inválido.")
        if powerup_max is not None and powerup_max not in POWERUP_MAX_OPTIONS:
            raise RoomError("Limite de habilidades inválido.")
        if speed_grace_seconds is not None and speed_grace_seconds not in GRACE_OPTIONS:
            raise RoomError("Tempo de QI cheio inválido.")
        if themes is not None:
            if not themes:
                raise RoomError("Escolha pelo menos um tema.")
            if not set(themes) <= set(self.theme_options):
                raise RoomError("Tema inválido.")
        if mode is not None:
            room.mode = mode
        if powerup_max is not None:
            room.powerup_max = powerup_max
        if rounds is not None:
            room.rounds = rounds
        if answer_seconds is not None:
            room.answer_seconds = answer_seconds
        if speed_grace_seconds is not None:
            room.speed_grace_seconds = speed_grace_seconds
        if themes is not None:
            room.themes = [t for t in self.theme_options if t in themes]  # na ordem da lista
        return room

    def start(self, sid: str, now: float | None = None) -> Room:
        """Cria a partida já na primeira rodada; o main.py conduz as seguintes."""
        room = self._host_room(sid, "começar a partida")
        if room.status != "lobby":
            raise RoomError("A partida já começou.")
        if len(room.players) < MIN_PLAYERS:
            raise RoomError(f"Precisa de pelo menos {MIN_PLAYERS} jogadores.")
        bank = [q for q in self.bank if q.theme in room.themes]
        questions = pick_questions(bank, room.rounds, room.used_questions, self.rng)
        room.used_questions |= {q.id for q in questions}
        for player in room.players:
            player.score = STARTING_IQ
            player.answer_ms = 0
            player.streak = 0
        room.game = Game(
            questions=questions,
            answer_seconds=room.answer_seconds,
            point_scale=point_scale(room.rounds),
            speed_grace_seconds=room.speed_grace_seconds,
            rng=self.rng,
            powers=room.mode == "powers",
            powerup_max=room.powerup_max,
        )
        if room.game.powers:
            room.game.deal_powerups([p.id for p in room.players])
        room.game.start_round(time.monotonic() if now is None else now)
        room.status = "playing"
        return room

    def answer(self, sid: str, option: int, now: float) -> Room:
        found = self.session(sid)
        if not found or not found[0].game:
            raise RoomError("Não tem partida rolando.")
        room, player = found
        try:
            room.game.answer(player.id, option, now)
        except GameError as e:
            raise RoomError(str(e)) from e
        return room

    def bet(self, sid: str, amount: int, now: float) -> Room:
        found = self.session(sid)
        if not found or not found[0].game:
            raise RoomError("Não tem partida rolando.")
        room, player = found
        try:
            room.game.bet(player, amount, now)
        except GameError as e:
            raise RoomError(str(e)) from e
        return room

    def arm_powerup(self, sid: str, kind: PowerUp, target: str | None, legendary: bool = False) -> Room:
        room, player = self._playing(sid)
        try:
            room.game.arm(player.id, kind, target, [p.id for p in room.players], legendary)
        except GameError as e:
            raise RoomError(str(e)) from e
        return room

    def use_powerup(self, sid: str, kind: PowerUp) -> Room:
        room, player = self._playing(sid)
        try:
            room.game.use_now(player.id, kind)
        except GameError as e:
            raise RoomError(str(e)) from e
        return room

    def ready(self, sid: str) -> Room:
        """Pular a revelação: acaba antes quando todos os conectados tocam."""
        room, player = self._playing(sid)
        try:
            room.game.mark_ready(player.id)
        except GameError as e:
            raise RoomError(str(e)) from e
        return room

    def _playing(self, sid: str) -> tuple[Room, Player]:
        found = self.session(sid)
        if not found or not found[0].game:
            raise RoomError("Não tem partida rolando.")
        return found

    def play_again(self, sid: str) -> Room:
        """Volta a sala para o lobby depois do fim da partida."""
        room = self._host_room(sid, "recomeçar")
        if not room.game or room.game.phase != "finished":
            raise RoomError("A partida ainda não terminou.")
        room.game = None
        room.status = "lobby"
        for player in room.players:
            player.score = STARTING_IQ
            player.answer_ms = 0
            player.streak = 0
        return room

    def _host_room(self, sid: str, action: str) -> Room:
        found = self.session(sid)
        if not found:
            raise RoomError("Você não está em nenhuma sala.")
        room, player = found
        if player.id != room.host_id:
            raise RoomError(f"Só o anfitrião pode {action}.")
        return room

    def _get(self, code: str) -> Room:
        room = self.rooms.get(normalize_code(code))
        if room is None:
            raise RoomError("Sala não encontrada. Confira o código.")
        return room

    def _remove(self, room: Room, player: Player) -> Room | None:
        room.players.remove(player)
        if not room.players:
            del self.rooms[room.code]
            return None
        if room.host_id == player.id:
            # O mais antigo vira anfitrião, preferindo quem está conectado.
            room.host_id = next((p for p in room.players if p.connected), room.players[0]).id
        return room

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self.rooms:
                return code
