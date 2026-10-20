"""Contrato dos eventos trocados entre servidor e cliente via Socket.IO.

Todo payload enviado ao cliente é um modelo Pydantic registrado em EVENT_MODELS.
O front gera seus tipos TypeScript a partir daqui (scripts/export_schema.py).
"""

from pydantic import BaseModel


class Pong(BaseModel):
    server_time: float


EVENT_MODELS: list[type[BaseModel]] = [Pong]
