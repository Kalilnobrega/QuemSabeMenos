"""Batata quente: um jogador por vez responde, os outros assistem.

A batata começa com alguém da roda. Quem está com ela responde perguntas fáceis e médias:
acertou, a batata passa para o próximo; errou, perde 10 segundos de pavio e vem outra pergunta.
O pavio (40 a 60 segundos, escondido) só queima enquanto alguém está respondendo. Quando acaba,
ou quando alguém erra 3 seguidas, a batata explode e quem está com ela sai. A rodada seguinte
começa com o próximo da roda e um pavio novo, até sobrar um.
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app.events import HotPotatoPlayer, HotPotatoTurn, HotPotatoView
from app.game import Question

START_SECONDS = 5.0
FUSE_SECONDS = (40.0, 60.0)
WRONG_PENALTY_SECONDS = 10.0
MAX_WRONG_STREAK = 3  # erros seguidos de quem está com a batata: explode na hora
PASS_SECONDS = 1.0  # a batata voando para o próximo (o pavio para)
WRONG_SECONDS = 1.2  # mostra o erro antes da próxima pergunta (o pavio para)
EXPLODED_SECONDS = 4.0
DIFFICULTIES = ("easy", "medium")

Phase = Literal["starting", "asking", "passing", "wrong", "exploded", "finished"]


class HotPotatoError(Exception):
    pass


@dataclass
class Holder:
    id: str
    out_round: int | None = None
    correct: int = 0
    wrong: int = 0

    @property
    def alive(self) -> bool:
        return self.out_round is None


@dataclass
class HotPotato:
    players: list[Holder]  # a ordem da roda
    pool: list[Question]
    used: set[str]
    rng: random.Random
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = 0
    holder: str | None = None
    fuse_total: float = 0
    fuse_left: float = 0  # segundos de pavio no começo da pergunta atual
    wrong_streak: int = 0
    question: Question | None = None
    turn: HotPotatoTurn | None = None  # a última resposta, para a tela de passe ou erro
    exploded: str | None = None
    winner: str | None = None

    @classmethod
    def create(cls, player_ids: list[str], pool: list[Question], used: set[str], rng: random.Random, now: float) -> "HotPotato":
        game = cls(players=[Holder(pid) for pid in player_ids], pool=[q for q in pool if q.difficulty in DIFFICULTIES], used=used, rng=rng)
        game._enter("starting", now, START_SECONDS)
        return game

    def player(self, player_id: str) -> Holder | None:
        return next((p for p in self.players if p.id == player_id), None)

    def alive_ids(self) -> list[str]:
        return [p.id for p in self.players if p.alive]

    def fuse_at(self, now: float) -> float:
        """Segundos de pavio que faltam agora."""
        if self.phase == "asking":
            return max(0.0, self.fuse_left - (now - self.phase_started_at))
        return self.fuse_left

    def deadline(self) -> float:
        if self.phase == "asking":
            return self.phase_started_at + self.fuse_left
        return self.phase_ends_at

    # --- ações ------------------------------------------------------------

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase != "asking":
            raise HotPotatoError("Agora não dá para responder.")
        if player_id != self.holder:
            raise HotPotatoError("A batata não está com você.")
        if option not in range(len(self.question.options)):
            raise HotPotatoError("Alternativa inválida.")
        if now >= self.deadline():
            return self._explode(now)
        holder = self.player(player_id)
        self.fuse_left = self.fuse_at(now)
        correct = option == self.question.answer
        self.turn = HotPotatoTurn(
            player_id=player_id, option=option, correct=correct, correct_option=self.question.answer,
            elapsed_ms=round((now - self.phase_started_at) * 1000),
        )
        if correct:
            holder.correct += 1
            self.wrong_streak = 0
            self._enter("passing", now, PASS_SECONDS)
            return
        holder.wrong += 1
        self.wrong_streak += 1
        self.fuse_left -= WRONG_PENALTY_SECONDS
        if self.wrong_streak >= MAX_WRONG_STREAK or self.fuse_left <= 0:
            return self._explode(now)
        self._enter("wrong", now, WRONG_SECONDS)

    def drop(self, player_id: str, now: float) -> None:
        """Quem sai da sala está fora; se estava com a batata, ela vai para o próximo."""
        p = self.player(player_id)
        if not p or not p.alive or self.phase == "finished":
            return
        p.out_round = self.round
        if len(self.alive_ids()) <= 1:
            return self._finish(now)
        if self.holder == player_id and self.phase in ("asking", "passing", "wrong"):
            self.holder = self._next_after(player_id)
            self.wrong_streak = 0
            self._ask(now)

    def advance(self, now: float) -> None:
        """O tempo da fase acabou (no asking, é o pavio)."""
        if self.phase == "starting":
            self._start_round(now, self.rng.choice(self.alive_ids()))
        elif self.phase == "asking":
            self._explode(now)
        elif self.phase == "passing":
            self.holder = self._next_after(self.holder)
            self.wrong_streak = 0
            self._ask(now)
        elif self.phase == "wrong":
            self._ask(now)
        elif self.phase == "exploded":
            alive = self.alive_ids()
            if len(alive) <= 1:
                return self._finish(now)
            self._start_round(now, self._next_after(self.exploded))

    # --- transições -------------------------------------------------------

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds

    def _start_round(self, now: float, first: str) -> None:
        self.round += 1
        self.fuse_total = self.fuse_left = self.rng.uniform(*FUSE_SECONDS)
        self.holder = first
        self.wrong_streak = 0
        self.exploded = None
        self._ask(now)

    def _ask(self, now: float) -> None:
        self.question = self._draw()
        self.turn = None
        self._enter("asking", now, self.fuse_left)

    def _explode(self, now: float) -> None:
        self.fuse_left = 0
        self.exploded = self.holder
        self.player(self.holder).out_round = self.round
        self._enter("exploded", now, EXPLODED_SECONDS)

    def _finish(self, now: float) -> None:
        alive = self.alive_ids()
        self.winner = alive[0] if alive else None
        self.holder = None
        self._enter("finished", now, 0)

    def _next_after(self, player_id: str) -> str:
        """O próximo vivo da roda depois de `player_id` (que pode já estar fora)."""
        ids = [p.id for p in self.players]
        start = ids.index(player_id)
        for step in range(1, len(ids) + 1):
            candidate = self.players[(start + step) % len(ids)]
            if candidate.alive:
                return candidate.id
        return player_id

    def _draw(self) -> Question:
        fresh = [q for q in self.pool if q.id not in self.used]
        if not fresh:
            self.used -= {q.id for q in self.pool}
            fresh = self.pool
        question = self.rng.choice(fresh)
        self.used.add(question.id)
        order = list(range(len(question.options)))
        self.rng.shuffle(order)
        return question.model_copy(update={"options": [question.options[i] for i in order], "answer": order.index(question.answer)})

    # --- ranking e visão --------------------------------------------------

    def places(self) -> dict[str, int]:
        """O vencedor, depois quem saiu mais tarde."""

        def key(p: Holder) -> tuple:
            return (p.id != self.winner, -(p.out_round if p.out_round is not None else 10**6), -p.correct)

        return {p.id: i + 1 for i, p in enumerate(sorted(self.players, key=key))}

    def view(self, now: float, player_ids: list[str]) -> HotPotatoView:
        q = self.question if self.phase in ("asking", "passing", "wrong") else None
        places = self.places() if self.phase == "finished" else {}
        fuse = self.fuse_at(now)
        return HotPotatoView(
            phase=self.phase,
            phase_duration_ms=round((self.deadline() - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.deadline() - now) * 1000)),
            round=self.round,
            holder=self.holder,
            # O pavio é segredo: vai só o quanto já queimou, para a batata chiar e tremer mais.
            heat=0.0 if not self.fuse_total else round(1 - fuse / self.fuse_total, 3),
            burning=self.phase == "asking",
            burn_per_second=round(1 / self.fuse_total, 4) if self.fuse_total else 0.0,
            wrong_streak=self.wrong_streak,
            max_wrong_streak=MAX_WRONG_STREAK,
            penalty_seconds=WRONG_PENALTY_SECONDS,
            fuse_range=list(FUSE_SECONDS),
            text=q.text if q else None,
            theme=q.theme if q else None,
            difficulty=q.difficulty if q else None,
            options=q.options if q else [],
            turn=self.turn,
            exploded=self.exploded,
            winner=self.winner,
            players=[
                HotPotatoPlayer(player_id=p.id, out_round=p.out_round, correct=p.correct, wrong=p.wrong, place=places.get(p.id))
                for p in self.players
                if p.id in player_ids
            ],
        )
