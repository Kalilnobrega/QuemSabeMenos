"""Times: cada time responde junto, por votos, e tem um QI só.

Todo mundo do time vota numa alternativa e vê o voto dos colegas na hora (os outros times só veem
quem já votou). O capitão da pergunta, em rodízio, vale 2 votos e desempata. O time responde quando
todos votaram ou quando o tempo acaba; a alternativa mais votada é a resposta, e os pontos são os do
clássico, com a velocidade contada até o time responder. Capitão na certa: +3 para o time; errado
ou sem votar: −3. Todo mundo votando na certa 3 perguntas seguidas: +10 de Sintonia.

Na aposta e na final, cada time escolhe um representante, que aposta (na aposta) e responde sozinho.
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app.events import Difficulty, QuestionView, TeamMatchView, TeamPlayerStat, TeamSide, TeamVote
from app.game import (
    BET_MAX_PERCENT,
    BET_ODDS,
    BET_PERCENTS,
    FINAL_DIFFICULTY,
    INTRO_SECONDS,
    LATE_SECONDS,
    LEVEL_SECONDS,
    SPEED_GRACE_SECONDS,
    START_SECONDS,
    STARTING_IQ,
    Question,
    bet_round,
    bet_win,
    max_bet,
    points,
    reading_seconds,
    results_seconds,
)

CHOOSING_SECONDS = 10.0
BET_SECONDS = 12.0
CAPTAIN_VOTES = 2
CAPTAIN_BONUS = 3  # capitão na certa; o mesmo tanto sai se ele errar ou não votar
HARMONY_STREAK = 3  # perguntas seguidas com todo mundo na certa
HARMONY_BONUS = 10

Phase = Literal["starting", "level", "choosing", "betting", "intro", "reading", "answering", "results", "finished"]


class TeamMatchError(Exception):
    pass


@dataclass
class Team:
    id: int
    members: list[str]
    score: int = STARTING_IQ
    turn: int = 0  # rodízio do capitão
    captain: str | None = None
    representative: str | None = None
    votes: dict[str, tuple[int, float]] = field(default_factory=dict)  # quem -> (alternativa, quando)
    locked_at: float | None = None
    option: int | None = None
    choices: dict[str, str] = field(default_factory=dict)
    bet: int | None = None
    harmony: int = 0
    correct: bool | None = None
    delta: int = 0
    captain_delta: int = 0
    harmony_delta: int = 0
    bet_delta: int = 0


@dataclass
class Stat:
    votes: int = 0
    right: int = 0
    captain_right: int = 0
    captain_rounds: int = 0
    represented: int = 0
    represented_right: int = 0


@dataclass
class TeamMatch:
    teams: list[Team]
    questions: list[Question]
    answer_seconds: float
    point_scale: float = 1.0
    speed_grace_seconds: float = SPEED_GRACE_SECONDS
    rng: random.Random = field(default_factory=random.Random)
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = -1  # índice da pergunta atual
    bet_index: int | None = None  # índice da pergunta com aposta
    stats: dict[str, Stat] = field(default_factory=dict)
    ready: set[str] = field(default_factory=set)

    @classmethod
    def create(
        cls,
        assignment: dict[str, int],
        questions: list[Question],
        answer_seconds: float,
        now: float,
        point_scale: float = 1.0,
        speed_grace_seconds: float = SPEED_GRACE_SECONDS,
        rng: random.Random | None = None,
    ) -> "TeamMatch":
        ids = sorted(set(assignment.values()))
        teams = [Team(id=t, members=[pid for pid, team in assignment.items() if team == t]) for t in ids]
        match = cls(
            teams=teams, questions=questions, answer_seconds=answer_seconds, point_scale=point_scale,
            speed_grace_seconds=speed_grace_seconds, rng=rng or random.Random(),
            stats={pid: Stat() for pid in assignment},
        )
        match.bet_index = bet_round(questions)
        match._enter("starting", now, START_SECONDS)
        return match

    # --- consultas --------------------------------------------------------

    @property
    def question(self) -> Question:
        return self.questions[self.round]

    @property
    def solo(self) -> bool:
        """Pergunta de representante: a aposta e a final."""
        return self.round >= 0 and (self.round == self.bet_index or self.question.difficulty == FINAL_DIFFICULTY)

    def team_of(self, player_id: str) -> Team | None:
        return next((t for t in self.teams if player_id in t.members), None)

    def deadline(self) -> float:
        return self.phase_ends_at + (LATE_SECONDS if self.phase in ("answering", "betting") else 0)

    def can_advance(self, connected: list[str]) -> bool:
        """Todo mundo já fez o que tinha de fazer nesta fase: dá para seguir antes do tempo."""
        if self.phase == "answering":
            return all(t.locked_at is not None or not self._present(t, connected) for t in self.teams)
        if self.phase == "choosing":
            return all(pid in t.choices for t in self.teams for pid in self._present(t, connected))
        if self.phase == "betting":
            return all(t.bet is not None or t.representative not in connected for t in self.teams)
        if self.phase == "results":
            return all(pid in self.ready for pid in connected)
        return False

    def _present(self, team: Team, connected: list[str]) -> list[str]:
        return [pid for pid in team.members if pid in connected]

    # --- ações ------------------------------------------------------------

    def vote(self, player_id: str, option: int, now: float, connected: list[str]) -> None:
        if self.phase != "answering" or now > self.deadline():
            raise TeamMatchError("Agora não dá para votar.")
        team = self.team_of(player_id)
        if not team:
            raise TeamMatchError("Você não está em nenhum time.")
        if option not in range(len(self.question.options)):
            raise TeamMatchError("Alternativa inválida.")
        if team.locked_at is not None:
            raise TeamMatchError("Seu time já respondeu.")
        if self.solo and player_id != team.representative:
            raise TeamMatchError("Quem responde esta é o representante do time.")
        at = min(now, self.phase_ends_at)
        team.votes[player_id] = (option, at)
        if self.solo or all(pid in team.votes for pid in self._present(team, connected)):
            self._lock(team, at)

    def choose(self, player_id: str, choice: str) -> None:
        if self.phase != "choosing":
            raise TeamMatchError("Agora não dá para escolher o representante.")
        team = self.team_of(player_id)
        if not team or choice not in team.members:
            raise TeamMatchError("Escolha alguém do seu time.")
        team.choices[player_id] = choice

    def place_bet(self, player_id: str, amount: int, now: float) -> None:
        if self.phase != "betting" or now > self.deadline():
            raise TeamMatchError("Agora não dá para apostar.")
        team = self.team_of(player_id)
        if not team or team.representative != player_id:
            raise TeamMatchError("Quem aposta é o representante do time.")
        if team.bet is not None:
            raise TeamMatchError("Seu time já apostou.")
        if not 0 <= amount <= max_bet(team.score):
            raise TeamMatchError(f"Dá para apostar de 0 a {max_bet(team.score)} de QI.")
        team.bet = amount

    def mark_ready(self, player_id: str) -> None:
        if self.phase != "results":
            raise TeamMatchError("Agora não dá para pular.")
        self.ready.add(player_id)

    def drop(self, player_id: str) -> None:
        """Quem sai da sala deixa o time (o QI do time fica)."""
        team = self.team_of(player_id)
        if team:
            team.members.remove(player_id)
            team.votes.pop(player_id, None)
            team.choices.pop(player_id, None)

    # --- fases ------------------------------------------------------------

    def advance(self, now: float, connected: list[str]) -> None:
        """A fase acabou (pelo tempo ou porque todo mundo já fez a sua parte)."""
        if self.phase in ("starting", "results"):
            self._next_question(now, connected)
        elif self.phase == "level":
            self._prepare(now, connected)
        elif self.phase == "choosing":
            self._pick_representatives(connected)
            if self.round == self.bet_index:
                self._enter("betting", now, BET_SECONDS)
            else:
                self._enter("intro", now, INTRO_SECONDS)
        elif self.phase in ("betting", "intro"):
            self._read(now)
        elif self.phase == "reading":
            self._enter("answering", now, self.answer_seconds)
        elif self.phase == "answering":
            self._close(now, connected)

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds

    def _next_question(self, now: float, connected: list[str]) -> None:
        if self.round + 1 >= len(self.questions):
            return self._enter("finished", now, 0)
        self.round += 1
        self.ready = set()
        for team in self.teams:
            team.votes, team.choices = {}, {}
            team.locked_at = team.option = team.bet = team.correct = None
            team.captain = team.representative = None
            team.delta = team.captain_delta = team.harmony_delta = team.bet_delta = 0
        previous = self.questions[self.round - 1].difficulty if self.round else None
        if previous and self.question.difficulty != previous and self.question.difficulty != FINAL_DIFFICULTY:
            return self._enter("level", now, LEVEL_SECONDS)
        self._prepare(now, connected)

    def _prepare(self, now: float, connected: list[str]) -> None:
        if self.solo:
            return self._enter("choosing", now, CHOOSING_SECONDS)
        for team in self.teams:
            team.captain = self._next_captain(team, connected)
        self._read(now)

    def _read(self, now: float) -> None:
        self._enter("reading", now, reading_seconds(self.question.text))

    def _next_captain(self, team: Team, connected: list[str]) -> str | None:
        """O próximo da vez, pulando quem está desconectado."""
        for _ in range(len(team.members)):
            pid = team.members[team.turn % len(team.members)]
            team.turn += 1
            if pid in connected:
                return pid
        return None

    def _pick_representatives(self, connected: list[str]) -> None:
        """O mais votado de cada time; empate ou ninguém votando: sorteio entre os empatados."""
        for team in self.teams:
            present = self._present(team, connected) or team.members
            tally = {pid: 0 for pid in present}
            for choice in team.choices.values():
                if choice in tally:
                    tally[choice] += 1
            top = max(tally.values(), default=0)
            team.representative = self.rng.choice([pid for pid, n in tally.items() if n == top]) if tally else None
            if team.representative:
                self.stats[team.representative].represented += 1

    def _lock(self, team: Team, at: float) -> None:
        team.locked_at = at
        team.option = self._tally(team)

    def _tally(self, team: Team) -> int | None:
        """Alternativa mais votada (o capitão vale 2); no empate, a do capitão, se estiver entre elas."""
        weights: dict[int, int] = {}
        for pid, (option, _) in team.votes.items():
            weights[option] = weights.get(option, 0) + (CAPTAIN_VOTES if pid == team.captain else 1)
        if not weights:
            return None
        top = max(weights.values())
        tied = sorted(o for o, w in weights.items() if w == top)
        captain = team.votes.get(team.captain) if team.captain else None
        if captain and captain[0] in tied:
            return captain[0]
        return self.rng.choice(tied)

    def _close(self, now: float, connected: list[str]) -> None:
        q = self.question
        for team in self.teams:
            if team.locked_at is None:
                # Nem todos votaram: vale o que tem, com a velocidade de quem esperou até o fim.
                self._lock(team, self.phase_ends_at)
            answered = team.option is not None
            team.correct = answered and team.option == q.answer
            elapsed = team.locked_at - self.phase_started_at
            team.delta = points(q.difficulty, team.correct if answered else None, self._speed(elapsed), self.point_scale)
            for pid, (option, _) in team.votes.items():
                if pid in self.stats:
                    self.stats[pid].votes += 1
                    self.stats[pid].right += option == q.answer
            if self.solo:
                if team.representative and team.representative in self.stats:
                    self.stats[team.representative].represented_right += bool(team.correct)
                if team.bet:
                    team.bet_delta = bet_win(team.bet) if team.correct else -team.bet
            else:
                self._captain_and_harmony(team, connected)
            team.score += team.delta + team.captain_delta + team.harmony_delta + team.bet_delta
        self._enter("results", now, results_seconds(q.fact))

    def _captain_and_harmony(self, team: Team, connected: list[str]) -> None:
        answer = self.question.answer
        if team.captain:
            vote = team.votes.get(team.captain)
            right = vote is not None and vote[0] == answer
            team.captain_delta = CAPTAIN_BONUS if right else -CAPTAIN_BONUS
            stat = self.stats.get(team.captain)
            if stat:
                stat.captain_rounds += 1
                stat.captain_right += right
        present = self._present(team, connected)
        if present and all(pid in team.votes and team.votes[pid][0] == answer for pid in present):
            team.harmony += 1
            if team.harmony >= HARMONY_STREAK:
                team.harmony = 0
                team.harmony_delta = HARMONY_BONUS
        else:
            team.harmony = 0

    def _speed(self, elapsed: float) -> float:
        decay = self.answer_seconds - self.speed_grace_seconds
        if elapsed <= self.speed_grace_seconds or decay <= 0:
            return 1.0
        return max(0.0, 1 - (elapsed - self.speed_grace_seconds) / decay)

    # --- visão ------------------------------------------------------------

    def view(self, now: float, viewer: str | None) -> TeamMatchView:
        asked = self.round >= 0
        showing = self.phase in ("reading", "answering", "results")
        revealed = self.phase == "results"
        q = self.question if asked else None
        mine = self.team_of(viewer) if viewer else None
        return TeamMatchView(
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)),
            round=self.round + 1,
            total_rounds=len(self.questions),
            solo=asked and self.solo,
            bet_round=asked and self.round == self.bet_index,
            difficulty=q.difficulty if q else self.questions[0].difficulty,
            theme=q.theme if q else "",
            question=QuestionView(text=q.text, options=q.options, theme=q.theme, difficulty=q.difficulty) if q and showing else None,
            correct_option=q.answer if q and revealed else None,
            fact=q.fact if q and revealed else None,
            bet_percents=list(BET_PERCENTS),
            bet_max_percent=BET_MAX_PERCENT,
            bet_odds=BET_ODDS,
            captain_bonus=CAPTAIN_BONUS,
            harmony_streak=HARMONY_STREAK,
            harmony_bonus=HARMONY_BONUS,
            teams=[self._side(t, t is mine, revealed) for t in self.teams],
            my_team=mine.id if mine else None,
            stats=[
                TeamPlayerStat(player_id=pid, team=team.id, **vars(self.stats[pid]))
                for team in self.teams
                for pid in team.members
                if pid in self.stats
            ],
            ready=sorted(self.ready),
        )

    def _side(self, team: Team, own: bool, revealed: bool) -> TeamSide:
        open_ = own or revealed
        return TeamSide(
            id=team.id,
            members=list(team.members),
            score=team.score,
            captain=team.captain,
            representative=team.representative,
            votes=[TeamVote(player_id=pid, option=o) for pid, (o, _) in team.votes.items()] if open_ else [],
            voted=list(team.votes),
            locked=team.locked_at is not None,
            option=team.option if open_ else None,
            choices=dict(team.choices) if own else {},
            bet=team.bet if open_ else None,
            harmony=team.harmony,
            correct=team.correct if revealed else None,
            delta=team.delta if revealed else 0,
            captain_delta=team.captain_delta if revealed else 0,
            harmony_delta=team.harmony_delta if revealed else 0,
            bet_delta=team.bet_delta if revealed else 0,
        )
