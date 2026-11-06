"""Prêmios do fim da partida: as frases que aparecem depois do pódio, em todos os modos.

Cada modo anota o que aconteceu num `Tally` e, no fim, diz quais disputas existem. Cada prêmio vai só
para quem foi mesmo o melhor (ou o pior) naquilo. Quando essa pessoa já levou outro, o prêmio fica de
fora, para ninguém receber uma frase que não é verdade.
"""

import random
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field

from app.events import MatchAward, PowerUpUse

MAX_AWARDS = 3
MIN_COMEBACK_PLACES = 2
MIN_FALL = 10
MIN_SABOTAGES = 2
MIN_HOT_RUN = 4
MIN_COLD_RUN = 3
MAX_QUICK_SECONDS = 5.0  # acima disso não dá para dizer "nem leu"
THEME_SHARE = 0.6  # acertos (ou erros) do tema, para valer a frase
MIN_THEME_QUESTIONS = 3


def team_key(team_id: int) -> str:
    """Prêmios de time disputam junto com os de jogador, com uma chave própria."""
    return f"team:{team_id}"


def award(kind: str, key: str, amount: float, **details) -> MatchAward:
    if key.startswith("team:"):
        return MatchAward(kind=kind, team=int(key.removeprefix("team:")), amount=amount, **details)
    return MatchAward(kind=kind, player_id=key, amount=amount, **details)


@dataclass
class Contest:
    """As notas de quem pode levar o prêmio. `make` monta o prêmio de quem ganhou."""

    kind: str
    scores: dict[str, float]
    lowest: bool = False
    make: Callable[[str, float], MatchAward] | None = None


def draw_awards(contests: list[Contest], eligible: Iterable[str], rng: random.Random) -> list[MatchAward]:
    """A ordem é sorteada para cada partida mostrar uma combinação diferente."""
    allowed = set(eligible)
    contests = list(contests)
    rng.shuffle(contests)
    awards: list[MatchAward] = []
    taken: set[str] = set()
    for contest in contests:
        scores = {key: score for key, score in contest.scores.items() if key in allowed}
        if not scores or len(awards) >= MAX_AWARDS:
            continue
        top = (min if contest.lowest else max)(scores.values())
        winners = [key for key, score in scores.items() if score == top and key not in taken]
        if not winners:
            continue
        winner = rng.choice(winners)
        taken.add(winner)
        make = contest.make or (lambda key, amount, kind=contest.kind: award(kind, key, amount))
        awards.append(make(winner, top))
    return awards


def sabotages(active: Iterable[PowerUpUse], targeted: frozenset, player_ids: list[str]) -> tuple[list[str], list[str]]:
    """Quem jogou e quem levou cada sabotagem da pergunta. A lendária conta uma vez para quem jogou e uma
    para cada atingido; a devolvida pelo Reverso segue contando para quem jogou, e pega nele."""
    thrown: list[str] = []
    received: list[str] = []
    for use in active:
        if use.kind not in targeted:
            continue
        # No Roubo e no Pacto devolvidos, `by` passa a ser quem devolveu e `target`, quem jogou.
        swapped = use.reflected_by and use.by == use.reflected_by
        thrown.append(use.target if swapped else use.by)
        received += [pid for pid in player_ids if (pid != use.by if use.legendary else pid == use.target)]
    return thrown, received


def ranked_ids(players: Iterable) -> list[str]:
    """Na mesma ordem do pódio: mais QI e, no empate, quem respondeu mais rápido."""
    return [p.id for p in sorted(players, key=lambda p: (-p.score, p.answer_ms))]


@dataclass
class Tally:
    """O que a partida vai acumulando, para decidir os prêmios no fim."""

    counts: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    peaks: dict[str, dict[str, float]] = field(default_factory=lambda: defaultdict(dict))
    samples: dict[str, dict[str, list[float]]] = field(default_factory=lambda: defaultdict(lambda: defaultdict(list)))
    running: dict[str, Counter[str]] = field(default_factory=lambda: defaultdict(Counter))
    half_places: dict[str, int] = field(default_factory=dict)

    def add(self, name: str, key: str, amount: float = 1) -> None:
        self.counts[name][key] += amount

    def peak(self, name: str, key: str, value: float) -> bool:
        """Guarda o maior valor. Devolve se esse é o novo recorde."""
        if value > self.peaks[name].get(key, float("-inf")):
            self.peaks[name][key] = value
            return True
        return False

    def sample(self, name: str, key: str, value: float) -> None:
        self.samples[name][key].append(value)

    def run(self, name: str, key: str, going: bool) -> None:
        """Sequência: soma enquanto dura, zera quando quebra, e guarda a maior."""
        self.running[name][key] = self.running[name][key] + 1 if going else 0
        if going:
            self.peak(name, key, self.running[name][key])

    def add_sabotages(self, thrown: Iterable[str], received: Iterable[str]) -> None:
        for pid in thrown:
            self.add("thrown", pid)
        for pid in received:
            self.add("received", pid)

    def counted(self, kind: str, name: str | None = None, minimum: float = 1) -> Contest:
        counts = self.counts[name or kind]
        return Contest(kind, {key: n for key, n in counts.items() if n >= minimum})

    def peaked(self, kind: str, name: str | None = None, minimum: float = 1) -> Contest:
        peaks = self.peaks[name or kind]
        return Contest(kind, {key: v for key, v in peaks.items() if v >= minimum})

    def mean(self, kind: str, name: str, limit: float, min_samples: int) -> Contest:
        """Quem tem a menor média. Média de pouca coisa não diz nada."""
        means = {key: sum(v) / len(v) for key, v in self.samples[name].items() if v and len(v) >= min_samples}
        return Contest(kind, {key: m for key, m in means.items() if m <= limit}, lowest=True)

    def sabotage_contests(self) -> list[Contest]:
        return [
            self.counted("villain", "thrown", MIN_SABOTAGES),
            self.counted("punching_bag", "received", MIN_SABOTAGES),
        ]

    def comeback(self, ranked: list[str]) -> Contest:
        """Compara a posição na metade da partida com a do fim."""
        places = {pid: place for place, pid in enumerate(ranked, start=1)}
        climbs = {pid: was - places[pid] for pid, was in self.half_places.items() if pid in places}
        return Contest(
            "comeback",
            {pid: up for pid, up in climbs.items() if up >= MIN_COMEBACK_PLACES},
            make=lambda pid, _: award("comeback", pid, places[pid], from_place=self.half_places[pid]),
        )
