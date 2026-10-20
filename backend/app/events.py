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

NICKNAME_MAX_LENGTH = 16


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


# --- Servidor → cliente -------------------------------------------------------

class PlayerView(BaseModel):
    id: str
    nickname: str
    avatar: Avatar
    connected: bool


class RoomState(BaseModel):
    """Enviado no evento `room_state` sempre que a sala muda."""

    code: str
    status: Literal["lobby", "playing"]
    host_id: str
    max_players: int
    min_players: int
    players: list[PlayerView]


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
    RoomState,
    JoinedAck,
    OkAck,
    ErrorAck,
]
