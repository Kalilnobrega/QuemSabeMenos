"""Último de pé: battle royale com vidas. Errar ou não responder tira uma vida; sem vidas, está fora.

Duas versões (`Rules`): Verdadeiro ou Falso (3 vidas, 10 médias e depois difíceis) e Alternativas
(3 vidas, 5 fáceis, 10 médias e depois difíceis). Se todos os vivos erram a mesma pergunta, ninguém
perde vida. Quando sobram 2, vira X1: morte súbita, com menos tempo a cada pergunta, até um errar
sozinho. Nas Alternativas, se o X1 passa de 10 perguntas, só vêm impossíveis, e nelas os dois
acertando ganha o mais rápido.
Sem QI: a colocação é a ordem de eliminação (mesma rodada desempata pelo tempo total de resposta).

Com poderes: os do clássico que não dependem de QI, armados na revelação para a próxima pergunta
(50/50 e Espiar na hora). Escudo segura uma vida, Roubo vira Roubo de vida, Alternativa falsa dá
um Escudo a quem jogou. Cada um ganha um no começo e outro a cada 3 acertos seguidos. Quem caiu vira
fantasma: a cada 3 perguntas ganha uma sabotagem para jogar nos vivos e, às vezes, a Ressurreição.
No X1 não tem poder.
"""

import random
from dataclasses import dataclass, field
from typing import Callable, Literal, Protocol

from app import powerups as pw
from app.duel import TRUE_FALSE_OPTIONS
from app.events import (
    Gift,
    LastingPowerUp,
    PowerUp,
    PowerUpGain,
    PowerUpUse,
    Survivor,
    SurvivalKind,
    SurvivalPick,
    SurvivalView,
    Stab,
)
from app.game import reading_seconds

START_SECONDS = 5.0
LEVEL_SECONDS = 3.0
RESULTS_SECONDS = 6.0
POWERS_RESULTS_SECONDS = 12.0  # dá tempo de escolher poder e alvo; todos pulando, acaba antes
DUEL_INTRO_SECONDS = 3.0
DUEL_RESULTS_SECONDS = 3.0
LATE_SECONDS = 1.0  # tolerância de rede para respostas no limite

# Poderes do modo. No V ou F, 50/50 e Alternativa falsa entregariam a resposta.
POWERS: tuple[PowerUp, ...] = (
    "fifty_fifty", "peek", "shield", "extra_time", "second_chance", "reverse", "theme", "backpack", "medkit", "hide",
    "scratch", "steal", "scramble", "accelerator", "mirror", "magnifier", "silence", "decoy", "flashbang",
    "curse", "blood_pact",
)
# Ataques que só existem aqui: o Reverso também devolve, mas eles não entram no sorteio de lendários do clássico.
TARGETED: frozenset[PowerUp] = pw.TARGETED | {"curse", "blood_pact"}
CURSE_LIVES = 2  # Maldição: errando, o alvo perde 2 vidas
DAGGER_CHANCE = 0.04  # Adaga (mítico): chance a cada poder ganho por acertos seguidos
TRUE_FALSE_BLOCKED: frozenset[PowerUp] = frozenset({"fifty_fifty", "decoy"})
LASTING: dict[PowerUp, int] = {"extra_time": 3, "shield": 2, "second_chance": 2, "reverse": 3}
TRUE_FALSE_SECOND_CHANCE_ROUNDS = 1  # com 2 opções a segunda tentativa é acerto garantido
GHOST_EVERY = 3  # perguntas entre um presente e outro para quem caiu
GHOST_SABOTAGES: tuple[PowerUp, ...] = ("scramble", "accelerator", "mirror", "magnifier", "flashbang")
GHOST_RESURRECTION_CHANCE = 0.08
DECOY_SHIELD_ROUNDS = 1  # Escudo para quem jogou a Alternativa falsa em quem caiu nela

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
        lives=3, levels=(("medium", 10),), answer_seconds=10.0, reading=False,
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
class Decoy:
    texts: list[str]
    order: list[int]  # posição na tela → índice em opções reais + falsas
    payees: list[str]  # quem jogou e ganha o Escudo se o alvo cair


@dataclass
class Survival:
    kind: SurvivalKind
    contenders: list[Contender]
    pool: list[Asked]  # perguntas dos temas escolhidos, de todos os níveis
    used: set[str]  # ids já sorteados nesta sala, para "jogar de novo" trazer perguntas novas
    rng: random.Random
    powers: bool = False
    powerup_max: int = pw.MAX_HELD
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
    ready: set[str] = field(default_factory=set)
    # Poderes (ver powerups.py para o que cada um faz no clássico).
    held: dict[str, list[PowerUp]] = field(default_factory=dict)
    mythics: dict[str, list[PowerUp]] = field(default_factory=dict)
    starting: dict[str, PowerUp] = field(default_factory=dict)
    extra_slots: dict[str, int] = field(default_factory=dict)
    armed: dict[str, PowerUpUse] = field(default_factory=dict)
    active: list[PowerUpUse] = field(default_factory=list)
    lasting: dict[str, dict[PowerUp, int]] = field(default_factory=dict)  # perguntas que faltam, contando a atual
    lasting_total: dict[str, dict[PowerUp, int]] = field(default_factory=dict)
    silences: list[tuple[PowerUpUse, int]] = field(default_factory=list)
    hidden_options: dict[str, list[int]] = field(default_factory=dict)
    first_wrong: dict[str, tuple[int, float]] = field(default_factory=dict)
    decoys: dict[str, Decoy | None] = field(default_factory=dict)
    theme_choices: list[str] = field(default_factory=list)
    next_theme: str | None = None
    runs: dict[str, int] = field(default_factory=dict)  # acertos seguidos rumo ao próximo poder
    revived: list[str] = field(default_factory=list)  # ressuscitados nesta revelação
    stabs: list[Stab] = field(default_factory=list)  # Adagas usadas nesta revelação
    blessed: set[str] = field(default_factory=set)  # quem ganhou a Bênção para a próxima pergunta
    blessing: set[str] = field(default_factory=set)  # quem vê a resposta certa nesta pergunta
    gifts: list[Gift] = field(default_factory=list)  # poderes ganhos nesta revelação

    @classmethod
    def create(
        cls,
        kind: SurvivalKind,
        player_ids: list[str],
        pool: list[Asked],
        used: set[str],
        rng: random.Random,
        now: float,
        powers: bool = False,
        powerup_max: int = pw.MAX_HELD,
    ) -> "Survival":
        lives = RULES[kind].lives
        game = cls(
            kind=kind, contenders=[Contender(pid, lives) for pid in player_ids], pool=pool, used=used, rng=rng,
            powers=powers, powerup_max=powerup_max,
        )
        if powers:
            for pid in player_ids:
                game.starting[pid] = game.rng.choice(game.power_kinds())
                game.held[pid] = [game.starting[pid]]
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
        return all(pid in self.answers or self._hiding(pid) for pid in self.answering_ids() if pid in connected)

    def _hiding(self, player_id: str) -> bool:
        return not self.in_duel() and self._affects("hide", player_id)

    def everyone_ready(self, connected: list[str]) -> bool:
        return self.phase == "results" and all(pid in self.ready for pid in connected)

    def answer_seconds(self) -> float:
        r = self.rules
        if self.in_duel():
            return max(r.duel_min_seconds, r.duel_first_seconds - r.duel_step_seconds * (self.duel_round - 1))
        return r.answer_seconds

    def answer_window(self, player_id: str) -> float:
        """Segundos que o jogador tem: Tempo extra soma, Acelerador corta."""
        seconds = self.answer_seconds()
        if self._affects("extra_time", player_id):
            seconds += pw.EXTRA_SECONDS
        if self._affects("accelerator", player_id):
            seconds *= pw.ACCELERATOR_FACTOR
        return seconds

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
        """Quando o servidor fecha a fase: nas respostas, o prazo mais longo, com a tolerância de rede."""
        if self.phase in ("answering", "duel_answering"):
            longest = max([self.answer_seconds(), *(self.answer_window(pid) for pid in self.answering_ids())])
            return self.phase_started_at + longest + LATE_SECONDS
        return self.phase_ends_at

    def power_kinds(self) -> list[PowerUp]:
        return [k for k in POWERS if not (self.kind == "true_false" and k in TRUE_FALSE_BLOCKED)]

    def powers_round(self) -> bool:
        return self.powers and not self.in_duel() and self.phase not in ("starting", "finished")

    def can_arm(self) -> bool:
        """Na revelação, se a próxima pergunta não é do X1."""
        return self.powers and self.phase == "results" and len(self.alive_ids()) > 2

    def capacity(self, player_id: str) -> int:
        return self.powerup_max + self.extra_slots.get(player_id, 0)

    def silence_left(self, player_id: str) -> int:
        if not self.powers_round():
            return 0
        return max((left for use, left in self.silences if use.target == player_id), default=0)

    # --- ações ------------------------------------------------------------

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase not in ("answering", "duel_answering"):
            raise SurvivalError("Não dá para responder agora.")
        if player_id not in self.answering_ids():
            raise SurvivalError("Você está fora desta rodada.")
        if player_id in self.answers:
            raise SurvivalError("Você já respondeu.")
        if self._hiding(player_id):
            raise SurvivalError("Você está escondido nesta pergunta.")
        deadline = self.phase_started_at + self.answer_window(player_id)
        if now > deadline + LATE_SECONDS:
            raise SurvivalError("O tempo acabou.")
        decoy = self._decoy_for(player_id)
        real = len(self.question.options)
        if option not in range(real + (len(decoy.texts) if decoy else 0)):
            raise SurvivalError("Resposta inválida.")
        if decoy:
            option = decoy.order[option]
        tried = self.first_wrong.get(player_id)
        if option in self.hidden_options.get(player_id, []) or (tried and tried[0] == option):
            raise SurvivalError("Resposta inválida.")
        at = min(now, deadline)
        if option != self.question.answer and not tried and self._affects("second_chance", player_id):
            self.first_wrong[player_id] = (option, at)
            self.lasting[player_id].pop("second_chance", None)
            return
        self.answers[player_id] = (option, at)

    def mark_ready(self, player_id: str) -> None:
        if self.phase != "results":
            raise SurvivalError("Agora não dá para pular.")
        self.ready.add(player_id)

    def arm(self, player_id: str, kind: PowerUp, target: str | None, theme: str | None = None) -> None:
        if not self.powers or self.phase != "results":
            raise SurvivalError("Agora não dá para usar habilidade.")
        if self.silence_left(player_id):
            raise SurvivalError("Silenciado: sem habilidades por enquanto.")
        me = self.contender(player_id)
        if kind == "resurrection":
            return self._resurrect(player_id)
        if kind == "dagger":
            return self._stab(player_id, target)
        held = self.held.get(player_id, [])
        if kind not in held:
            raise SurvivalError("Você não tem essa habilidade.")
        if kind == "backpack":
            return self._open_backpack(player_id)
        if kind == "medkit":
            return self._heal(player_id)
        if not self.can_arm():
            raise SurvivalError("No X1 não tem habilidade.")
        if player_id in self.armed:
            raise SurvivalError("Você já armou uma habilidade para a próxima pergunta.")
        if kind in pw.INSTANT:
            raise SurvivalError("Essa se usa na hora da pergunta.")
        if not me.alive and kind not in TARGETED:
            raise SurvivalError("Fantasma só joga sabotagem nos vivos.")
        if kind in TARGETED:
            alive = self.alive_ids()
            if target is None or target == player_id or target not in alive:
                raise SurvivalError("Escolha em quem usar (só em quem está vivo).")
        else:
            target = None
        if kind == "theme":
            if theme not in self.theme_choices:
                raise SurvivalError("Escolha um dos temas.")
            if self.next_theme:
                raise SurvivalError("Alguém já escolheu o tema da próxima pergunta.")
            self.next_theme = theme
        else:
            theme = None
        held.remove(kind)
        self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=target, reflected_by=None, theme=theme)

    def use_now(self, player_id: str, kind: PowerUp) -> None:
        """50/50 e Espiar: durante a pergunta, valem na hora."""
        if self.phase not in ("reading", "answering") or not self.powers_round():
            raise SurvivalError("Agora não dá para usar habilidade.")
        if kind not in pw.INSTANT:
            raise SurvivalError("Essa se arma na revelação.")
        if player_id not in self.alive_ids():
            raise SurvivalError("Você está fora.")
        if self.silence_left(player_id):
            raise SurvivalError("Silenciado: sem habilidades por enquanto.")
        held = self.held.get(player_id, [])
        if kind not in held:
            raise SurvivalError("Você não tem essa habilidade.")
        if player_id in self.answers:
            raise SurvivalError("Você já respondeu.")
        if self._affects(kind, player_id):
            raise SurvivalError("Já está valendo.")
        held.remove(kind)
        self.active.append(PowerUpUse(kind=kind, by=player_id, target=None, reflected_by=None))
        if kind == "fifty_fifty":
            q = self.question
            self.hidden_options[player_id] = pw.fifty_fifty(len(q.options), q.answer, self.rng)

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
        self.active = []
        self._enter("finished", now, 0)

    def _next_question(self, now: float) -> None:
        alive = self.alive_ids()
        if len(alive) <= 1:
            return self._finish(now, alive[0] if alive else None)
        if self.in_duel() and len(self.duelists) < 2:
            return self._finish(now, self.duelists[0] if self.duelists else None)
        self.round += 1
        self.ready = set()
        self.revived = []
        self.stabs = []
        self.gifts = []
        if len(alive) == 2 and not self.in_duel():
            self.duelists = alive
            self.duel_round = 1
            self.armed = {}
            self.active = []
            self.blessed, self.blessing = set(), set()  # no X1 não tem poder
            self.question = self._draw(self.difficulty())
            self._enter("duel_intro", now, DUEL_INTRO_SECONDS)
            return
        if self.in_duel():
            self.duel_round += 1
        else:
            self._start_powers()
        self.question = self._draw(self.difficulty(), self.next_theme)
        self.next_theme = None
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
        real = len(self.question.options)
        for pid in self.answering_ids():
            c = self.contender(pid)
            if self._hiding(pid):
                self.picks.append(SurvivalPick(player_id=pid, option=None, correct=False, elapsed_ms=None, lost_life=False, hidden=True))
                continue
            window_ms = round(self.answer_window(pid) * 1000)
            first = self.first_wrong.get(pid)
            option, at = self.answers.get(pid) or first or (None, None)
            elapsed = min(window_ms, round((at - self.phase_started_at) * 1000)) if at is not None else None
            correct = option is not None and option == self.question.answer
            c.answer_ms += window_ms if elapsed is None else elapsed
            c.correct += correct
            decoy = self._decoy_for(pid)
            self.picks.append(
                SurvivalPick(
                    player_id=pid,
                    option=option,
                    correct=correct,
                    elapsed_ms=elapsed,
                    lost_life=False,
                    first_option=first[0] if first and (option, at) != first else None,
                    decoy=decoy.texts[option - real] if decoy and option is not None and option >= real else None,
                )
            )
        counted = [p for p in self.picks if not p.hidden]
        wrong = [p for p in counted if not p.correct]
        if self.in_duel():
            self._close_duel(wrong)
            self._enter("duel_results", now, DUEL_RESULTS_SECONDS)
            return
        self.spared = len(wrong) == len(counted) and len(counted) > 0
        if not self.spared:
            for pick in wrong:
                c = self.contender(pick.player_id)
                if self._shielded(pick):
                    continue
                pick.lost_life = True
                c.lives -= 1
                if self._affects("curse", pick.player_id):
                    pick.cursed = True
                    c.lives -= CURSE_LIVES - 1
            self._blood_pacts()
        if self.powers:
            self._settle_powers()
        for pick in self.picks:
            c = self.contender(pick.player_id)
            if c.lives <= 0 and c.alive:
                c.out_round = self.round
        if self.powers:
            self._gains()
            self.theme_choices = self._draw_theme_choices()
        self._enter("results", now, POWERS_RESULTS_SECONDS if self.powers else RESULTS_SECONDS)

    def _shielded(self, pick: SurvivalPick) -> bool:
        """O Escudo segura a vida (e a Maldição junto)."""
        if not self._affects("shield", pick.player_id):
            return False
        pick.shielded = True
        self.lasting[pick.player_id].pop("shield", None)
        return True

    def _blood_pacts(self) -> None:
        """Pacto de sangue: quem jogou perdeu vida, o alvo perde uma também."""
        by_id = {p.player_id: p for p in self.picks}
        for use in self.active:
            source, victim = by_id.get(use.by), by_id.get(use.target)
            target = self.contender(use.target)
            if use.kind != "blood_pact" or not source or not source.lost_life or not target or not target.alive:
                continue
            if victim and self._shielded(victim):
                continue
            target.lives -= 1
            if victim:
                victim.pact_from = use.by
                victim.lost_life = True

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

    def _draw(self, difficulty: str, theme: str | None = None) -> Asked:
        """Sorteia uma pergunta do nível (e do tema, com o poder Tema) que ainda não saiu; se
        acabaram, libera as do nível de novo. As alternativas das perguntas do banco vêm embaralhadas."""
        level = [q for q in self.pool if q.difficulty == difficulty] or [q for q in self.pool if q.difficulty == "hard"] or self.pool
        if theme:
            level = [q for q in level if q.theme == theme] or level
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

    # --- poderes ----------------------------------------------------------

    def _start_powers(self) -> None:
        """Começo de uma pergunta comum: o que foi armado passa a valer (o Reverso devolve)."""
        self.silences = [(use, left - 1) for use, left in self.silences if left > 1]
        self.hidden_options = {}
        self.first_wrong = {}
        self.decoys = {}
        self.theme_choices = []
        armed = list(self.armed.values())
        self.armed = {}
        for use in armed:
            if use.kind in LASTING:
                rounds = LASTING[use.kind]
                if use.kind == "second_chance" and self.kind == "true_false":
                    rounds = TRUE_FALSE_SECOND_CHANCE_ROUNDS
                self.lasting.setdefault(use.by, {})[use.kind] = rounds
                self.lasting_total.setdefault(use.by, {})[use.kind] = rounds
        reversers = {pid for pid in self.lasting if self._affects("reverse", pid)}
        self.active = [self._reflect_own(use, reversers) for use in pw.reflect(armed, reversers)]
        self.blessing, self.blessed = self.blessed, set()
        for use in self.active:
            if use.reflected_by:
                self.lasting[use.reflected_by].pop("reverse", None)
            if use.kind == "silence":
                self.silences.append((use, pw.SILENCE_ROUNDS))

    def _reflect_own(self, use: PowerUpUse, reversers: set[str]) -> PowerUpUse:
        """O Reverso com os ataques daqui: a Maldição volta para quem jogou, e o Pacto passa a amarrar
        quem jogou ao alvo (se o alvo perder vida, quem jogou perde também)."""
        if use.kind not in ("curse", "blood_pact") or use.target not in reversers:
            return use
        if use.kind == "curse":
            return PowerUpUse(kind="curse", by=use.by, target=use.by, reflected_by=use.target)
        return PowerUpUse(kind="blood_pact", by=use.target, target=use.by, reflected_by=use.target)

    def _affects(self, kind: PowerUp, player_id: str) -> bool:
        if not self.powers_round():
            return False
        if kind == "silence":
            return self.silence_left(player_id) > 0
        if kind in LASTING:
            return self.lasting.get(player_id, {}).get(kind, 0) > 0
        return any((use.target or use.by) == player_id for use in self.active if use.kind == kind)

    def _decoy_for(self, player_id: str) -> Decoy | None:
        if player_id not in self.decoys:
            payees = [use.reflected_by or use.by for use in self.active if use.kind == "decoy" and use.target == player_id]
            self.decoys[player_id] = self._make_decoy(payees) if payees and self.powers_round() else None
        return self.decoys[player_id]

    def _make_decoy(self, payees: list[str]) -> Decoy | None:
        q = self.question
        similar = [o for other in self.pool if other.theme == q.theme and other.text != q.text for o in other.options]
        self.rng.shuffle(similar)
        texts = pw.decoys(q.options[q.answer], q.options, similar[:48], self.rng)
        if not texts:
            return None
        order = list(range(len(q.options) + len(texts)))
        self.rng.shuffle(order)
        return Decoy(texts=texts, order=order, payees=payees)

    def _settle_powers(self) -> None:
        """Depois das vidas: Roubo de vida, Escudo de quem pegou alguém na falsa, e o desgaste
        das que duram mais de uma pergunta."""
        by_id = {p.player_id: p for p in self.picks}
        for use in self.active:
            if use.kind == "steal" and (victim := by_id.get(use.target)) and victim.lost_life:
                thief = self.contender(use.by)
                if thief and thief.alive and thief.lives > 0:
                    thief.lives = min(self.rules.lives, thief.lives + 1)
                    victim.stolen_by = use.by
        for pick in self.picks:
            decoy = self.decoys.get(pick.player_id)
            if pick.decoy and decoy:
                for payee in decoy.payees:
                    self.lasting.setdefault(payee, {})["shield"] = DECOY_SHIELD_ROUNDS + 1
                    self.lasting_total.setdefault(payee, {})["shield"] = DECOY_SHIELD_ROUNDS
        for kinds in self.lasting.values():
            for kind in list(kinds):
                kinds[kind] -= 1
                if kinds[kind] <= 0:
                    del kinds[kind]

    def _gains(self) -> None:
        """Um poder a cada 3 acertos seguidos; quem caiu ganha uma sabotagem a cada 3 perguntas."""
        for pick in self.picks:
            pid = pick.player_id
            if pick.hidden:
                continue  # escondido: a sequência nem anda nem quebra
            if not pick.correct or pick.first_option is not None:
                self.runs[pid] = 0
                continue
            self.runs[pid] = self.runs.get(pid, 0) + 1
            if self.runs[pid] >= pw.STREAK_FOR_POWERUP:
                self.runs[pid] = 0
                if self.rng.random() < DAGGER_CHANCE and "dagger" not in self.mythics.get(pid, []):
                    self._give(pid, "dagger", "streak", mythic=True)
                else:
                    self._give(pid, self.rng.choice(self.power_kinds()), "streak")
        if self.round % GHOST_EVERY:
            return
        for c in self.contenders:
            if c.alive or c.out_round == self.round:
                continue
            mythic = self.rng.random() < GHOST_RESURRECTION_CHANCE and "resurrection" not in self.mythics.get(c.id, [])
            kind = "resurrection" if mythic else self.rng.choice(GHOST_SABOTAGES)
            self._give(c.id, kind, "ghost", mythic=mythic)

    def _give(self, player_id: str, kind: PowerUp, reason: str, mythic: bool = False) -> None:
        """Com as mãos cheias, não ganha nada (o mítico não ocupa vaga)."""
        hand = self.mythics.setdefault(player_id, []) if mythic else self.held.setdefault(player_id, [])
        if not mythic and len(hand) >= self.capacity(player_id):
            return
        hand.append(kind)
        self.gifts.append(Gift(player_id=player_id, gain=PowerUpGain(kind=kind, reason=reason, mythic=mythic)))

    def _open_backpack(self, player_id: str) -> None:
        if self.extra_slots.get(player_id, 0) >= pw.BACKPACK_MAX_EXTRA:
            raise SurvivalError("Sua Mochila já está no tamanho máximo.")
        held = self.held[player_id]
        held.remove("backpack")
        self.extra_slots[player_id] = self.extra_slots.get(player_id, 0) + 1
        held.append(self.rng.choice([k for k in self.power_kinds() if k != "backpack"]))

    def _heal(self, player_id: str) -> None:
        c = self.contender(player_id)
        if not c.alive:
            raise SurvivalError("Kit médico é para quem está vivo.")
        if c.lives >= self.rules.lives:
            raise SurvivalError("Você já está com todas as vidas.")
        self.held[player_id].remove("medkit")
        c.lives += 1

    def _stab(self, player_id: str, target_id: str | None) -> None:
        """Adaga: tira 1 vida do alvo na hora. Se eliminar, quem usou ganha a Bênção na próxima."""
        me, target = self.contender(player_id), self.contender(target_id or "")
        if "dagger" not in self.mythics.get(player_id, []):
            raise SurvivalError("Você não tem essa habilidade.")
        if not me.alive:
            raise SurvivalError("A Adaga é para quem está vivo.")
        if not self.can_arm():
            raise SurvivalError("No X1 não tem habilidade.")
        if not target or target is me or not target.alive:
            raise SurvivalError("Escolha em quem usar (só em quem está vivo).")
        self.mythics[player_id].remove("dagger")
        target.lives -= 1
        eliminated = target.lives <= 0
        if eliminated:
            target.lives = 0
            target.out_round = self.round
            self.blessed.add(player_id)
        self.stabs.append(Stab(by=player_id, target=target.id, eliminated=eliminated))

    def _resurrect(self, player_id: str) -> None:
        c = self.contender(player_id)
        if "resurrection" not in self.mythics.get(player_id, []):
            raise SurvivalError("Você não tem essa habilidade.")
        if c.alive or self.in_duel() or len(self.alive_ids()) < 2:
            raise SurvivalError("A Ressurreição é para quem caiu, antes do X1.")
        self.mythics[player_id].remove("resurrection")
        c.out_round = None
        c.lives = 1
        self.revived.append(player_id)

    def _draw_theme_choices(self) -> list[str]:
        themes = sorted({q.theme for q in self.pool})
        return sorted(self.rng.sample(themes, min(pw.THEME_CHOICES, len(themes))))

    # --- ranking e visão --------------------------------------------------

    def places(self) -> dict[str, int]:
        """Colocação de cada um: o vencedor, depois quem caiu mais tarde (vivos antes de todos)."""

        def key(c: Contender) -> tuple:
            return (c.id != self.winner, -(c.out_round if c.out_round is not None else 10**6), -c.lives, c.answer_ms)

        return {c.id: i + 1 for i, c in enumerate(sorted(self.contenders, key=key))}

    def _screen(self, viewer: str | None) -> tuple[list[str], Callable[[int | None], int | None]]:
        """Alternativas na ordem da tela de quem vê (com as falsas, se for o alvo)."""
        q = self.question
        real = len(q.options)
        decoy = self.decoys.get(viewer) if viewer else None
        if not decoy:
            return q.options, lambda i: i if i is not None and i < real else None
        everything = [*q.options, *decoy.texts]
        return [everything[i] for i in decoy.order], lambda i: decoy.order.index(i) if i is not None else None

    def view(self, now: float, viewer: str | None, player_ids: list[str]) -> SurvivalView:
        revealed = self.phase in ("results", "duel_results")
        showing = self.phase in ("reading", "duel_reading", "answering", "duel_answering", "results", "duel_results")
        places = self.places() if self.phase == "finished" else {}
        q = self.question if showing else None
        counts = dict(self.rules.levels)
        silenced = self.silence_left(viewer) if viewer else 0
        hidden = revealed and silenced > 0  # silenciado não vê a revelação
        if q and viewer and self.phase in ("reading", "answering"):
            self._decoy_for(viewer)
        options, screen = self._screen(viewer) if q else ([], lambda i: i)
        ends_at = self.phase_ends_at
        if self.phase == "answering" and viewer in self.answering_ids():
            ends_at = self.phase_started_at + self.answer_window(viewer)
        asking = self.phase in ("reading", "answering")
        peek = None
        if asking and viewer and self._affects("peek", viewer):
            real = len(q.options)
            tally = [0] * real
            for pid, (option, _) in {**self.answers, **self.first_wrong}.items():
                if pid != viewer and option < real:
                    tally[option] += 1
            peek = [tally[i] if i < real else 0 for i in self._underlying_order(viewer)]
        mine = self.first_wrong.get(viewer) if viewer else None
        return SurvivalView(
            kind=self.kind,
            phase=self.phase,
            phase_duration_ms=round((ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((ends_at - now) * 1000)),
            round=self.round,
            duel_round=self.duel_round,
            easy_count=counts.get("easy", 0),
            medium_count=counts.get("medium", 0),
            max_lives=self.rules.lives,
            difficulty=self.difficulty() if self.round else self.rules.levels[0][0],
            text=q.text if q else None,
            theme=q.theme if q else None,
            options=options if q else list(TRUE_FALSE_OPTIONS if self.kind == "true_false" else []),
            answered=[] if silenced else [pid for pid in {*self.answers, *self.first_wrong} if pid in player_ids],
            my_answer=screen(self.answers[viewer][0]) if viewer in self.answers else None,
            picks=[] if hidden or not revealed else [self._pick_view(p, viewer, screen) for p in self.picks],
            correct_option=screen(q.answer) if q and revealed and not hidden else None,
            fact=q.fact if q and revealed and not hidden else None,
            spared=self.spared and not hidden,
            duelists=list(self.duelists),
            next_seconds=self.answer_seconds() if self.in_duel() else None,
            winner=self.winner,
            survivors=[
                Survivor(
                    player_id=c.id,
                    lives=-1 if silenced and c.id != viewer else c.lives,
                    out_round=c.out_round,
                    correct=c.correct,
                    answer_ms=c.answer_ms,
                    place=places.get(c.id),
                )
                for c in self.contenders
                if c.id in player_ids
            ],
            powers=self.powers,
            powerups=list(self.held.get(viewer, [])) if viewer else [],
            legendary_powerups=[],
            mythic_powerups=list(self.mythics.get(viewer, [])) if viewer else [],
            powerup_max=self.capacity(viewer) if viewer else self.powerup_max,
            starting_powerup=self.starting.get(viewer) if viewer else None,
            can_arm=self.can_arm() and not silenced,
            armed=self.armed.get(viewer) if viewer else None,
            active=[] if hidden else self._visible_uses(viewer, revealed),
            lasting=self._lasting_view(viewer) if viewer and not revealed else [],
            hidden_options=[screen(i) for i in self.hidden_options.get(viewer, [])] if viewer else [],
            first_wrong=screen(mine[0]) if mine else None,
            peek=peek,
            flashbang=bool(viewer) and asking and self._affects("flashbang", viewer),
            silenced_rounds=silenced,
            theme_choices=self.theme_choices,
            powers_round=self.powers_round(),
            ready=sorted(self.ready),
            revived=list(self.revived),
            stabs=list(self.stabs),
            hiding=bool(viewer) and asking and self._hiding(viewer),
            blessing=screen(q.answer) if q and asking and viewer in self.blessing and not self.in_duel() else None,
            gifts=self.gifts if revealed and not hidden else [],
        )

    def _underlying_order(self, viewer: str) -> list[int]:
        decoy = self.decoys.get(viewer)
        return decoy.order if decoy else list(range(len(self.question.options)))

    def _pick_view(self, pick: SurvivalPick, viewer: str | None, screen: Callable[[int | None], int | None]) -> SurvivalPick:
        """Escolhas na ordem da tela de quem vê; a falsa em que outro caiu não tem lugar nela."""
        real = len(self.question.options)
        own = pick.player_id == viewer

        def place(option: int | None) -> int | None:
            return None if option is None or (not own and option >= real) else screen(option)

        return pick.model_copy(update={"option": place(pick.option), "first_option": place(pick.first_option)})

    def _lasting_view(self, viewer: str) -> list[LastingPowerUp]:
        lasting = [
            LastingPowerUp(kind=kind, rounds_left=left, total=self.lasting_total[viewer][kind])
            for kind, left in self.lasting.get(viewer, {}).items()
            if self._affects(kind, viewer)
        ]
        if silence_left := self.silence_left(viewer):
            lasting.append(LastingPowerUp(kind="silence", rounds_left=silence_left, total=pw.SILENCE_ROUNDS))
        return lasting

    def _visible_uses(self, viewer: str | None, revealed: bool) -> list[PowerUpUse]:
        """O Roubo de vida é surpresa até a revelação; o Reverso armado só o dono vê."""
        if not self.powers_round() and not revealed:
            return []
        uses = [use for use in self.active if use.kind != "reverse" or use.by == viewer]
        return uses if revealed else [use for use in uses if use.kind != "steal" or use.by == viewer]
