"""O que todos os modos de jogo têm em comum."""

from typing import ClassVar


class RoomError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador. Cada modo tem a sua subclasse."""


class Phased:
    """Partida que anda por fases com hora para acabar."""

    def _enter(self, phase: str, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds


class Revealed(Phased):
    """Partida com revelação, em que dá para tocar em Pular."""

    rule_error: ClassVar[type[RoomError]] = RoomError

    def mark_ready(self, player_id: str) -> None:
        if self.phase != "results":
            raise self.rule_error("Agora não dá para pular.")
        self.ready.add(player_id)
