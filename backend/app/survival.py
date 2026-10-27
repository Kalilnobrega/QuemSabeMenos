"""Último de pé: battle royale com vidas. Errar ou não responder tira uma vida; sem vidas, está fora.

Duas versões (`Rules`): Verdadeiro ou Falso (2 vidas, 10 médias e depois difíceis) e Alternativas
(3 vidas, 5 fáceis, 10 médias e depois difíceis). Se todos os vivos erram a mesma pergunta, ninguém
perde vida. Quando sobram 2, vira X1: morte súbita, com menos tempo a cada pergunta, até um errar
sozinho. Nas Alternativas, se o X1 passa de 10 perguntas, só vêm impossíveis, e nelas os dois
acertando ganha o mais rápido.
Sem QI: a colocação é a ordem de eliminação (mesma rodada desempata pelo tempo total de resposta).
"""

import random
from dataclasses import dataclass, field
from typing import Literal, Protocol

from app.duel import TRUE_FALSE_OPTIONS
from app.events import Survivor, SurvivalKind, SurvivalPick, SurvivalView
from app.game import reading_seconds

START_SECONDS = 5.0
LEVEL_SECONDS = 3.0
RESULTS_SECONDS = 6.0
DUEL_INTRO_SECONDS = 3.0
DUEL_RESULTS_SECONDS = 3.0
LATE_SECONDS = 1.0  # tolerância de rede para respostas no limite

Difficulty = Literal["easy", "medium", "hard", "impossible"]
Phase = Literal[
    "starting", "level", "reading", "answering", "results",
    "duel_intro", "duel_reading", "duel_answering", "duel_results", "finished",
]


@dataclass(frozen=True)
class Rules:
    lives: int
    levels: tuple[tuple[Difficulty, int], ...]  # nível e quantas perguntas; depois da última, só difíceis
    answer_seconds: float
    reading: bool  # fase de leitura antes de liberar as respostas
    duel_first_seconds: float
    duel_step_seconds: float  # cada pergunta do X1 tem esse tanto a menos que a anterior
    duel_min_seconds: float
    duel_impossible_after: int | None  # depois dessa pergunta do X1, só impossíveis


RULES: dict[SurvivalKind, Rules] = {
    "true_false": Rules(
        lives=2, levels=(("medium", 10),), answer_seconds=10.0, reading=False,
        duel_first_seconds=8.0, duel_step_seconds=0.5, duel_min_seconds=3.0, duel_impossible_after=None,
    ),
    "choices": Rules(
        lives=3, levels=(("easy", 5), ("medium", 10)), answer_seconds=15.0, reading=True,
        duel_first_seconds=12.0, duel_step_seconds=1.0, duel_min_seconds=5.0, duel_impossible_after=10,
    ),
}


class SurvivalError(Exception):
    pass


class Asked(Protocol):
    """Uma pergunta do banco (app.game.Question) ou uma frase de V ou F (app.duel.DuelQuestion)."""

    id: str
    theme: str
    difficulty: str | None
    text: str
    options: list[str]
    answer: int
    fact: str


@dataclass
class Contender:
    id: str
    lives: int
    out_round: int | None = None  # a rodada em que caiu
    answer_ms: int = 0
    correct: int = 0

    @property
    def alive(self) -> bool:
        return self.out_round is None


