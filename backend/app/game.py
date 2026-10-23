"""Modo clássico: perguntas de múltipla escolha com pontos de QI.

Lógica pura: quem chama passa o relógio (`now`) e o main.py cuida das esperas.
"""

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from app.events import Difficulty, GameView, QuestionView, RoundResult

QUESTIONS_DIR = Path(__file__).parent / "questions"

# A partida vai das fáceis às difíceis e termina com uma pergunta impossível.
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
FINAL_DIFFICULTY: Difficulty = "impossible"
OPTION_COUNT = {"easy": 4, "medium": 4, "hard": 4, "impossible": 6}
# Pontuação calibrada para, numa partida de 15, antes da pergunta final, um jogador
# médio terminar perto de 80 e um bom perto de 150. Ajuste aqui depois de jogar.
STARTING_IQ = 50
# Acerto rende do mínimo (respondeu no último instante) ao máximo (na hora).
CORRECT_POINTS = {"easy": (0, 0), "medium": (6, 12), "hard": (15, 25), "impossible": (35, 35)}
WRONG_PENALTY = {"easy": -15, "medium": -7, "hard": -2, "impossible": 0}
# Quem responde nos primeiros segundos leva o máximo; depois o valor cai até o mínimo.
SPEED_GRACE_SECONDS = 3.0
NO_ANSWER_PENALTY = -10

# Velocidade do efeito de digitação; o tempo de resposta só começa depois.
TYPING_SECONDS_PER_CHAR = 0.035
MIN_READING_SECONDS = 1.5
MAX_READING_SECONDS = 6.0
# O resultado fica na tela o suficiente para ler a curiosidade.
RESULTS_SECONDS_PER_CHAR = 0.055
MIN_RESULTS_SECONDS = 7.0
MAX_RESULTS_SECONDS = 12.0


class GameError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


class Question(BaseModel):
    id: str
    theme: str
    difficulty: Difficulty
    text: str
    options: list[str]
    answer: int = Field(ge=0)
    fact: str = Field(min_length=1)  # curiosidade ou explicação, mostrada depois da resposta

    @model_validator(mode="after")
    def check_options(self) -> "Question":
        expected = OPTION_COUNT[self.difficulty]
        if len(self.options) != expected:
            raise ValueError(f"{self.id}: {self.difficulty} precisa de {expected} alternativas")
        if self.answer >= expected:
            raise ValueError(f"{self.id}: answer fora das alternativas")
        return self


class ThemeFile(BaseModel):
    theme: str
    questions: list[dict]


def load_bank(directory: Path = QUESTIONS_DIR) -> list[Question]:
    """Lê questions/<tema>.json. O id de cada pergunta é <arquivo>-<posição>."""
    bank = []
    for path in sorted(directory.glob("*.json")):
        data = ThemeFile.model_validate(json.loads(path.read_text()))
        for i, raw in enumerate(data.questions, start=1):
            bank.append(Question(id=f"{path.stem}-{i}", theme=data.theme, **raw))
    return bank


