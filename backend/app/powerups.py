"""Habilidades do modo com poderes.

Quase todas são armadas na revelação e valem na pergunta seguinte, que abre anunciando quem jogou
o quê. As que só fazem sentido depois de ler a pergunta (50/50 e Espiar) são usadas na hora,
pelos ícones na tela da pergunta. Escudo e Reverso valem por até 2 perguntas (o Reverso por até 3,
menos para quem está em 1º) e acabam quando são usados; a Segunda chance vale nas 2 perguntas.
As que chegam ao fim sem uso quebram. Fora da aposta e da pergunta final.

Cada um ganha uma sorteada no início e outra a cada 3 acertos seguidos (qualquer nível). O
lanterna, se estiver muito atrás dos primeiros, ganha uma a cada 3 rodadas seguidas em último.
Dá para guardar no máximo 2 (o anfitrião pode mudar para 1 ou 3); ganhar com as mãos cheias não dá nada.

Cada habilidade ganha na partida tem uma chance pequena de vir como um ataque lendário (maior para o
lanterna): vale em todos os outros jogadores de uma vez e o Reverso não segura.
"""

import random
from typing import Protocol

from app.events import PowerUp, PowerUpUse

# Para quem usa:
#   50/50: tira duas erradas. Escudo: errar não tira QI. Dobro: a resposta vale o dobro (o erro
#   também). Espiar: mostra quantos escolheram cada alternativa até agora. Tempo extra: mais tempo
#   e QI cheio o tempo todo por 3 perguntas. Segunda chance: errou, tenta de novo valendo metade.
#   Reverso (a carta do Uno): a sabotagem que mirar você volta para quem jogou; só você vê que armou.
# Contra outro jogador:
#   Raspadinha: pergunta e alternativas cobertas. Roubo: leva QI do alvo (surpresa).
#   Embaralhar: letras embaralhadas dentro das palavras da pergunta e das alternativas.
#   Acelerador: um terço do tempo e sem QI cheio. Espelho: a pergunta aparece espelhada.
#   Silêncio: sem cronômetro, sem saber quem respondeu e sem QI cheio.
#   Lupa: pergunta e alternativas borradas; só dá para ler arrastando uma lupa por cima.
POWERUPS: tuple[PowerUp, ...] = (
    "fifty_fifty", "shield", "double", "peek", "extra_time", "second_chance", "reverse",
    "scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier",
)
TARGETED: frozenset[PowerUp] = frozenset(
    {"scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier"}
)
INSTANT: frozenset[PowerUp] = frozenset({"fifty_fifty", "peek"})  # usadas durante a pergunta
# Quantas perguntas comuns cada uma dura. Tempo extra e Segunda chance valem em todas; Escudo e
# Reverso acabam quando são usados (o Escudo segura um erro, o Reverso devolve).
LASTING: dict[PowerUp, int] = {"extra_time": 3, "shield": 2, "second_chance": 2, "reverse": 3}
REVERSE_LEADER_ROUNDS = 2  # o Reverso de quem está em 1º ao armar dura menos
BREAKABLE: frozenset[PowerUp] = frozenset({"shield", "second_chance", "reverse"})
MAX_HELD = 2
STREAK_FOR_POWERUP = 3
COMEBACK_ROUNDS = 3
# Distância até o 2º colocado (até o 1º, com 2 jogadores) para o último ganhar habilidade
# (e ter mais chance de lendária).
COMEBACK_GAP = 20
LEGENDARY_CHANCE = 0.05
LEGENDARY_TRAILING_CHANCE = 0.20
LEGENDARY_STEAL_FIXED = 5  # o Roubo lendário tira menos de cada um
FIFTY_FIFTY_REMOVES = 2
# Roubo: o ladrão leva 10 fixos e, se o alvo acertar, mais metade do que ele ganhar; tudo sai do
# alvo. O Escudo que segura o erro do alvo bloqueia o roubo.
STEAL_FIXED = 10
STEAL_GAIN_SHARE = 0.5
DOUBLE_FACTOR = 2
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
