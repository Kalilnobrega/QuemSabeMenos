"""Times: cada time responde junto, por votos, e tem um QI só.

Todo mundo do time vota numa alternativa e vê o voto dos colegas na hora (os outros times só veem
quem já votou). O capitão da pergunta, em rodízio, vale 2 votos e desempata. O time responde quando
todos votaram ou quando o tempo acaba; a alternativa mais votada é a resposta, e os pontos são os do
clássico, com a velocidade contada até o time responder. Capitão na certa: +3 para o time; errado
ou sem votar: −3. Todo mundo votando na certa 3 perguntas seguidas: +10 de Sintonia.

Na aposta e na final, cada time escolhe um representante, que aposta (na aposta) e responde sozinho.

Com poderes, a mão é do time e quem usa é o capitão: na revelação, o capitão da próxima pergunta
escolhe um poder para ela (50/50 e Espiar se usam durante a pergunta). Os ataques miram um time
adversário. Sem capitão (Motim), qualquer um do time escolhe. Míticos: X1 entre times (cada time
manda um representante e os outros times apostam) e Imposto (o 1º paga 15% ao último).
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app import duel as x1
from app import powerups as pw
from app.events import (
    Difficulty,
    DuelPick,
    DuelView,
    LastingPowerUp,
    PowerUp,
    PowerUpGain,
    QuestionView,
    TeamMatchView,
    TeamPlayerStat,
    TeamPowerUse,
    TeamSide,
    TeamVote,
)
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
    _duel_question,
    _shuffle_options,
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

# Poderes dos Times.
POWERS: tuple[PowerUp, ...] = (
    "fifty_fifty", "shield", "double", "peek", "extra_time", "second_chance", "theme", "backpack",
    "scratch", "steal", "scramble", "accelerator", "mirror", "magnifier", "toll", "decoy", "flashbang", "silence",
    "mutiny", "infiltrator", "gag", "iron_captain",
)
ATTACKS: frozenset[PowerUp] = frozenset(
    {"scratch", "steal", "scramble", "accelerator", "mirror", "magnifier", "toll", "decoy", "flashbang", "silence",
     "mutiny", "infiltrator", "gag"}
)
NEEDS_TEAM: frozenset[PowerUp] = ATTACKS | {"peek", "duel"}
VISUAL: frozenset[PowerUp] = frozenset({"scratch", "scramble", "mirror", "magnifier", "flashbang"})
INSTANT: frozenset[PowerUp] = frozenset({"fifty_fifty", "peek"})
LASTING: dict[PowerUp, int] = {"extra_time": 3, "shield": 2, "second_chance": 2}
MUTINY_ROUNDS = 3
POWERUP_MAX = 3  # a mão do time é maior que a de um jogador, e não muda no lobby
INFILTRATOR_VOTES = 2
IRON_RIGHT = 8
IRON_WRONG = -10
DECOY_PER_PLAYER = 5  # por jogador do time alvo que votar numa alternativa falsa
TAX_SHARE = 0.15
# Míticos: (chance normal, chance do time lanterna), sorteados em cada poder ganho.
MYTHIC_CHANCES: dict[PowerUp, tuple[float, float]] = {"duel": (0.02, 0.08), "tax": (0.0, 0.06)}

Phase = Literal[
    "starting", "level", "choosing", "betting", "intro", "reading", "answering", "results", "finished",
    "duel_choosing", "duel_betting", "duel_answering", "duel_results", "duel_end",
]


class TeamMatchError(Exception):
    pass


@dataclass
class Decoy:
    texts: list[str]
    order: list[int]  # posição na tela → índice em opções reais + falsas
    payees: list[int]  # times que jogaram


@dataclass
class Team:
    id: int
    members: list[str]
    score: int = STARTING_IQ
    turn: int = 0  # rodízio do capitão
    captain: str | None = None
    next_captain: str | None = None
    representative: str | None = None
    votes: dict[str, tuple[int, float]] = field(default_factory=dict)  # quem -> (alternativa real ou falsa, quando)
    infiltrators: dict[str, tuple[int, float]] = field(default_factory=dict)
    locked_at: float | None = None
    option: int | None = None
    choices: dict[str, str] = field(default_factory=dict)
    bet: int | None = None
    harmony: int = 0
    # Poderes.
    held: list[PowerUp] = field(default_factory=list)
    mythics: list[PowerUp] = field(default_factory=list)
    extra_slots: int = 0
    armed: TeamPowerUse | None = None
    lasting: dict[PowerUp, int] = field(default_factory=dict)
    lasting_total: dict[PowerUp, int] = field(default_factory=dict)
    mutiny_left: int = 0
    runs: int = 0  # acertos seguidos rumo ao próximo poder
    last_runs: int = 0  # rodadas seguidas em último, longe
    hidden: list[int] = field(default_factory=list)
    first_option: int | None = None
    retried: bool = False
    decoy: Decoy | None = None
    tolls: list[tuple[int, list[int]]] = field(default_factory=list)  # (quem recebe, preço por alternativa real)
    iron: bool = False
    gagged: set[str] = field(default_factory=set)
    silenced: bool = False
    effects: list[PowerUp] = field(default_factory=list)
    peeking: int | None = None
    # Revelação.
    correct: bool | None = None
    delta: int = 0
    captain_delta: int = 0
    harmony_delta: int = 0
    bet_delta: int = 0
    shielded: int = 0
    doubled: bool = False
    stolen: int = 0
    robbed: int = 0
    tolled: int = 0
    toll_received: int = 0
    tricked: int = 0
    tax: int = 0
    duel_delta: int = 0
    gained: PowerUpGain | None = None

    def capacity(self, powerup_max: int) -> int:
        return powerup_max + self.extra_slots


@dataclass
class Stat:
    votes: int = 0
    right: int = 0
    captain_right: int = 0
    captain_rounds: int = 0
    represented: int = 0
    represented_right: int = 0


class _Side:
    """O time visto como um jogador, para o X1 do clássico mexer no QI dele."""

    def __init__(self, player_id: str, team: Team) -> None:
        self.id = player_id
        self.team = team

    @property
    def score(self) -> int:
        return self.team.score

    @score.setter
    def score(self, value: int) -> None:
        self.team.duel_delta += value - self.team.score
        self.team.score = value


@dataclass
class TeamMatch:
    teams: list[Team]
    questions: list[Question]
    answer_seconds: float
    point_scale: float = 1.0
    speed_grace_seconds: float = SPEED_GRACE_SECONDS
    rng: random.Random = field(default_factory=random.Random)
    powers: bool = False
    powerup_max: int = POWERUP_MAX
    bank: list[Question] = field(default_factory=list)  # para o Tema e o X1
    statements: list[x1.DuelQuestion] = field(default_factory=list)
    used: set[str] = field(default_factory=set)
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = -1  # índice da pergunta atual
    bet_index: int | None = None  # índice da pergunta com aposta
    stats: dict[str, Stat] = field(default_factory=dict)
    ready: set[str] = field(default_factory=set)
    active: list[TeamPowerUse] = field(default_factory=list)  # poderes valendo nesta pergunta
    theme_choices: list[str] = field(default_factory=list)
    duel_queue: list[tuple[int, int]] = field(default_factory=list)
    duel: x1.Duel | None = None
    duel_teams: tuple[int, int] | None = None

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
        powers: bool = False,
        powerup_max: int = POWERUP_MAX,
        bank: list[Question] | None = None,
        statements: list[x1.DuelQuestion] | None = None,
        used: set[str] | None = None,
    ) -> "TeamMatch":
        ids = sorted(set(assignment.values()))
        teams = [Team(id=t, members=[pid for pid, team in assignment.items() if team == t]) for t in ids]
        match = cls(
            teams=teams, questions=questions, answer_seconds=answer_seconds, point_scale=point_scale,
            speed_grace_seconds=speed_grace_seconds, rng=rng or random.Random(), powers=powers,
            powerup_max=powerup_max, bank=bank or [], statements=statements or [],
            used=used if used is not None else set(), stats={pid: Stat() for pid in assignment},
        )
        match.bet_index = bet_round(questions)
        if powers:
            for team in teams:
                team.held = [match.rng.choice(POWERS)]
        match._enter("starting", now, START_SECONDS)
        return match

    # --- consultas --------------------------------------------------------

    @property
    def question(self) -> Question:
        return self.questions[self.round]

    def is_solo(self, index: int) -> bool:
        return index == self.bet_index or self.questions[index].difficulty == FINAL_DIFFICULTY

    @property
    def solo(self) -> bool:
        """Pergunta de representante: a aposta e a final."""
        return self.round >= 0 and self.is_solo(self.round)

    def team(self, team_id: int | None) -> Team | None:
        return next((t for t in self.teams if t.id == team_id), None)

    def team_of(self, player_id: str) -> Team | None:
        return next((t for t in self.teams if player_id in t.members), None)

    def window(self, team: Team) -> float:
        seconds = self.answer_seconds
        if self._lasts(team, "extra_time"):
            seconds += pw.EXTRA_SECONDS
        if self._hit(team, "accelerator"):
            seconds *= pw.ACCELERATOR_FACTOR
        return seconds

    def grace(self, team: Team) -> float:
        if self._hit(team, "accelerator"):
            return 0.0
        return self.window(team) if self._lasts(team, "extra_time") else self.speed_grace_seconds

    def team_deadline(self, team: Team) -> float:
        return self.phase_started_at + self.window(team)

    def deadline(self) -> float:
        if self.phase == "answering":
            pending = [self.team_deadline(t) for t in self.teams if t.locked_at is None]
            return (min(pending) if pending else self.phase_started_at) + LATE_SECONDS
        if self.phase == "duel_answering" and self.duel:
            return self.duel.deadline() + LATE_SECONDS
        return self.phase_ends_at + (LATE_SECONDS if self.phase == "betting" else 0)

    def can_advance(self, connected: list[str]) -> bool:
        """Todo mundo já fez o que tinha de fazer nesta fase: dá para seguir antes do tempo."""
        if self.phase == "answering":
            return all(self._done(t, connected) for t in self.teams)
        if self.phase in ("choosing", "duel_choosing"):
            return all(pid in t.choices for t in self._choosing_teams() for pid in self._present(t, connected))
        if self.phase == "betting":
            return all(t.bet is not None or t.representative not in connected for t in self.teams)
        if self.phase == "duel_betting":
            duel = self.duel
            return bool(duel) and all(pid in duel.bets for pid in duel.bettors if pid in connected)
        if self.phase == "duel_answering":
            return bool(self.duel) and self.duel.everyone_answered()
        if self.phase == "results":
            return all(pid in self.ready for pid in connected)
        return False

    def _done(self, team: Team, connected: list[str]) -> bool:
        return team.locked_at is not None or not self._present(team, connected)

    def _present(self, team: Team, connected: list[str]) -> list[str]:
        return [pid for pid in team.members if pid in connected]

    def _choosing_teams(self) -> list[Team]:
        if self.phase == "duel_choosing" and self.duel_teams:
            return [t for t in self.teams if t.id in self.duel_teams]
        return self.teams

    def _hit(self, team: Team, kind: PowerUp) -> bool:
        return any(u.kind == kind and u.target_team == team.id for u in self.active)

    def _lasts(self, team: Team, kind: PowerUp) -> bool:
        return self.powers and not self.solo and team.lasting.get(kind, 0) > 0

    def _options(self, team: Team) -> int:
        return len(self.question.options) + (len(team.decoy.texts) if team.decoy else 0)

    def _to_real(self, team: Team, screen: int) -> int:
        """Posição na tela do time → índice real (as falsas vêm depois das reais)."""
        return team.decoy.order[screen] if team.decoy else screen

    def _to_screen(self, team: Team, real: int | None) -> int | None:
        if real is None:
            return None
        return team.decoy.order.index(real) if team.decoy else real

    # --- ações ------------------------------------------------------------

    def vote(self, player_id: str, option: int, now: float, connected: list[str], team_id: int | None = None) -> None:
        if self.phase == "duel_answering":
            return self._duel_answer(player_id, option, now)
        if self.phase != "answering":
            raise TeamMatchError("Agora não dá para votar.")
        own = self.team_of(player_id)
        if not own:
            raise TeamMatchError("Você não está em nenhum time.")
        team, infiltrating = own, False
        if team_id is not None and team_id != own.id:
            team = self.team(team_id)
            if not team or not self._infiltrates(player_id, team):
                raise TeamMatchError("Você não está infiltrado nesse time.")
            infiltrating = True
        if now > self.team_deadline(team) + LATE_SECONDS:
            raise TeamMatchError("O tempo acabou.")
        if team.locked_at is not None:
            raise TeamMatchError("Esse time já respondeu." if infiltrating else "Seu time já respondeu.")
        if not infiltrating:
            if player_id in team.gagged:
                raise TeamMatchError("Mordaça: você não vota nesta.")
            if self.solo and player_id != team.representative:
                raise TeamMatchError("Quem responde esta é o representante do time.")
            if team.iron and player_id != team.captain:
                raise TeamMatchError("Capitão de ferro: só o capitão vota.")
        if option not in range(self._options(team)):
            raise TeamMatchError("Alternativa inválida.")
        real = self._to_real(team, option)
        if real in team.hidden or real == team.first_option:
            raise TeamMatchError("Alternativa inválida.")
        at = min(now, self.team_deadline(team))
        (team.infiltrators if infiltrating else team.votes)[player_id] = (real, at)
        if infiltrating:
            return
        voters = [pid for pid in self._present(team, connected) if pid not in team.gagged]
        if self.solo or (team.iron and player_id == team.captain) or all(pid in team.votes for pid in voters):
            self._lock(team, at)

    def _infiltrates(self, player_id: str, team: Team) -> bool:
        return any(u.kind == "infiltrator" and u.target_team == team.id and u.target_player == player_id for u in self.active)

    def choose(self, player_id: str, choice: str) -> None:
        if self.phase not in ("choosing", "duel_choosing"):
            raise TeamMatchError("Agora não dá para escolher o representante.")
        team = self.team_of(player_id)
        if not team or team not in self._choosing_teams() or choice not in team.members:
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

    def duel_bet(self, player_id: str, choice: str, now: float) -> None:
        duel = self.duel
        if not duel or self.phase != "duel_betting" or now > self.phase_ends_at + LATE_SECONDS:
            raise TeamMatchError("Agora não dá para apostar.")
        if player_id not in duel.bettors:
            raise TeamMatchError("Você não pode apostar neste X1.")
        if player_id in duel.bets:
            raise TeamMatchError("Você já apostou.")
        if choice not in duel.fighters:
            raise TeamMatchError("Aposte em um dos dois.")
        duel.bets[player_id] = choice

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
        for t in self.teams:
            t.infiltrators.pop(player_id, None)

    # --- poderes ----------------------------------------------------------

    def can_arm(self, player_id: str) -> bool:
        team = self.team_of(player_id)
        upcoming = self.round + 1
        if not self.powers or not team or self.phase != "results" or upcoming >= len(self.questions):
            return False
        if self.is_solo(upcoming):
            return False
        return team.next_captain in (None, player_id)

    def can_use(self, player_id: str) -> bool:
        team = self.team_of(player_id)
        if not self.powers or not team or self.solo or self.phase not in ("reading", "answering"):
            return False
        return team.locked_at is None and team.captain in (None, player_id)

    def arm(
        self,
        player_id: str,
        kind: PowerUp,
        target_team: int | None = None,
        target_player: str | None = None,
        theme: str | None = None,
    ) -> None:
        """Na revelação: o capitão da próxima escolhe o poder do time (míticos e Mochila valem na hora)."""
        team = self.team_of(player_id)
        if not self.powers or not team or self.phase != "results":
            raise TeamMatchError("Agora não dá para usar habilidade.")
        if kind in ("duel", "tax"):
            return self._use_mythic(team, player_id, kind, target_team)
        if kind not in team.held:
            raise TeamMatchError("Seu time não tem essa habilidade.")
        if not self.can_arm(player_id):
            raise TeamMatchError("Quem escolhe o poder é o capitão da próxima pergunta.")
        if kind == "backpack":
            return self._open_backpack(team)
        if team.armed:
            raise TeamMatchError("Seu time já escolheu o poder da próxima.")
        if kind in INSTANT:
            raise TeamMatchError("Essa se usa na hora da pergunta.")
        target = self.team(target_team)
        if kind in NEEDS_TEAM:
            if not target or target is team:
                raise TeamMatchError("Escolha um time adversário.")
        else:
            target_team = None
        if kind == "gag":
            if target_player not in target.members:
                raise TeamMatchError("Escolha quem do outro time fica sem votar.")
        elif kind == "infiltrator":
            if target_player not in team.members:
                raise TeamMatchError("Escolha quem do seu time se infiltra.")
        else:
            target_player = None
        if kind == "iron_captain" and not team.next_captain:
            raise TeamMatchError("Seu time está sem capitão.")
        if kind == "theme":
            if theme not in self.theme_choices:
                raise TeamMatchError("Escolha um dos temas.")
            if any(t.armed and t.armed.kind == "theme" for t in self.teams):
                raise TeamMatchError("Outro time já escolheu o tema da próxima.")
            self._swap_next_question(theme)
        else:
            theme = None
        team.held.remove(kind)
        team.armed = TeamPowerUse(
            kind=kind, by=player_id, by_team=team.id, target_team=target_team, target_player=target_player, theme=theme,
        )

    def use_now(self, player_id: str, kind: PowerUp, target_team: int | None = None) -> None:
        """50/50 e Espiar: o capitão usa durante a pergunta."""
        team = self.team_of(player_id)
        if not team or not self.can_use(player_id):
            raise TeamMatchError("Agora não dá para usar habilidade.")
        if kind not in INSTANT:
            raise TeamMatchError("Essa se escolhe na revelação.")
        if kind not in team.held:
            raise TeamMatchError("Seu time não tem essa habilidade.")
        if any(u.kind == kind and u.by_team == team.id for u in self.active):
            raise TeamMatchError("Já está valendo.")
        if kind == "peek":
            target = self.team(target_team)
            if not target or target is team:
                raise TeamMatchError("Escolha um time adversário.")
            team.peeking = target.id
        else:
            target_team = None
            q = self.question
            wrong = [i for i in range(len(q.options)) if i != q.answer and i != team.first_option]
            team.hidden = sorted(self.rng.sample(wrong, min(pw.FIFTY_FIFTY_REMOVES, len(wrong))))
            for pid, (option, _) in list(team.votes.items()):
                if option in team.hidden:
                    del team.votes[pid]
        team.held.remove(kind)
        self.active.append(TeamPowerUse(kind=kind, by=player_id, by_team=team.id, target_team=target_team))

    def _use_mythic(self, team: Team, player_id: str, kind: PowerUp, target_team: int | None) -> None:
        if kind not in team.mythics:
            raise TeamMatchError("Seu time não tem essa habilidade.")
        if self.round + 1 >= len(self.questions):
            raise TeamMatchError("A partida está acabando.")
        if team.next_captain not in (None, player_id):
            raise TeamMatchError("Quem escolhe o poder é o capitão da próxima pergunta.")
        if kind == "duel":
            target = self.team(target_team)
            if not target or target is team or not target.members:
                raise TeamMatchError("Escolha um time adversário.")
            team.mythics.remove(kind)
            self.duel_queue.append((team.id, target.id))
            return
        others = [t for t in self.teams if t is not team]
        if not others or any(t.score < team.score for t in others):
            raise TeamMatchError("O Imposto é para o time em último.")
        top = max(others, key=lambda t: t.score)
        amount = max(0, top.score) * round(TAX_SHARE * 100) // 100
        team.mythics.remove(kind)
        top.score -= amount
        top.tax -= amount
        team.score += amount
        team.tax += amount

    def _open_backpack(self, team: Team) -> None:
        if team.extra_slots >= pw.BACKPACK_MAX_EXTRA:
            raise TeamMatchError("A Mochila do time já está no tamanho máximo.")
        team.held.remove("backpack")
        team.extra_slots += 1
        team.held.append(self.rng.choice([k for k in POWERS if k != "backpack"]))

    def _swap_next_question(self, theme: str) -> None:
        upcoming = self.round + 1
        current = self.questions[upcoming]
        if current.theme == theme:
            return
        pool = [q for q in self.bank if q.theme == theme and q.difficulty == current.difficulty and q.id not in self.used]
        if not pool:
            raise TeamMatchError("Acabaram as perguntas desse tema.")
        question = self.rng.choice(pool)
        self.used.add(question.id)
        self.questions[upcoming] = _shuffle_options(question, self.rng)

    def _draw_theme_choices(self) -> list[str]:
        upcoming = self.round + 1
        if not self.powers or upcoming >= len(self.questions) or self.is_solo(upcoming):
            return []
        level = self.questions[upcoming].difficulty
        themes = sorted({q.theme for q in self.bank if q.difficulty == level and q.id not in self.used} | {self.questions[upcoming].theme})
        return sorted(self.rng.sample(themes, min(pw.THEME_CHOICES, len(themes))))

    def _activate(self) -> None:
        """Começo de uma pergunta comum: o que os times escolheram passa a valer."""
        uses = [t.armed for t in self.teams if t.armed]
        for team in self.teams:
            team.armed = None
        self.active = uses
        for use in uses:
            mine, target = self.team(use.by_team), self.team(use.target_team)
            if use.kind in LASTING:
                mine.lasting[use.kind] = mine.lasting_total[use.kind] = LASTING[use.kind]
            elif use.kind == "mutiny" and target:
                target.mutiny_left = MUTINY_ROUNDS
            elif use.kind == "silence" and target:
                target.silenced = True
            elif use.kind == "gag" and target:
                target.gagged.add(use.target_player)
            elif use.kind == "iron_captain":
                mine.iron = True
            elif use.kind == "double":
                mine.doubled = True
            elif use.kind == "decoy" and target:
                if target.decoy:
                    target.decoy.payees.append(mine.id)
                else:
                    target.decoy = self._make_decoy([mine.id])
            elif use.kind == "toll" and target:
                prices = [self.rng.randint(*pw.TOLL_PRICES) for _ in self.question.options]
                target.tolls.append((mine.id, prices))
            elif use.kind in VISUAL and target:
                target.effects.append(use.kind)

    def _make_decoy(self, payees: list[int]) -> Decoy | None:
        q = self.question
        similar = [o for other in self.bank if other.theme == q.theme and other.text != q.text for o in other.options]
        self.rng.shuffle(similar)
        texts = pw.decoys(q.options[q.answer], q.options, similar[:48], self.rng)
        if not texts:
            return None
        order = list(range(len(q.options) + len(texts)))
        self.rng.shuffle(order)
        return Decoy(texts=texts, order=order, payees=payees)

    def _gains(self) -> None:
        """Um poder a cada 3 acertos seguidos do time; o lanterna muito atrás por 3 rodadas também ganha."""
        behind = pw.trailing(self.teams)  # type: ignore[arg-type]
        for team in self.teams:
            team.runs = team.runs + 1 if team.correct else 0
            team.last_runs = team.last_runs + 1 if team.id in behind else 0
            if team.runs >= pw.STREAK_FOR_POWERUP:
                reason = "streak"
            elif team.last_runs >= pw.COMEBACK_ROUNDS:
                reason = "comeback"
            else:
                continue
            if len(team.held) + len(team.mythics) >= team.capacity(self.powerup_max):
                continue
            roll, edge, kind = self.rng.random(), 0.0, None
            for mythic, (normal, trailing) in MYTHIC_CHANCES.items():
                edge += trailing if team.id in behind else normal
                if roll < edge:
                    kind = mythic
                    break
            if kind:
                team.mythics.append(kind)
            else:
                kind = self.rng.choice(POWERS)
                team.held.append(kind)
            team.gained = PowerUpGain(kind=kind, reason=reason, mythic=kind in MYTHIC_CHANCES)
            if reason == "streak":
                team.runs = 0
            else:
                team.last_runs = 0

    def _wear(self) -> None:
        for team in self.teams:
            if team.shielded:
                team.lasting.pop("shield", None)
            for kind in list(team.lasting):
                team.lasting[kind] -= 1
                if team.lasting[kind] <= 0:
                    del team.lasting[kind]
            team.mutiny_left = max(0, team.mutiny_left - 1)

    # --- fases ------------------------------------------------------------

    def advance(self, now: float, connected: list[str]) -> None:
        """A fase acabou (pelo tempo ou porque todo mundo já fez a sua parte)."""
        if self.phase == "starting":
            self._next_question(now, connected)
        elif self.phase == "results":
            if self.duel_queue and self.round + 1 < len(self.questions):
                return self._start_duel(now, connected)
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
            self._enter("answering", now, max(self.window(t) for t in self.teams))
        elif self.phase == "answering":
            for team in self.teams:
                if team.locked_at is None and now >= self.team_deadline(team):
                    self._lock(team, self.team_deadline(team))
            if all(self._done(t, connected) or now >= self.phase_ends_at for t in self.teams):
                self._close(now, connected)
        elif self.phase == "duel_choosing":
            self._open_duel(now, connected)
        elif self.phase == "duel_betting":
            self.duel.fill_bets(self.rng)
            self._next_duel_question(now, connected)
        elif self.phase == "duel_answering":
            self.duel.close()
            self._enter("duel_results", now, x1.RESULTS_SECONDS)
        elif self.phase == "duel_results":
            self._next_duel_question(now, connected)
        elif self.phase == "duel_end":
            self.duel, self.duel_teams = None, None
            if self.duel_queue:
                return self._start_duel(now, connected)
            self._next_question(now, connected)

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds

    def _next_question(self, now: float, connected: list[str]) -> None:
        if self.round + 1 >= len(self.questions):
            return self._enter("finished", now, 0)
        self.round += 1
        self.ready = set()
        self.theme_choices = []
        for team in self.teams:
            team.votes, team.choices, team.infiltrators = {}, {}, {}
            team.locked_at = team.option = team.bet = team.correct = None
            team.captain = team.representative = None
            team.delta = team.captain_delta = team.harmony_delta = team.bet_delta = 0
            team.shielded = team.stolen = team.robbed = team.tolled = team.toll_received = 0
            team.tricked = team.tax = team.duel_delta = 0
            team.doubled = team.iron = team.silenced = team.retried = False
            team.hidden, team.tolls, team.effects, team.gagged = [], [], [], set()
            team.first_option = team.peeking = team.decoy = team.gained = None
        self.active = []
        previous = self.questions[self.round - 1].difficulty if self.round else None
        if previous and self.question.difficulty != previous and self.question.difficulty != FINAL_DIFFICULTY:
            return self._enter("level", now, LEVEL_SECONDS)
        self._prepare(now, connected)

    def _prepare(self, now: float, connected: list[str]) -> None:
        if self.solo:
            for team in self.teams:
                team.armed = None
            return self._enter("choosing", now, CHOOSING_SECONDS)
        for team in self.teams:
            team.captain = team.next_captain if team.next_captain in connected else self._next_captain(team, connected)
            team.next_captain = None
        if self.powers:
            self._activate()
        for team in self.teams:
            if team.mutiny_left or team.captain in team.gagged:
                team.captain = None
            if team.iron and not team.captain:
                team.iron = False
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
        for team in self._choosing_teams():
            present = self._present(team, connected) or team.members
            tally = {pid: 0 for pid in present}
            for choice in team.choices.values():
                if choice in tally:
                    tally[choice] += 1
            top = max(tally.values(), default=0)
            team.representative = self.rng.choice([pid for pid, n in tally.items() if n == top]) if tally else None
            if team.representative and self.phase == "choosing":
                self.stats[team.representative].represented += 1

    def _lock(self, team: Team, at: float) -> None:
        option = self._tally(team)
        retry = option is not None and option != self.question.answer and self._lasts(team, "second_chance") and not team.retried
        if retry:
            # Segunda chance: o time errou e vota de novo, sem a alternativa que escolheu.
            team.retried = True
            team.first_option = option
            team.lasting.pop("second_chance", None)
            team.votes = {}
            team.infiltrators = {}
            return
        team.locked_at = at
        team.option = option

    def _tally(self, team: Team) -> int | None:
        """Alternativa mais votada (capitão e Infiltrado valem 2); no empate, a do capitão, se estiver entre elas."""
        weights: dict[int, int] = {}
        for pid, (option, _) in team.votes.items():
            weights[option] = weights.get(option, 0) + (CAPTAIN_VOTES if pid == team.captain else 1)
        for option, _ in team.infiltrators.values():
            weights[option] = weights.get(option, 0) + INFILTRATOR_VOTES
        if team.iron:
            vote = team.votes.get(team.captain)
            return vote[0] if vote else None
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
                self._lock(team, self.team_deadline(team))
                if team.locked_at is None:  # a Segunda chance apareceu no fim do tempo
                    team.locked_at, team.option = self.team_deadline(team), None
        for team in self.teams:
            self._score(team, connected)
        if not self.solo and self.powers:
            self._settle_attacks()
        for team in self.teams:
            team.score += (
                team.delta + team.captain_delta + team.harmony_delta + team.bet_delta
                + team.stolen - team.robbed + team.toll_received - team.tolled + team.tricked
            )
        if not self.solo and self.powers:
            self._gains()
            self._wear()
        self._plan_next_captains(connected)
        self.theme_choices = self._draw_theme_choices()
        self._enter("results", now, results_seconds(q.fact) + (4 if self.powers else 0))

    def _score(self, team: Team, connected: list[str]) -> None:
        q = self.question
        answered = team.option is not None
        team.correct = answered and team.option == q.answer
        elapsed = team.locked_at - self.phase_started_at
        delta = points(q.difficulty, team.correct if answered else None, self._speed(elapsed, team), self.point_scale)
        if team.correct and team.first_option is not None:
            delta = int(delta * pw.SECOND_CHANCE_SHARE)
        if team.doubled:
            hard_loss = delta < 0 and q.difficulty == "hard"
            delta *= pw.DOUBLE_HARD_LOSS_FACTOR if hard_loss else pw.DOUBLE_FACTOR
        if delta < 0 and self._lasts(team, "shield"):
            team.shielded = -delta
            delta = 0
        team.delta = delta
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

    def _captain_and_harmony(self, team: Team, connected: list[str]) -> None:
        answer = self.question.answer
        if team.captain:
            vote = team.votes.get(team.captain)
            right = vote is not None and vote[0] == answer
            if team.iron:
                team.captain_delta = IRON_RIGHT if right else IRON_WRONG
            else:
                team.captain_delta = CAPTAIN_BONUS if right else -CAPTAIN_BONUS
            stat = self.stats.get(team.captain)
            if stat:
                stat.captain_rounds += 1
                stat.captain_right += right
        if team.iron:
            return  # só o capitão votou: a Sintonia não anda nem quebra
        voters = [pid for pid in self._present(team, connected) if pid not in team.gagged]
        if voters and all(pid in team.votes and team.votes[pid][0] == answer for pid in voters):
            team.harmony += 1
            if team.harmony >= HARMONY_STREAK:
                team.harmony = 0
                team.harmony_delta = HARMONY_BONUS
        else:
            team.harmony = 0

    def _settle_attacks(self) -> None:
        """Roubo, Pedágio e Alternativa falsa, depois dos pontos de cada time."""
        real = len(self.question.options)
        for team in self.teams:
            if team.decoy:
                fooled = sum(1 for option, _ in team.votes.values() if option >= real)
                for payee in team.decoy.payees:
                    if thief := self.team(payee):
                        thief.tricked += DECOY_PER_PLAYER * fooled
            for payee, prices in team.tolls:
                price = min(prices) if team.option is None or team.option >= real else prices[team.option]
                team.tolled += price
                if receiver := self.team(payee):
                    receiver.toll_received += price
        for use in self.active:
            thief, target = self.team(use.by_team), self.team(use.target_team)
            if use.kind != "steal" or not thief or not target or target.shielded:
                continue
            share = pw.STEAL_FIXED + (round(target.delta * pw.STEAL_GAIN_SHARE) if target.delta > 0 else 0)
            thief.stolen += share
            target.robbed += share

    def _plan_next_captains(self, connected: list[str]) -> None:
        """Já na revelação se sabe quem é o capitão da próxima: é ele quem escolhe o poder."""
        upcoming = self.round + 1
        for team in self.teams:
            team.next_captain = None
            if upcoming < len(self.questions) and not self.is_solo(upcoming) and not team.mutiny_left:
                team.next_captain = self._next_captain(team, connected)

    def _speed(self, elapsed: float, team: Team) -> float:
        grace, window = self.grace(team), self.window(team)
        decay = window - grace
        if elapsed <= grace or decay <= 0:
            return 1.0
        return max(0.0, 1 - (elapsed - grace) / decay)

    # --- X1 entre times ---------------------------------------------------

    def _start_duel(self, now: float, connected: list[str]) -> None:
        while self.duel_queue:
            a, b = self.duel_queue.pop(0)
            ta, tb = self.team(a), self.team(b)
            if ta and tb and self._present(ta, connected) and self._present(tb, connected):
                break
        else:
            return self._next_question(now, connected)
        self.duel_teams = (a, b)
        for team in (ta, tb):
            team.choices = {}
        self._enter("duel_choosing", now, CHOOSING_SECONDS)

    def _open_duel(self, now: float, connected: list[str]) -> None:
        self._pick_representatives(connected)
        a, b = (self.team(t) for t in self.duel_teams)
        questions = []
        for kind, count in x1.LAYOUT:
            if kind == "true_false":
                pool = [s for s in self.statements if s.id not in self.used]
            else:
                taken = {q.id for q in self.questions}
                pool = [_duel_question(q, kind) for q in self.bank if q.difficulty == kind and q.id not in self.used and q.id not in taken]
            picked = self.rng.sample(pool, min(count, len(pool)))
            self.used.update(q.id for q in picked)
            questions += picked
        bettors = [
            pid for t in self.teams if t.id not in self.duel_teams and t.score >= x1.BET
            for pid in self._present(t, connected)
        ]
        self.duel = x1.Duel(challenger=a.representative, rival=b.representative, questions=questions, bettors=bettors)
        self._enter("duel_betting", now, x1.INTRO_SECONDS + (x1.BET_SECONDS if bettors else 0))

    def _next_duel_question(self, now: float, connected: list[str]) -> None:
        duel = self.duel
        if duel.has_next():
            duel.open_next(now)
            return self._enter("duel_answering", now, duel.seconds())
        if duel.winner is None:
            duel.loser, duel.winner = duel.rival, duel.challenger
        sides = [_Side(duel.challenger, self.team(self.duel_teams[0])), _Side(duel.rival, self.team(self.duel_teams[1]))]
        sides += [_Side(pid, self.team_of(pid)) for pid in duel.bets if self.team_of(pid)]
        for team in self.teams:
            team.duel_delta = 0
        duel.settle(sides)
        self._enter("duel_end", now, x1.END_SECONDS)

    def _duel_answer(self, player_id: str, option: int, now: float) -> None:
        duel = self.duel
        if not duel or now > duel.deadline() + LATE_SECONDS:
            raise TeamMatchError("Agora não dá para responder.")
        if player_id not in duel.fighters:
            raise TeamMatchError("Só os dois do X1 respondem.")
        if player_id in duel.answers:
            raise TeamMatchError("Você já respondeu.")
        if not 0 <= option < len(duel.question.options):
            raise TeamMatchError("Alternativa inválida.")
        duel.answers[player_id] = (option, min(now, duel.deadline()))

    def _duel_view(self, viewer: str | None) -> DuelView | None:
        duel = self.duel
        if not duel or not self.phase.startswith("duel_") or self.phase == "duel_choosing":
            return None
        asked = duel.index >= 0
        question = duel.question if asked else None
        closed = self.phase in ("duel_results", "duel_end") and asked
        return DuelView(
            challenger=duel.challenger,
            rival=duel.rival,
            question_number=duel.index + 1,
            total_questions=len(duel.questions),
            kind=question.kind if question else None,
            text=question.text if question else None,
            options=question.options if question else [],
            theme=question.theme if question else None,
            answered=[pid for pid in duel.fighters if pid in duel.answers],
            picks=[DuelPick(**vars(pick)) for pick in duel.picks] if closed else [],
            correct_option=question.answer if closed else None,
            fact=question.fact if closed else None,
            total_ms=dict(duel.total_ms),
            can_bet=self.phase == "duel_betting" and viewer in duel.bettors and viewer not in duel.bets,
            my_bet=duel.bets.get(viewer) if viewer else None,
            bets=dict(duel.bets) if self.phase == "duel_end" else {},
            winner=duel.winner if self.phase == "duel_end" else None,
            loser=duel.loser if self.phase == "duel_end" else None,
            paid=duel.paid,
            from_bets=duel.from_bets,
            favorite_bonus=duel.favorite_bonus,
        )

    # --- visão ------------------------------------------------------------

    def view(self, now: float, viewer: str | None) -> TeamMatchView:
        asked = self.round >= 0
        showing = self.phase in ("reading", "answering", "results")
        revealed = self.phase == "results"
        q = self.question if asked else None
        mine = self.team_of(viewer) if viewer else None
        infiltrated = next(
            (t for t in self.teams if viewer and self._infiltrates(viewer, t)), None
        ) if self.phase in ("reading", "answering") else None
        ends_at = self.phase_ends_at
        if self.phase == "answering" and mine:
            ends_at = self.team_deadline(mine)
        if self.phase == "duel_answering" and self.duel:
            ends_at = self.duel.deadline()
        return TeamMatchView(
            phase=self.phase,
            phase_duration_ms=round((ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((ends_at - now) * 1000)),
            round=self.round + 1,
            total_rounds=len(self.questions),
            solo=asked and self.solo,
            bet_round=asked and self.round == self.bet_index,
            difficulty=q.difficulty if q else self.questions[0].difficulty,
            theme=q.theme if q else "",
            question=self._question_view(mine) if q and showing else None,
            correct_option=self._to_screen(mine, q.answer) if mine and q and revealed else (q.answer if q and revealed else None),
            fact=q.fact if q and revealed else None,
            bet_percents=list(BET_PERCENTS),
            bet_max_percent=BET_MAX_PERCENT,
            bet_odds=BET_ODDS,
            captain_bonus=CAPTAIN_BONUS,
            harmony_streak=HARMONY_STREAK,
            harmony_bonus=HARMONY_BONUS,
            teams=[self._side(t, mine, revealed, viewer) for t in self.teams],
            my_team=mine.id if mine else None,
            stats=[
                TeamPlayerStat(player_id=pid, team=team.id, **vars(self.stats[pid]))
                for team in self.teams
                for pid in team.members
                if pid in self.stats
            ],
            ready=sorted(self.ready),
            powers=self.powers,
            can_arm=bool(viewer) and self.can_arm(viewer),
            can_use=bool(viewer) and self.can_use(viewer) and any(k in INSTANT for k in mine.held),
            uses=self._visible_uses(mine, revealed),
            theme_choices=self.theme_choices,
            hidden_options=[self._to_screen(mine, i) for i in mine.hidden] if mine and showing else [],
            first_wrong=self._to_screen(mine, mine.first_option) if mine and showing else None,
            tolls=self._toll_view(mine) if mine and q and self.phase in ("reading", "answering") else None,
            gagged=bool(mine) and viewer in mine.gagged and showing,
            infiltrating=infiltrated.id if infiltrated else None,
            infiltrate_question=self._question_view(infiltrated) if infiltrated and q else None,
            effects=list(mine.effects) if mine and self.phase in ("reading", "answering") else [],
            silenced=bool(mine) and mine.silenced and self.phase in ("reading", "answering"),
            peeking=mine.peeking if mine and self.phase in ("reading", "answering") else None,
            duel=self._duel_view(viewer),
            duel_teams=list(self.duel_teams or []),
        )

    def _question_view(self, team: Team | None) -> QuestionView:
        q = self.question
        options = q.options
        if team and team.decoy:
            everything = [*q.options, *team.decoy.texts]
            options = [everything[i] for i in team.decoy.order]
        return QuestionView(text=q.text, options=options, theme=q.theme, difficulty=q.difficulty)

    def _toll_view(self, team: Team) -> list[int] | None:
        if not team.tolls:
            return None
        real = len(self.question.options)
        total = [sum(prices[i] for _, prices in team.tolls) for i in range(real)]
        cheapest = min(total)
        return [total[i] if i < real else cheapest for i in (team.decoy.order if team.decoy else range(real))]

    def _visible_uses(self, mine: Team | None, revealed: bool) -> list[TeamPowerUse]:
        if revealed or not mine:
            return list(self.active)
        return [u for u in self.active if mine.id in (u.by_team, u.target_team)]

    def _side(self, team: Team, mine: Team | None, revealed: bool, viewer: str | None) -> TeamSide:
        own = team is mine
        peeked = bool(mine) and mine.peeking == team.id and self.phase in ("reading", "answering")
        silenced = own and team.silenced and self.phase in ("reading", "answering")
        open_ = own or revealed or peeked

        def screen(option: int) -> int | None:
            # Na tela de quem vê: o próprio time com as falsas dele; os outros só as reais.
            if own:
                return self._to_screen(team, option)
            real = len(self.question.options)
            if option >= real:
                return None
            return self._to_screen(mine, option) if mine else option

        votes: list[TeamVote] = []
        if open_:
            for pid, (option, _) in team.votes.items():
                if silenced and pid != viewer:
                    continue  # Silêncio: cada um só vê o próprio voto
                votes.append(TeamVote(player_id=pid, option=screen(option)))
            votes += [TeamVote(player_id=pid, option=screen(option), infiltrator=True) for pid, (option, _) in team.infiltrators.items()]
        lasting = [
            LastingPowerUp(kind=kind, rounds_left=left, total=team.lasting_total.get(kind, left))
            for kind, left in team.lasting.items()
        ]
        real = len(self.question.options) if self.round >= 0 else 0
        return TeamSide(
            id=team.id,
            members=list(team.members),
            score=team.score,
            captain=team.captain,
            representative=team.representative,
            votes=votes,
            voted=list(team.votes),
            locked=team.locked_at is not None,
            option=screen(team.option) if open_ and team.option is not None else None,
            choices=dict(team.choices) if own else {},
            bet=team.bet if open_ else None,
            harmony=team.harmony,
            next_captain=team.next_captain if self.phase == "results" else None,
            mutiny_left=team.mutiny_left,
            iron=team.iron,
            powerups=list(team.held) if own else [],
            mythic_powerups=list(team.mythics) if own else [],
            powerup_max=team.capacity(self.powerup_max),
            armed=team.armed if own else None,
            lasting=lasting if own else [],
            correct=team.correct if revealed else None,
            decoy_pick=revealed and team.option is not None and team.option >= real,
            delta=team.delta if revealed else 0,
            captain_delta=team.captain_delta if revealed else 0,
            harmony_delta=team.harmony_delta if revealed else 0,
            bet_delta=team.bet_delta if revealed else 0,
            shielded=team.shielded if revealed else 0,
            doubled=team.doubled,
            second_chance=revealed and bool(team.correct) and team.first_option is not None,
            stolen=team.stolen if revealed else 0,
            robbed=team.robbed if revealed else 0,
            tolled=team.tolled if revealed else 0,
            toll_received=team.toll_received if revealed else 0,
            tricked=team.tricked if revealed else 0,
            tax=team.tax,
            duel_delta=team.duel_delta if self.phase == "duel_end" else 0,
            gained=team.gained if revealed else None,
        )
