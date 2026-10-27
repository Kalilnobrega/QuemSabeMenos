"""Último de pé: modo battle royale só com Verdadeiro ou Falso.

Cada um começa com 2 vidas; errar ou não responder tira uma, e sem vidas está fora. Se todos os
vivos erram a mesma frase, ninguém perde vida. São 10 frases médias e depois só difíceis. Quando
sobram 2, vira X1: morte súbita, com menos tempo a cada frase, até um errar sozinho.
Sem QI: a colocação é a ordem de eliminação (mesma rodada desempata pelo tempo total de resposta).
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app.duel import TRUE_FALSE_OPTIONS, DuelQuestion
from app.events import Survivor, SurvivalPick, SurvivalView

LIVES = 2
MEDIUM_COUNT = 10
START_SECONDS = 5.0
LEVEL_SECONDS = 3.0
ANSWER_SECONDS = 10.0
RESULTS_SECONDS = 6.0
DUEL_INTRO_SECONDS = 3.0
DUEL_FIRST_SECONDS = 8.0
DUEL_STEP_SECONDS = 0.5  # cada frase do X1 tem meio segundo a menos que a anterior
DUEL_MIN_SECONDS = 3.0
DUEL_RESULTS_SECONDS = 3.0
LATE_SECONDS = 1.0  # tolerância de rede para respostas no limite

Phase = Literal["starting", "level", "answering", "results", "duel_intro", "duel_answering", "duel_results", "finished"]


class SurvivalError(Exception):
    pass


@dataclass
class Contender:
    id: str
    lives: int = LIVES
    out_round: int | None = None  # a rodada em que caiu
    answer_ms: int = 0
    correct: int = 0

    @property
    def alive(self) -> bool:
        return self.out_round is None


@dataclass
class Survival:
    contenders: list[Contender]
    statements: list[DuelQuestion]  # com `difficulty` medium ou hard
    used: set[str]  # ids já sorteados nesta sala, para "jogar de novo" trazer frases novas
    rng: random.Random
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = 0
    duel_round: int = 0  # 1 na primeira frase do X1
    duelists: list[str] = field(default_factory=list)
    question: DuelQuestion | None = None
    answers: dict[str, tuple[int, float]] = field(default_factory=dict)
    picks: list[SurvivalPick] = field(default_factory=list)
    spared: bool = False  # todos os vivos erraram: ninguém perdeu vida
    winner: str | None = None

    @classmethod
    def create(cls, player_ids: list[str], statements: list[DuelQuestion], used: set[str], rng: random.Random, now: float) -> "Survival":
        game = cls(contenders=[Contender(pid) for pid in player_ids], statements=statements, used=used, rng=rng)
        game._enter("starting", now, START_SECONDS)
        return game

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
        if self.in_duel():
            return max(DUEL_MIN_SECONDS, DUEL_FIRST_SECONDS - DUEL_STEP_SECONDS * (self.duel_round - 1))
        return ANSWER_SECONDS

    def difficulty(self) -> Literal["medium", "hard"]:
        return "medium" if self.round <= MEDIUM_COUNT else "hard"

    def deadline(self) -> float:
        """Quando o servidor fecha as respostas: na fase de respostas, com a tolerância de rede."""
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
        if option not in range(len(TRUE_FALSE_OPTIONS)):
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
            self._next_statement(now)
        elif self.phase in ("level", "duel_intro"):
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

    def _next_statement(self, now: float) -> None:
        alive = self.alive_ids()
        if len(alive) <= 1:
            return self._finish(now, alive[0] if alive else None)
        if self.in_duel() and len(self.duelists) < 2:
            return self._finish(now, self.duelists[0] if self.duelists else None)
        self.round += 1
        self.question = self._draw(self.difficulty())
        if len(alive) == 2 and not self.in_duel():
            self.duelists = alive
            self.duel_round = 1
            self._enter("duel_intro", now, DUEL_INTRO_SECONDS)
        elif self.in_duel():
            self.duel_round += 1
            self._open(now)
        elif self.round == MEDIUM_COUNT + 1:
            self._enter("level", now, LEVEL_SECONDS)
        else:
            self._open(now)

    def _open(self, now: float) -> None:
        self.answers = {}
        self.picks = []
        self.spared = False
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
            # Morte súbita: perde quem errou sozinho; se os dois erram ou acertam, segue.
            if len(wrong) == 1 and len(self.picks) == 2:
                loser = self.contender(wrong[0].player_id)
                wrong[0].lost_life = True
                loser.lives = 0
                loser.out_round = self.round
                self.duelists.remove(loser.id)
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

    def _draw(self, difficulty: str) -> DuelQuestion:
        """Sorteia uma frase do nível que ainda não saiu; se acabaram, libera as do nível de novo."""
        level = [s for s in self.statements if s.difficulty == difficulty] or self.statements
        fresh = [s for s in level if s.id not in self.used]
        if not fresh:
            self.used -= {s.id for s in level}
            fresh = level
        statement = self.rng.choice(fresh)
        self.used.add(statement.id)
        return statement

    # --- ranking e visão --------------------------------------------------

    def places(self) -> dict[str, int]:
        """Colocação de cada um: o vencedor, depois quem caiu mais tarde (vivos antes de todos)."""
        def key(c: Contender) -> tuple:
            return (c.id != self.winner, -(c.out_round if c.out_round is not None else 10**6), -c.lives, c.answer_ms)

        return {c.id: i + 1 for i, c in enumerate(sorted(self.contenders, key=key))}

    def view(self, now: float, viewer: str | None, player_ids: list[str]) -> SurvivalView:
        revealed = self.phase in ("results", "duel_results", "finished")
        asking = self.phase in ("answering", "duel_answering", "results", "duel_results")
        places = self.places() if self.phase == "finished" else {}
        q = self.question if asking else None
        return SurvivalView(
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)),
            round=self.round,
            duel_round=self.duel_round,
            medium_count=MEDIUM_COUNT,
            max_lives=LIVES,
            difficulty=self.difficulty() if self.round else "medium",
            text=q.text if q else None,
            theme=q.theme if q else None,
            options=list(TRUE_FALSE_OPTIONS),
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
