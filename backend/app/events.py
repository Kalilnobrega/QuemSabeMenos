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
ROUND_OPTIONS = (10, 15, 20, 25, 30, 35)
ANSWER_OPTIONS = (10, 15, 20, 25, 30)  # segundos para responder
GRACE_OPTIONS = (0, 2, 3, 5)  # segundos de QI cheio


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
    """Só os campos enviados mudam."""

    rounds: int | None = None
    answer_seconds: float | None = None
    speed_grace_seconds: float | None = None
    themes: list[str] | None = None


class SubmitAnswerRequest(BaseModel):
    option: int


class SubmitBetRequest(BaseModel):
    amount: int = Field(ge=0)


# --- Servidor → cliente -------------------------------------------------------

class PlayerView(BaseModel):
    id: str
    nickname: str
    avatar: Avatar
    connected: bool
    score: int  # QI na partida
    answer_ms: int  # tempo total de resposta; desempata quem tem o mesmo QI
    streak: int  # > 0: acertos seguidos em médias/difíceis; < 0: erros seguidos


class RoomSettings(BaseModel):
    rounds: int
    answer_seconds: float
    speed_grace_seconds: float  # respostas até aqui valem o máximo
    round_options: list[int]
    answer_options: list[int]
    grace_options: list[int]
    themes: list[str]  # temas sorteados na partida (pelo menos um)
    theme_options: list[str]


class QuestionView(BaseModel):
    text: str
    options: list[str]
    theme: str
    difficulty: Difficulty


class Bonus(BaseModel):
    """Bônus da partida: gabaritar as fáceis, sequências de acertos (positivo) e sequências
    de erros (negativo). Uma sequência repetida na mesma partida vale a metade."""

    kind: Literal["perfect_easy", "streak", "wrong_streak"]
    count: int  # quantas fáceis ou o tamanho da sequência
    delta: int
    repeat: bool  # já tinha feito essa sequência nesta partida


class RoundResult(BaseModel):
    player_id: str
    option: int | None  # None = não respondeu
    correct: bool
    delta: int  # pontos da resposta, sem os bônus e sem a aposta
    bonuses: list[Bonus]
    bet: int | None  # None fora da rodada da aposta; 0 = não apostou
    bet_delta: int  # +bet × (bet_odds - 1) (para baixo) se acertou, -bet se errou ou não respondeu


class GameView(BaseModel):
    """Fases de cada rodada: reading (texto aparecendo, respostas bloqueadas) →
    answering → results. Telas de preparação, em que a pergunta não é enviada: starting
    (antes da 1ª pergunta), level (quando a dificuldade muda), betting (aposta, só com o
    tema à mostra) e intro (antes da final).
    Depois da última rodada: finished."""

    round: int  # começa em 1
    total_rounds: int
    phase: Literal["starting", "level", "intro", "betting", "reading", "answering", "results", "finished"]
    phase_duration_ms: int
    phase_ends_in_ms: int  # relativo ao envio, para não depender do relógio do celular
    difficulty: Difficulty  # da pergunta da rodada (enviada também nas telas de preparação)
    theme: str  # idem
    question: QuestionView | None  # None em starting, level e intro
    answered: list[str]  # ids de quem já respondeu nesta rodada
    bet_round: int | None  # rodada com aposta (começa em 1)
    bet_percents: list[int]  # atalhos de aposta, em % do QI
    bet_max_percent: int  # aposta máxima, em % do QI (arredondada para baixo)
    bet_odds: float  # quanto a aposta paga se acertar (odd decimal: 1.5 = apostou 100, lucra 50)
    bets_placed: list[str]  # ids de quem já apostou; os valores só aparecem em results
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
    SubmitBetRequest,
    RoomState,
    JoinedAck,
    OkAck,
    ErrorAck,
]
