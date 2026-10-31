"""Chutômetro: perguntas de número. Cada um digita um chute; quanto mais perto da resposta, mais QI.

O erro é medido em % da resposta (ou da `scale` da pergunta, para anos e números pequenos, em que
a porcentagem da resposta não faz sentido). Os níveis seguem o clássico: fáceis, médias e difíceis,
na mesma divisão. Sem aposta, final impossível nem poderes.
Fases: starting → (answering → results) por pergunta, com level quando o nível muda → finished.
Não tem tempo de leitura: a pergunta já abre para chutar, e os 20 segundos já incluem ler.
"""

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app.events import EstimateGuess, EstimateScoring, EstimateView
from app.game import point_scale as scale_for, split_by_difficulty

ESTIMATES_DIR = Path(__file__).parent / "estimates"
ROUND_OPTIONS = (10, 15, 20)
START_SECONDS = 5.0
LEVEL_SECONDS = 3.0  # a tela de "Próximo nível", como no clássico
ANSWER_SECONDS = 20.0
RESULTS_SECONDS = 10.0
LATE_SECONDS = 1.0  # tolerância de rede para chutes no limite
MAX_LOSS_FACTOR = 3  # a perda chega ao máximo no triplo do erro em que o ganho zera


@dataclass(frozen=True)
class Scoring:
    """Pontos contínuos, em linha reta: o ganho cai de `max_points` (erro quase zero) até 0 em
    `break_even` % de erro; daí em diante perde, até `max_loss` no triplo desse erro (e não passa
    disso). Cravar soma `exact_bonus`. Sem chute, perde o máximo."""

    max_points: int
    exact_bonus: int
    break_even: float
    max_loss: int

    @property
    def max_loss_at(self) -> float:
        return self.break_even * MAX_LOSS_FACTOR


# Como no clássico: a fácil é obrigação (ganha pouco, perde muito) e a difícil vale o risco.
SCORING: dict[str, Scoring] = {
    "easy": Scoring(max_points=8, exact_bonus=4, break_even=20, max_loss=-20),
    "medium": Scoring(max_points=16, exact_bonus=8, break_even=30, max_loss=-15),
    "hard": Scoring(max_points=24, exact_bonus=12, break_even=35, max_loss=-10),
}

Phase = Literal["starting", "level", "answering", "results", "finished"]


class EstimateError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


class EstimateQuestion(BaseModel):
    id: str
    theme: str
    difficulty: Literal["easy", "medium", "hard"]
    text: str
    answer: float
    unit: str | None = None  # aparece do lado do campo do chute ("km", "anos")
    scale: float | None = Field(default=None, gt=0)  # base do erro em %; sem ela, a própria resposta
    fact: str = Field(min_length=1)


class EstimateFile(BaseModel):
    theme: str
    questions: list[dict]


def load_estimates(directory: Path = ESTIMATES_DIR) -> list[EstimateQuestion]:
    """Lê estimates/<tema>.json. O id de cada pergunta é chute-<arquivo>-<posição>."""
    bank = []
    for path in sorted(directory.glob("*.json")):
        data = EstimateFile.model_validate(json.loads(path.read_text()))
        for i, raw in enumerate(data.questions, start=1):
            bank.append(EstimateQuestion(id=f"chute-{path.stem}-{i}", theme=data.theme, **raw))
    return bank


def error_percent(question: EstimateQuestion, value: float) -> float:
    reference = question.scale or abs(question.answer) or 1
    return abs(value - question.answer) / reference * 100


def guess_points(error: float | None, difficulty: str = "medium", scale: float = 1.0) -> int:
    """`scale`: como no clássico, partidas curtas valem mais por pergunta (20/N)."""
    rules = SCORING[difficulty]
    if error is None:
        points = rules.max_loss
    elif error == 0:
        points = rules.max_points + rules.exact_bonus
    elif error <= rules.break_even:
        points = rules.max_points * (1 - error / rules.break_even)
    else:
        beyond = (error - rules.break_even) / (rules.max_loss_at - rules.break_even)
        points = rules.max_loss * min(1.0, beyond)
    return _round(points * scale)


def _round(value: float) -> int:
    """Meio ponto arredonda para longe do zero (2,5 → 3 e −2,5 → −3), sem o arredondamento do banqueiro."""
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


class Scorable(Protocol):
    id: str
    score: int
    answer_ms: int