def split_by_difficulty(rounds: int) -> dict[Difficulty, int]:
    """15 → 5/5/5; 10 → 4/3/3. Sobras vão para as mais fáceis."""
    return {d: rounds // 3 + (1 if i < rounds % 3 else 0) for i, d in enumerate(DIFFICULTIES)}


def pick_questions(bank: list[Question], rounds: int, used: set[str], rng: random.Random) -> list[Question]:
    """Sorteia as perguntas da partida, das fáceis às difíceis, evitando as já usadas na sala.

    A última é a pergunta final, impossível, quando o banco tem alguma.
    As alternativas são embaralhadas para a certa não ficar sempre na mesma posição.
    """
    has_final = any(q.difficulty == FINAL_DIFFICULTY for q in bank)
    counts = split_by_difficulty(rounds - 1 if has_final else rounds)
    if has_final:
        counts[FINAL_DIFFICULTY] = 1
    picked = []
    for difficulty, count in counts.items():
        pool = [q for q in bank if q.difficulty == difficulty]
        fresh = [q for q in pool if q.id not in used]
        stale = [q for q in pool if q.id in used]
        rng.shuffle(fresh)
        rng.shuffle(stale)
        picked += (fresh + stale)[:count]
    return [_shuffle_options(q, rng) for q in picked]


def _shuffle_options(question: Question, rng: random.Random) -> Question:
    order = list(range(len(question.options)))
    rng.shuffle(order)
    return question.model_copy(
        update={"options": [question.options[i] for i in order], "answer": order.index(question.answer)}
    )


def reading_seconds(text: str) -> float:
    return min(MAX_READING_SECONDS, max(MIN_READING_SECONDS, len(text) * TYPING_SECONDS_PER_CHAR))


def results_seconds(fact: str) -> float:
    return min(MAX_RESULTS_SECONDS, max(MIN_RESULTS_SECONDS, 4 + len(fact) * RESULTS_SECONDS_PER_CHAR))


def points(difficulty: Difficulty, correct: bool | None, remaining_fraction: float = 0) -> int:
    """correct=None significa que não respondeu."""
    if correct is None:
        return NO_ANSWER_PENALTY
    if not correct:
        return WRONG_PENALTY[difficulty]
    low, high = CORRECT_POINTS[difficulty]
    return round(low + (high - low) * max(0.0, min(1.0, remaining_fraction)))


class Scorable(Protocol):
    id: str
    score: int
    answer_ms: int  # tempo total de resposta na partida, para desempate


@dataclass
class Answer:
    option: int
    at: float


@dataclass
class Game:
    questions: list[Question]
    answer_seconds: float
    round: int = -1  # índice da pergunta atual; -1 antes de começar
    phase: Literal["reading", "answering", "results", "finished"] = "reading"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    answers: dict[str, Answer] = field(default_factory=dict)
    results: list[RoundResult] = field(default_factory=list)

    @property
    def question(self) -> Question:
        return self.questions[self.round]

    @property
    def has_next_round(self) -> bool:
        return self.round + 1 < len(self.questions)

    def start_round(self, now: float) -> None:
        self.round += 1
        self.answers = {}
        self.results = []
        self._enter("reading", now, reading_seconds(self.question.text))

    def open_answers(self, now: float) -> None:
        self._enter("answering", now, self.answer_seconds)

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase != "answering" or now > self.phase_ends_at:
            raise GameError("Agora não dá para responder.")
        if player_id in self.answers:
            raise GameError("Você já respondeu.")
        if not 0 <= option < len(self.question.options):
            raise GameError("Alternativa inválida.")
        self.answers[player_id] = Answer(option, now)

    def everyone_answered(self, player_ids: list[str]) -> bool:
        return all(pid in self.answers for pid in player_ids)

    def speed_fraction(self, elapsed: float) -> float:
        """1 dentro da carência, caindo até 0 no fim do tempo de resposta."""
        decay = self.answer_seconds - SPEED_GRACE_SECONDS
        if elapsed <= SPEED_GRACE_SECONDS or decay <= 0:
            return 1.0
        return max(0.0, 1 - (elapsed - SPEED_GRACE_SECONDS) / decay)

    def close_round(self, players: list[Scorable], now: float) -> None:
        """Calcula os pontos da rodada e aplica no placar dos jogadores."""
        difficulty = self.question.difficulty
        self.results = []
        for player in players:
            answer = self.answers.get(player.id)
            if answer is None:
                correct, delta = False, points(difficulty, None)
                elapsed = self.answer_seconds
            else:
                correct = answer.option == self.question.answer
                elapsed = self.answer_seconds - (self.phase_ends_at - answer.at)
                delta = points(difficulty, correct, self.speed_fraction(elapsed))
            player.score += delta
            player.answer_ms += round(max(0.0, elapsed) * 1000)
            self.results.append(
                RoundResult(player_id=player.id, option=answer.option if answer else None, correct=correct, delta=delta)
            )
        self._enter("results", now, results_seconds(self.question.fact))

    def finish(self, now: float) -> None:
        self._enter("finished", now, 0)

    def view(self, now: float) -> GameView:
        q = self.question
        show_answer = self.phase in ("results", "finished")
        return GameView(
            round=self.round + 1,
            total_rounds=len(self.questions),
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)),
            question=QuestionView(text=q.text, options=q.options, theme=q.theme, difficulty=q.difficulty),
            answered=list(self.answers),
            correct_option=q.answer if show_answer else None,
            fact=q.fact if show_answer else None,
            results=self.results,
        )

    def _enter(self, phase: Literal["reading", "answering", "results", "finished"], now: float, seconds: float):
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds
