"""Habilidades do modo com poderes.

Quase todas são armadas na revelação e valem na pergunta seguinte; 50/50 e Espiar são usadas na
hora. Nenhuma vale na aposta nem na pergunta final.

Cada um ganha uma sorteada no início e outra a cada 3 acertos seguidos; o lanterna muito atrás
ganha uma a cada 3 rodadas seguidas em último. Ganhar com as mãos cheias não dá nada. As ganhas na
partida podem vir como ataque lendário: vale em todos os outros jogadores e o Reverso não segura.
"""

import random
import re
from typing import Protocol

from app.events import PowerUp, PowerUpUse

POWERUPS: tuple[PowerUp, ...] = (
    "fifty_fifty", "shield", "double", "peek", "extra_time", "second_chance", "reverse",
    "backpack", "theme", "investment",
    "scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier", "toll", "decoy", "flashbang",
)
TARGETED: frozenset[PowerUp] = frozenset(
    {"scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier", "toll", "decoy", "flashbang"}
)
NOT_DEALT: frozenset[PowerUp] = frozenset({"investment"})  # nunca vem no sorteio inicial
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
LEGENDARY_CHANCE = 0.06
LEGENDARY_TRAILING_CHANCE = 0.20
# Míticos: (chance para quem não é lanterna, chance para o lanterna), sorteados antes dos lendários.
MYTHIC_CHANCES: dict[PowerUp, tuple[float, float]] = {"resurrection": (0.0, 0.06), "duel": (0.02, 0.08)}
# Ressurreição: o último pula para logo atrás do penúltimo (com 2 jogadores, 10 atrás do 1º).
RESURRECTION_GAP = 1
RESURRECTION_GAP_TWO_PLAYERS = 10
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
# Pedágio: cada alternativa do alvo tem um preço sorteado; quem não responde paga o menor.
TOLL_PRICES = (3, 8)
LEGENDARY_TOLL_PRICES = (2, 4)
BACKPACK_MAX_EXTRA = 2  # vagas a mais que a Mochila pode dar na partida
THEME_CHOICES = 4
# Alternativa falsa: o alvo vê alternativas inventadas a mais; quem cair dá QI a quem jogou.
DECOY_COUNT = 2
DECOY_BONUS = 10
LEGENDARY_DECOY_BONUS = 5
FLASHBANG_SECONDS = 4.0  # depois de liberar as respostas
# Investimento: bônus a cada acerto seguido; acaba no primeiro erro ou depois do último.
INVESTMENT_BONUS = (2, 4, 6, 8, 10)


class Ranked(Protocol):
    id: str
    score: int


def fifty_fifty(options: int, answer: int, rng: random.Random) -> list[int]:
    """Alternativas erradas que o 50/50 tira, em ordem."""
    wrong = [i for i in range(options) if i != answer]
    return sorted(rng.sample(wrong, FIFTY_FIFTY_REMOVES))


def decoys(answer: str, existing: list[str], similar: list[str], rng: random.Random) -> list[str]:
    """Alternativas falsas para uma pergunta. Número vira um número próximo (ano, um ano perto);
    texto vem de `similar`, alternativas de perguntas parecidas, das mais parecidas para as menos,
    preferindo as que têm o mesmo jeito da certa (tamanho, maiúscula, algarismos)."""
    taken = {option.strip().lower() for option in existing}
    number = re.fullmatch(r"(\d{1,3}(?:\.\d{3})+|\d{1,5})(\D*)", answer.strip())
    if number:
        value, suffix = int(number[1].replace(".", "")), number[2]
        spread = 20 if 1000 <= value <= 2100 else max(2, round(value * 0.3))
        dotted = "." in number[1]
        candidates = [
            f"{n:,}".replace(",", ".") + suffix if dotted else f"{n}{suffix}"
            for n in range(max(0, value - spread), value + spread + 1)
            if n != value
        ]
        fresh = [c for c in dict.fromkeys(candidates) if c.lower() not in taken]
        return rng.sample(fresh, min(DECOY_COUNT, len(fresh)))

    def shape(text: str) -> tuple[int, bool, bool]:
        return min(len(text.split()), 4), text[:1].isupper(), any(ch.isdigit() for ch in text)

    fresh = [c for c in dict.fromkeys(similar) if c.strip().lower() not in taken]
    alike = [c for c in fresh if shape(c) == shape(answer)]
    pool = (alike + [c for c in fresh if c not in alike])[: DECOY_COUNT * 3]
    rng.shuffle(pool)
    pool.sort(key=lambda c: c not in alike)
    return pool[:DECOY_COUNT]


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
