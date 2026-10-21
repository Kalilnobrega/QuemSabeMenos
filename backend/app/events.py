"""Contrato dos eventos trocados entre servidor e cliente via Socket.IO.

Todo payload enviado ao cliente é um modelo Pydantic registrado em EVENT_MODELS.
O front gera seus tipos TypeScript a partir daqui (scripts/export_schema.py).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Os ids batem com os arquivos em frontend/src/assets/avatars/<id>.svg.
Avatar = Literal[
    "burro", "cachorro", "coelho", "coruja", "galinha", "gato", "leao", "macaco",
    "ovelha", "panda", "pinguim", "porco", "raposa", "sapo", "urso", "vaca",
]

Difficulty = Literal["easy", "medium", "hard", "impossible"]

NICKNAME_MAX_LENGTH = 16
ROUND_OPTIONS = (5, 10, 15, 20, 25, 30)


class Pong(BaseModel):
    server_time: float


# --- Cliente → servidor -------------------------------------------------------

class Profile(BaseModel):
    nickname: str = Field(min_length=1, max_length=NICKNAME_MAX_LENGTH)
    avatar: Avatar


class CreateRoomRequest(Profile):
    pass


class JoinRoomRequest(Profile):
    code: str


class RejoinRoomRequest(BaseModel):
    code: str
    token: str


class UpdateSettingsRequest(BaseModel):
    rounds: int


class SubmitAnswerRequest(BaseModel):
    option: int


# --- Servidor → cliente -------------------------------------------------------

class PlayerView(BaseModel):
    id: str
    nickname: str
    avatar: Avatar
    connected: bool
    score: int


class RoomSettings(BaseModel):
    rounds: int
    answer_seconds: float
    round_options: list[int]


class QuestionView(BaseModel):
    text: str
    options: list[str]
    theme: str
    difficulty: Difficulty


class RoundResult(BaseModel):
    player_id: str
    option: int | None  # None = não respondeu
    correct: bool
    delta: int


class GameView(BaseModel):
    """Fases de cada rodada: reading (texto aparecendo, respostas bloqueadas) →
    answering → results. Depois da última rodada: finished."""

    round: int  # começa em 1
    total_rounds: int
    phase: Literal["reading", "answering", "results", "finished"]
    phase_duration_ms: int
    phase_ends_in_ms: int  # relativo ao envio, para não depender do relógio do celular
    question: QuestionView | None
    answered: list[str]  # ids de quem já respondeu nesta rodada
    correct_option: int | None  # só aparece em results
    fact: str | None  # curiosidade sobre a resposta, também só em results
    results: list[RoundResult]


class RoomState(BaseModel):
    """Enviado no evento `room_state` sempre que a sala muda."""

    code: str
    status: Literal["lobby", "playing"]
    host_id: str
    max_players: int
    min_players: int
    settings: RoomSettings
    players: list[PlayerView]
    game: GameView | None


class Ack(BaseModel):
    # Mantém `ok` obrigatório no TS, para o front distinguir sucesso de erro.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class JoinedAck(Ack):
    """Resposta de create_room, join_room e rejoin_room quando dá certo."""

    ok: Literal[True] = True
    player_id: str
    token: str
    room: RoomState


class OkAck(Ack):
    ok: Literal[True] = True


class ErrorAck(Ack):
    ok: Literal[False] = False
    error: str


EVENT_MODELS: list[type[BaseModel]] = [
    Pong,
    CreateRoomRequest,
    JoinRoomRequest,
    RejoinRoomRequest,
    UpdateSettingsRequest,
    SubmitAnswerRequest,
    RoomState,
    JoinedAck,
    OkAck,
    ErrorAck,
]
