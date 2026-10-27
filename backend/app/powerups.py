"""Habilidades do modo com poderes.

Quase todas são armadas na revelação e valem na pergunta seguinte; 50/50 e Espiar são usadas na
hora. Nenhuma vale na aposta nem na pergunta final.

Cada um ganha uma sorteada no início e outra a cada 3 acertos seguidos; o lanterna muito atrás
ganha uma a cada 3 rodadas seguidas em último. Ganhar com as mãos cheias não dá nada. As ganhas na
partida podem vir como ataque lendário: vale em todos os outros jogadores e o Reverso não segura.
"""

import random
from typing import Protocol

from app.events import PowerUp, PowerUpUse

POWERUPS: tuple[PowerUp, ...] = (
    "fifty_fifty", "shield", "double", "peek", "extra_time", "second_chance", "reverse",
    "scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier",
)
TARGETED: frozenset[PowerUp] = frozenset(
    {"scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier"}
)
INSTANT: frozenset[PowerUp] = frozenset({"fifty_fifty", "peek"})
# Perguntas comuns que cada uma dura; Escudo e Reverso acabam antes, quando são usados.
LASTING: dict[PowerUp, int] = {"extra_time": 3, "shield": 2, "second_chance": 2, "reverse": 3}
REVERSE_LEADER_ROUNDS = 2  # o Reverso de quem está em 1º ao armar dura menos
# Silêncio: por 2 perguntas comuns o alvo não vê tempo, placar nem revelação e não usa habilidades.
SILENCE_ROUNDS = 2
BREAKABLE: frozenset[PowerUp] = frozenset({"shield", "second_chance", "reverse"})
MAX_HELD = 2
STREAK_FOR_POWERUP = 3
COMEBACK_ROUNDS = 3
# QI atrás do 2º colocado (do 1º, com 2 jogadores) para o último contar como lanterna.
COMEBACK_GAP = 20
LEGENDARY_CHANCE = 0.05
LEGENDARY_TRAILING_CHANCE = 0.20
LEGENDARY_STEAL_POOL = 1.5
LEGENDARY_STEAL_TOP_WEIGHT = 2
FIFTY_FIFTY_REMOVES = 2
STEAL_FIXED = 10
STEAL_GAIN_SHARE = 0.5
DOUBLE_FACTOR = 2
DOUBLE_HARD_LOSS_FACTOR = 3
SECOND_CHANCE_SHARE = 0.5
EXTRA_SECONDS = 5.0  # e QI cheio o tempo todo
ACCELERATOR_FACTOR = 1 / 3  # e o QI cheio vai a zero (no Silêncio também)


class Ranked(Protocol):
    id: str
    score: int


def fifty_fifty(options: int, answer: int, rng: random.Random) -> list[int]:
    """Alternativas erradas que o 50/50 tira, em ordem."""
    wrong = [i for i in range(options) if i != answer]
    return sorted(rng.sample(wrong, FIFTY_FIFTY_REMOVES))


def reflect(uses: list[PowerUpUse], reversers: set[str]) -> list[PowerUpUse]:
    """Aplica o Reverso: a sabotagem volta para quem jogou (uma volta só, sem pingue-pongue).
    No roubo, quem rebateu passa a roubar quem tentou roubar. A lendária (sem alvo) não volta."""
    result = []
    for use in uses:
        if use.kind in TARGETED and use.target in reversers:
            if use.kind == "steal":
                use = PowerUpUse(kind="steal", by=use.target, target=use.by, reflected_by=use.target)
            else:
                use = PowerUpUse(kind=use.kind, by=use.by, target=use.by, reflected_by=use.target)
        result.append(use)
    return result


def trailing(players: list[Ranked]) -> set[str]:
    """Quem está em último e muito atrás dos dois primeiros."""
    if len(players) < 2:
        return set()
    scores = sorted((p.score for p in players), reverse=True)
    reference = scores[1] if len(players) > 2 else scores[0]
    if reference - scores[-1] < COMEBACK_GAP:
        return set()
    return {p.id for p in players if p.score == scores[-1]}