@dataclass
class Estimate:
    questions: list[EstimateQuestion]
    point_scale: float = 1.0  # 20/N, como no clássico
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = -1  # índice da pergunta atual
    guesses: dict[str, tuple[float, float]] = field(default_factory=dict)  # chute e quando
    results: list[EstimateGuess] = field(default_factory=list)
    ready: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls, pool: list[EstimateQuestion], rounds: int, used: set[str], rng: random.Random, now: float
    ) -> "Estimate":
        """Sorteia as perguntas das fáceis às difíceis, como no clássico, preferindo as que a sala ainda não viu."""
        questions = []
        for difficulty, count in split_by_difficulty(rounds).items():
            fresh = [q for q in pool if q.difficulty == difficulty and q.id not in used]
            stale = [q for q in pool if q.difficulty == difficulty and q.id in used]
            rng.shuffle(fresh)
            rng.shuffle(stale)
            questions += (fresh + stale)[:count]
        game = cls(questions=questions, point_scale=scale_for(rounds))
        used |= {q.id for q in game.questions}
        game._enter("starting", now, START_SECONDS)
        return game

    @property
    def question(self) -> EstimateQuestion:
        return self.questions[self.round]

    def guess(self, player_id: str, value: float, now: float) -> None:
        if self.phase != "answering":
            raise EstimateError("Agora não dá para chutar.")
        if player_id in self.guesses:
            raise EstimateError("Você já chutou.")
        if now > self.phase_ends_at + LATE_SECONDS:
            raise EstimateError("O tempo acabou.")
        self.guesses[player_id] = (value, now)

    def everyone_answered(self, connected: list[str]) -> bool:
        return all(pid in self.guesses for pid in connected)

    def mark_ready(self, player_id: str) -> None:
        if self.phase != "results":
            raise EstimateError("Agora não dá para pular.")
        self.ready.add(player_id)

    def everyone_ready(self, connected: list[str]) -> bool:
        return all(pid in self.ready for pid in connected)

    def advance(self, now: float, players: list[Scorable]) -> None:
        """Passa para a próxima fase. O main.py chama quando o tempo acaba (ou todos fizeram a sua parte)."""
        if self.phase == "level":
            self._enter("answering", now, ANSWER_SECONDS)
        elif self.phase == "answering":
            self._close(now, players)
        elif self.phase in ("starting", "results"):
            if self.round + 1 >= len(self.questions):
                self._enter("finished", now, 0)
                return
            self.round += 1
            self.guesses = {}
            self.results = []
            self.ready = set()
            if self.round > 0 and self.question.difficulty != self.questions[self.round - 1].difficulty:
                self._enter("level", now, LEVEL_SECONDS)
            else:
                self._enter("answering", now, ANSWER_SECONDS)

    def _close(self, now: float, players: list[Scorable]) -> None:
        q = self.question
        self.results = []
        for player in players:
            guessed = self.guesses.get(player.id)
            if guessed is None:
                error, elapsed = None, ANSWER_SECONDS
            else:
                error, elapsed = error_percent(q, guessed[0]), max(0.0, guessed[1] - self.phase_started_at)
            delta = guess_points(error, q.difficulty, self.point_scale)
            player.score += delta
            player.answer_ms += round(elapsed * 1000)
            self.results.append(
                EstimateGuess(
                    player_id=player.id,
                    value=guessed[0] if guessed else None,
                    error_percent=None if error is None else round(error, 1),
                    exact=error == 0,
                    delta=delta,
                    elapsed_ms=round(elapsed * 1000) if guessed else None,
                )
            )
        # Do mais perto para o mais longe; quem não chutou fica no fim.
        self.results.sort(key=lambda r: (r.error_percent is None, r.error_percent or 0, r.elapsed_ms or 0))
        self._enter("results", now, RESULTS_SECONDS)

    def deadline(self) -> float:
        return self.phase_ends_at + (LATE_SECONDS if self.phase == "answering" else 0)

    def view(self, now: float, viewer: str | None = None) -> EstimateView:
        q = self.question if self.round >= 0 else None
        reveal = self.phase in ("results", "finished") and q is not None
        mine = self.guesses.get(viewer) if viewer else None
        return EstimateView(
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)),
            round=self.round + 1,
            total_rounds=len(self.questions),
            theme=q.theme if q else None,
            difficulty=q.difficulty if q else self.questions[0].difficulty,
            text=q.text if q and self.phase not in ("starting", "level") else None,
            unit=q.unit if q else None,
            answered=list(self.guesses),
            my_guess=mine[0] if mine else None,
            answer=q.answer if reveal else None,
            reference=(q.scale or abs(q.answer) or 1) if reveal else None,
            fact=q.fact if reveal else None,
            guesses=self.results if reveal else [],
            scoring=self._scoring_view(q.difficulty if q else self.questions[0].difficulty),
            ready=sorted(self.ready),
        )

    def _scoring_view(self, difficulty: str) -> EstimateScoring:
        rules = SCORING[difficulty]
        return EstimateScoring(
            max_points=_round(rules.max_points * self.point_scale),
            exact_bonus=_round(rules.exact_bonus * self.point_scale),
            break_even_percent=rules.break_even,
            max_loss=_round(rules.max_loss * self.point_scale),
            max_loss_percent=rules.max_loss_at,
        )

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds
