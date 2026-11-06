"""Prêmios do fim do Chutômetro: as frases engraçadas que aparecem depois do pódio.

Cada prêmio vai só para quem foi mesmo o melhor (ou o pior) naquilo. Quando essa pessoa já levou
outro, o prêmio fica de fora, para ninguém receber uma frase que não é verdade.
"""

import math
import random
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.events import EstimateAward, EstimateGuess

MAX_AWARDS = 3
MIN_ABSURD_ERROR = 50.0  # abaixo disso o chute não tem nada de absurdo
MAX_SHARP_ERROR = 30.0  # acima disso o "errou só" vira ironia sem querer
MAX_QUICK_SECONDS = 8.0  # acima disso não dá para dizer "nem leu"
MIN_COMEBACK_PLACES = 2
MIN_FALL = 10
MIN_SABOTAGES = 2


@dataclass
class WorstGuess:
    error: float
    value: float
    answer: float
    unit: str | None


@dataclass
class AwardTally:
    """O que a partida vai acumulando, pergunta por pergunta."""

    questions: int = 0
    errors: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    seconds: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    exact: Counter[str] = field(default_factory=Counter)
    worst: dict[str, WorstGuess] = field(default_factory=dict)
    falls: dict[str, int] = field(default_factory=dict)
    stolen: Counter[str] = field(default_factory=Counter)
    thrown: Counter[str] = field(default_factory=Counter)
    received: Counter[str] = field(default_factory=Counter)
    half_places: dict[str, int] = field(default_factory=dict)

    def add_round(
        self,
        results: Iterable[EstimateGuess],
        answer: float,
        unit: str | None,
        thrown: Iterable[str] = (),
        received: Iterable[str] = (),
    ) -> None:
        self.questions += 1
        self.thrown.update(thrown)
        self.received.update(received)
        for guess in results:
            pid = guess.player_id
            if guess.stolen:
                self.stolen[pid] += guess.stolen
            if guess.total < 0:
                self.falls[pid] = max(self.falls.get(pid, 0), -guess.total)
            if guess.value is None or guess.error_percent is None:
                continue
            if guess.nudged_from is not None or guess.swapped_from is not None or guess.copied_from is not None:
                continue  # o chute que valeu não foi o da pessoa: não dá para culpar nem elogiar
            self.errors[pid].append(guess.error_percent)
            if guess.elapsed_ms is not None:
                self.seconds[pid].append(guess.elapsed_ms / 1000)
            if guess.exact:
                self.exact[pid] += 1
            if pid not in self.worst or guess.error_percent > self.worst[pid].error:
                self.worst[pid] = WorstGuess(guess.error_percent, guess.value, answer, unit)

    def draw(self, ranked: list[str], rng: random.Random) -> list[EstimateAward]:
        """`ranked`: do 1º ao último. A ordem é sorteada para cada partida mostrar uma combinação diferente."""
        places = {pid: place for place, pid in enumerate(ranked, start=1)}
        contests = self._contests(places)
        rng.shuffle(contests)
        awards: list[EstimateAward] = []
        taken: set[str] = set()
        for scores, lowest, award_for in contests:
            scores = {pid: score for pid, score in scores.items() if pid in places}
            if not scores or len(awards) >= MAX_AWARDS:
                continue
            top = (min if lowest else max)(scores.values())
            winners = [pid for pid, score in scores.items() if score == top and pid not in taken]
            if not winners:
                continue
            winner = rng.choice(winners)
            taken.add(winner)
            awards.append(award_for(winner, top))
        return awards

    def _contests(self, places: dict[str, int]) -> list:
        """Cada disputa: as notas de quem pode levar, se ganha a menor nota, e como montar o prêmio."""
        enough = math.ceil(self.questions / 2)  # média de um chute só não diz nada

        def means(values: dict[str, list[float]], limit: float) -> dict[str, float]:
            averages = {pid: sum(v) / len(v) for pid, v in values.items() if len(v) >= enough}
            return {pid: mean for pid, mean in averages.items() if mean <= limit}

        def simple(kind: str):
            return lambda pid, amount: EstimateAward(kind=kind, player_id=pid, amount=amount)

        def absurd(pid: str, _: float) -> EstimateAward:
            worst = self.worst[pid]
            return EstimateAward(
                kind="absurd",
                player_id=pid,
                amount=worst.error,
                guess=worst.value,
                answer=worst.answer,
                unit=worst.unit,
            )

        def comeback(pid: str, _: float) -> EstimateAward:
            return EstimateAward(kind="comeback", player_id=pid, amount=places[pid], from_place=self.half_places[pid])

        climbs = {pid: was - places[pid] for pid, was in self.half_places.items() if pid in places}
        return [
            (
                {pid: w.error for pid, w in self.worst.items() if w.error >= MIN_ABSURD_ERROR},
                False,
                absurd,
            ),
            (means(self.errors, MAX_SHARP_ERROR), True, simple("sharp")),
            (dict(self.exact), False, simple("exact")),
            (means(self.seconds, MAX_QUICK_SECONDS), True, simple("quick")),
            ({pid: up for pid, up in climbs.items() if up >= MIN_COMEBACK_PLACES}, False, comeback),
            ({pid: fall for pid, fall in self.falls.items() if fall >= MIN_FALL}, False, simple("fall")),
            ({pid: n for pid, n in self.thrown.items() if n >= MIN_SABOTAGES}, False, simple("villain")),
            ({pid: n for pid, n in self.received.items() if n >= MIN_SABOTAGES}, False, simple("punching_bag")),
            (dict(self.stolen), False, simple("thief")),
        ]