@dataclass
class Survival:
    kind: SurvivalKind
    contenders: list[Contender]
    pool: list[Asked]  # perguntas dos temas escolhidos, de todos os níveis
    used: set[str]  # ids já sorteados nesta sala, para "jogar de novo" trazer perguntas novas
    rng: random.Random
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = 0
    duel_round: int = 0  # 1 na primeira pergunta do X1
    duelists: list[str] = field(default_factory=list)
    question: Asked | None = None
    answers: dict[str, tuple[int, float]] = field(default_factory=dict)
    picks: list[SurvivalPick] = field(default_factory=list)
    spared: bool = False  # todos os vivos erraram: ninguém perdeu vida
    winner: str | None = None

    @classmethod
    def create(
        cls, kind: SurvivalKind, player_ids: list[str], pool: list[Asked], used: set[str], rng: random.Random, now: float
    ) -> "Survival":
        lives = RULES[kind].lives
        game = cls(kind=kind, contenders=[Contender(pid, lives) for pid in player_ids], pool=pool, used=used, rng=rng)
        game._enter("starting", now, START_SECONDS)
        return game

    @property
    def rules(self) -> Rules:
        return RULES[self.kind]

    # --- consultas --------------------------------------------------------

    def contender(self, player_id: str) -> Contender | None:
        return next((c for c in self.contenders if c.id == player_id), None)

    def alive_ids(self) -> list[str]:
        return [c.id for c in self.contenders if c.alive]

    def in_duel(self) -> bool:
        return bool(self.duelists)

    def answering_ids(self) -> list[str]:
        return list(self.duelists) if self.in_duel() else self.alive_ids()

    def everyone_answered(self, connected: list[str]) -> bool:
        return all(pid in self.answers for pid in self.answering_ids() if pid in connected)

    def answer_seconds(self) -> float:
        r = self.rules
        if self.in_duel():
            return max(r.duel_min_seconds, r.duel_first_seconds - r.duel_step_seconds * (self.duel_round - 1))
        return r.answer_seconds

    def difficulty(self, round_: int | None = None) -> Difficulty:
        """O nível da rodada (a atual, se não disser): segue `levels` e depois só difíceis."""
        round_ = self.round if round_ is None else round_
        if self.in_duel() and self.rules.duel_impossible_after and self.duel_round > self.rules.duel_impossible_after:
            return "impossible"
        for level, count in self.rules.levels:
            if round_ <= count:
                return level
            round_ -= count
        return "hard"

    def deadline(self) -> float:
        """Quando o servidor fecha a fase: nas respostas, com a tolerância de rede."""
        late = LATE_SECONDS if self.phase in ("answering", "duel_answering") else 0
        return self.phase_ends_at + late

    # --- ações ------------------------------------------------------------

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase not in ("answering", "duel_answering"):
            raise SurvivalError("Não dá para responder agora.")
        if player_id not in self.answering_ids():
            raise SurvivalError("Você está fora desta rodada.")
        if player_id in self.answers:
            raise SurvivalError("Você já respondeu.")
        if option not in range(len(self.question.options)):
            raise SurvivalError("Resposta inválida.")
        if now > self.phase_ends_at + LATE_SECONDS:
            raise SurvivalError("O tempo acabou.")
        self.answers[player_id] = (option, now)

    def drop(self, player_id: str) -> None:
        """Quem sai da sala está fora na hora."""
        if (c := self.contender(player_id)) and c.alive:
            c.lives = 0
            c.out_round = self.round
        if player_id in self.duelists and self.phase != "finished":
            self.duelists.remove(player_id)

    def advance(self, now: float) -> None:
        """Passa para a próxima fase. O main.py chama quando o tempo acaba (ou todos responderam)."""
        if self.phase in ("answering", "duel_answering"):
            self._close(now)
        elif self.phase in ("starting", "results", "duel_results"):
            self._next_question(now)
        elif self.phase in ("level", "duel_intro"):
            self._read(now)
        elif self.phase in ("reading", "duel_reading"):
            self._open(now)

    # --- transições -------------------------------------------------------

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds

    def _finish(self, now: float, winner: str | None) -> None:
        self.winner = winner
        self.duelists = []
        self._enter("finished", now, 0)

    def _next_question(self, now: float) -> None:
        alive = self.alive_ids()
        if len(alive) <= 1:
            return self._finish(now, alive[0] if alive else None)
        if self.in_duel() and len(self.duelists) < 2:
            return self._finish(now, self.duelists[0] if self.duelists else None)
        self.round += 1
        if len(alive) == 2 and not self.in_duel():
            self.duelists = alive
            self.duel_round = 1
            self.question = self._draw(self.difficulty())
            self._enter("duel_intro", now, DUEL_INTRO_SECONDS)
            return
        if self.in_duel():
            self.duel_round += 1
        self.question = self._draw(self.difficulty())
        if not self.in_duel() and self.round > 1 and self.difficulty() != self.difficulty(self.round - 1):
            self._enter("level", now, LEVEL_SECONDS)
        else:
            self._read(now)

    def _read(self, now: float) -> None:
        self.answers = {}
        self.picks = []
        self.spared = False
        if not self.rules.reading:
            return self._open(now)
        self._enter("duel_reading" if self.in_duel() else "reading", now, reading_seconds(self.question.text))

    def _open(self, now: float) -> None:
        self._enter("duel_answering" if self.in_duel() else "answering", now, self.answer_seconds())

    def _close(self, now: float) -> None:
        window_ms = round(self.answer_seconds() * 1000)
        for pid in self.answering_ids():
            c = self.contender(pid)
            option, at = self.answers.get(pid, (None, None))
            elapsed = min(window_ms, round((at - self.phase_started_at) * 1000)) if at is not None else None
            correct = option is not None and option == self.question.answer
            c.answer_ms += window_ms if elapsed is None else elapsed
            c.correct += correct
            self.picks.append(SurvivalPick(player_id=pid, option=option, correct=correct, elapsed_ms=elapsed, lost_life=False))
        wrong = [p for p in self.picks if not p.correct]
        if self.in_duel():
            self._close_duel(wrong)
            self._enter("duel_results", now, DUEL_RESULTS_SECONDS)
            return
        self.spared = len(wrong) == len(self.picks) and len(self.picks) > 0
        if not self.spared:
            for pick in wrong:
                c = self.contender(pick.player_id)
                pick.lost_life = True
                c.lives -= 1
                if c.lives <= 0:
                    c.out_round = self.round
        self._enter("results", now, RESULTS_SECONDS)

    def _close_duel(self, wrong: list[SurvivalPick]) -> None:
        """Morte súbita: perde quem errou sozinho; se os dois erram ou acertam, segue.
        Na impossível, os dois acertando, perde o mais lento."""
        if len(self.picks) < 2:
            return
        loser = None
        if len(wrong) == 1:
            loser = wrong[0]
        elif not wrong and self.question.difficulty == "impossible":
            a, b = self.picks
            if a.elapsed_ms != b.elapsed_ms:
                loser = a if a.elapsed_ms > b.elapsed_ms else b
        if loser:
            c = self.contender(loser.player_id)
            loser.lost_life = True
            c.lives = 0
            c.out_round = self.round
            self.duelists.remove(c.id)

    def _draw(self, difficulty: str) -> Asked:
        """Sorteia uma pergunta do nível que ainda não saiu; se acabaram, libera as do nível de novo.
        As alternativas das perguntas do banco vêm embaralhadas."""
        level = [q for q in self.pool if q.difficulty == difficulty] or [q for q in self.pool if q.difficulty == "hard"] or self.pool
        fresh = [q for q in level if q.id not in self.used]
        if not fresh:
            self.used -= {q.id for q in level}
            fresh = level
        question = self.rng.choice(fresh)
        self.used.add(question.id)
        if self.kind == "true_false":
            return question
        order = list(range(len(question.options)))
        self.rng.shuffle(order)
        return question.model_copy(update={"options": [question.options[i] for i in order], "answer": order.index(question.answer)})

    # --- ranking e visão --------------------------------------------------

    def places(self) -> dict[str, int]:
        """Colocação de cada um: o vencedor, depois quem caiu mais tarde (vivos antes de todos)."""

        def key(c: Contender) -> tuple:
            return (c.id != self.winner, -(c.out_round if c.out_round is not None else 10**6), -c.lives, c.answer_ms)

        return {c.id: i + 1 for i, c in enumerate(sorted(self.contenders, key=key))}

    def view(self, now: float, viewer: str | None, player_ids: list[str]) -> SurvivalView:
        revealed = self.phase in ("results", "duel_results")
        showing = self.phase in ("reading", "duel_reading", "answering", "duel_answering", "results", "duel_results")
        places = self.places() if self.phase == "finished" else {}
        q = self.question if showing else None
        counts = dict(self.rules.levels)
        return SurvivalView(
            kind=self.kind,
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)),
            round=self.round,
            duel_round=self.duel_round,
            easy_count=counts.get("easy", 0),
            medium_count=counts.get("medium", 0),
            max_lives=self.rules.lives,
            difficulty=self.difficulty() if self.round else self.rules.levels[0][0],
            text=q.text if q else None,
            theme=q.theme if q else None,
            options=q.options if q else list(TRUE_FALSE_OPTIONS if self.kind == "true_false" else []),
            answered=[pid for pid in self.answers if pid in player_ids],
            my_answer=self.answers[viewer][0] if viewer in self.answers else None,
            picks=self.picks if revealed else [],
            correct_option=q.answer if q and revealed else None,
            fact=q.fact if q and revealed else None,
            spared=self.spared,
            duelists=list(self.duelists),
            next_seconds=self.answer_seconds() if self.in_duel() else None,
            winner=self.winner,
            survivors=[
                Survivor(player_id=c.id, lives=c.lives, out_round=c.out_round, correct=c.correct, answer_ms=c.answer_ms, place=places.get(c.id))
                for c in self.contenders
                if c.id in player_ids
            ],
        )
