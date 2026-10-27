"""X1: poder mítico neutro. Quem usa escolhe um adversário e a partida para para o duelo.

Antes do duelo a plateia aposta 5 de QI em quem vai ganhar. Depois vêm até 10 perguntas
(4 de Verdadeiro ou Falso, 5 difíceis e 1 impossível), com cada vez menos tempo e sem
habilidades. Perde quem errar uma que o outro acertou; se os dois erram, segue. Se chegar ao
fim, ganha quem somou menos tempo de resposta. Quem perde paga 40% do próprio QI a quem ganha.
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

STATEMENTS_DIR = Path(__file__).parent / "true_false"

INTRO_SECONDS = 3.0  # a animação de entrada; com plateia, a aposta vem depois dela
BET_SECONDS = 8.0
FIRST_SECONDS = 8.0
STEP_SECONDS = 0.5  # cada pergunta tem meio segundo a menos que a anterior
RESULTS_SECONDS = 2.0
END_SECONDS = 6.0
SHARE = 0.4  # do QI de quem perde
BET = 5  # quem acerta recebe o dobro do que apostou
FAVORITE_BONUS = 5
LAYOUT: tuple[tuple[str, int], ...] = (("true_false", 4), ("hard", 5), ("impossible", 1))
TRUE_FALSE_OPTIONS = ["Verdadeiro", "Falso"]

Kind = Literal["true_false", "hard", "impossible"]


class Scorable(Protocol):
    id: str
    score: int


@dataclass
class DuelQuestion:
    id: str
    theme: str
    kind: Kind
    text: str
    options: list[str]
    answer: int
    fact: str
    difficulty: str | None = None  # das frases de V ou F: medium ou hard


@dataclass
class Pick:
    player_id: str
    option: int | None
    correct: bool
    elapsed_ms: int | None


@dataclass
class Duel:
    challenger: str
    rival: str
    questions: list[DuelQuestion]
    bettors: list[str]  # quem pode apostar: os outros jogadores com QI para isso
    bets: dict[str, str] = field(default_factory=dict)
    index: int = -1
    started_at: float = 0
    answers: dict[str, tuple[int, float]] = field(default_factory=dict)
    total_ms: dict[str, int] = field(default_factory=dict)
    picks: list[Pick] = field(default_factory=list)
    winner: str | None = None
    loser: str | None = None
    paid: int = 0
    from_bets: int = 0
    favorite_bonus: int = 0

    @property
    def fighters(self) -> tuple[str, str]:
        return self.challenger, self.rival

    @property
    def question(self) -> DuelQuestion:
        return self.questions[self.index]

    def seconds(self) -> float:
        return FIRST_SECONDS - STEP_SECONDS * self.index

    def deadline(self) -> float:
        return self.started_at + self.seconds()

    def has_next(self) -> bool:
        return self.winner is None and self.index + 1 < len(self.questions)

    def open_next(self, now: float) -> None:
        self.index += 1
        self.started_at = now
        self.answers = {}
        self.picks = []

    def everyone_answered(self) -> bool:
        return all(pid in self.answers for pid in self.fighters)

    def close(self) -> None:
        """Fecha a pergunta: quem errou sozinho perde. Na última, sem erro sozinho, decide o tempo."""
        window_ms = round(self.seconds() * 1000)
        for pid in self.fighters:
            option, at = self.answers.get(pid, (None, None))
            elapsed = min(window_ms, round((at - self.started_at) * 1000)) if at is not None else None
            self.total_ms[pid] = self.total_ms.get(pid, 0) + (window_ms if elapsed is None else elapsed)
            correct = option is not None and option == self.question.answer
            self.picks.append(Pick(player_id=pid, option=option, correct=correct, elapsed_ms=elapsed))
        wrong = [p.player_id for p in self.picks if not p.correct]
        if len(wrong) == 1:
            self.loser = wrong[0]
        elif not self.has_next_question():
            a, b = self.fighters
            self.loser = a if self.total_ms[a] > self.total_ms[b] else b
        if self.loser:
            self.winner = self.rival if self.loser == self.challenger else self.challenger

    def has_next_question(self) -> bool:
        return self.index + 1 < len(self.questions)

    def fill_bets(self, rng: random.Random) -> None:
        """A aposta é obrigatória: quem não escolheu a tempo aposta num dos dois, sorteado."""
        for pid in self.bettors:
            self.bets.setdefault(pid, rng.choice(self.fighters))

    def settle(self, players: list[Scorable]) -> None:
        by_id = {p.id: p for p in players}
        winner, loser = by_id.get(self.winner), by_id.get(self.loser)
        if not winner or not loser:
            return
        self.paid = max(0, loser.score) * round(SHARE * 100) // 100
        loser.score -= self.paid
        backers = sum(choice == self.winner for choice in self.bets.values())
        against = len(self.bets) - backers
        self.from_bets = BET * against
        self.favorite_bonus = FAVORITE_BONUS if backers > against else 0
        winner.score += self.paid + self.from_bets + self.favorite_bonus
        for pid, choice in self.bets.items():
            if bettor := by_id.get(pid):
                bettor.score += BET if choice == self.winner else -BET


def load_statements(directory: Path = STATEMENTS_DIR) -> list[DuelQuestion]:
    """Lê true_false/<tema>.json. O id de cada frase é vf-<arquivo>-<posição>."""
    statements = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text())
        for i, raw in enumerate(data["statements"], start=1):
            statements.append(
                DuelQuestion(
                    id=f"vf-{path.stem}-{i}",
                    theme=data["theme"],
                    kind="true_false",
                    text=raw["text"],
                    options=list(TRUE_FALSE_OPTIONS),
                    answer=0 if raw["answer"] else 1,
                    fact=raw["fact"],
                    difficulty=raw["difficulty"],
                )
            )
    return statements
