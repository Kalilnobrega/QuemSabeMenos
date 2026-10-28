"""Batata quente: um jogador por vez responde, os outros assistem.

A batata começa com alguém da roda. Quem está com ela responde perguntas fáceis e médias:
acertou, a batata passa para o próximo; errou, perde 10 segundos de pavio e vem outra pergunta.
O pavio (40 a 60 segundos, escondido) só queima enquanto alguém está respondendo. Quando acaba,
ou quando alguém erra 3 seguidas, a batata explode e quem está com ela sai. A rodada seguinte
começa com o próximo da roda e um pavio novo, até sobrar um.

Com poderes: cada um começa com um e ganha outro a cada 3 acertos seguidos. As ajudas só quem está
com a batata usa, na hora; as sabotagens quem assiste joga em quem está com a batata, valendo na
pergunta atual. Quem explodiu vira fantasma e ganha uma sabotagem a cada explosão de outro (às
vezes, a Ressurreição, que traz de volta para a roda), e quem continua vivo ganha um poder.

Batata dupla (mítico): entra uma segunda batata, dourada, com pavio próprio, que nunca vai para quem
a jogou e dura até explodir. Ela começa com quem está mais longe da principal na roda. Quem estiver
com as duas responde uma pergunta para cada uma.
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app import powerups as pw
from app.events import Gift, HotPotatoPlayer, HotPotatoTurn, HotPotatoView, PotatoView, PowerUp, PowerUpGain, PowerUpUse
from app.game import Question

START_SECONDS = 5.0
FUSE_SECONDS = (40.0, 60.0)
GOLDEN_FUSE_SECONDS = (30.0, 45.0)  # a Batata dupla queima um pouco mais rápido
WRONG_PENALTY_SECONDS = 10.0
MAX_WRONG_STREAK = 3  # erros seguidos de quem está com a batata: explode na hora
PASS_SECONDS = 1.0  # a batata voando para o próximo (o pavio dela para)
WRONG_SECONDS = 1.2  # mostra o erro antes da próxima pergunta (o pavio dela para)
EXPLODED_SECONDS = 4.0
DIFFICULTIES = ("easy", "medium")

HELPS: tuple[PowerUp, ...] = ("fifty_fifty", "shield", "second_chance", "cold_water", "reverse", "free_pass", "thermometer")
SABOTAGES: tuple[PowerUp, ...] = ("accelerator", "scramble", "mirror", "magnifier", "flashbang", "scratch", "short_fuse", "double_bomb")
GHOST_SABOTAGES: tuple[PowerUp, ...] = SABOTAGES + ("scare",)  # o Susto é só dos fantasmas
COLD_WATER_SECONDS = 10.0
SHORT_FUSE_SECONDS = 10.0
ACCELERATOR_RATE = 2.0  # o pavio queima 2x mais rápido até a próxima pergunta
DOUBLE_BOMB_RIGHTS = 2  # Bomba dupla: acertos seguidos para conseguir passar
RESURRECTION_CHANCE = 0.08
DOUBLE_POTATO_CHANCE = 0.04  # Batata dupla: chance a cada poder ganho por acertos seguidos
DOUBLE_POTATO_MIN_ALIVE = 3

Phase = Literal["starting", "playing", "exploded", "finished"]
State = Literal["asking", "passing", "wrong", "again"]


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
class Potato:
    id: int
    holder: str
    golden: bool = False
    excluded: str | None = None  # quem jogou a Batata dupla: ela nunca vai para essa pessoa
    fuse_total: float = 0
    fuse_left: float = 0  # segundos de pavio em `burn_from`
    burn_from: float = 0  # desde quando o pavio queima no ritmo `burn_rate`
    burn_rate: float = 1.0
    state: State = "asking"
    state_started_at: float = 0
    state_ends_at: float = 0
    wrong_streak: int = 0
    need_right: int = 1
    bomb: bool = False  # Bomba dupla valendo enquanto ela estiver com o mesmo jogador
    thermometer: bool = False  # Termômetro valendo enquanto ela estiver com o mesmo jogador
    question: Question | None = None
    turn: HotPotatoTurn | None = None  # a última resposta, para a tela de passe ou erro
    uses: list[PowerUpUse] = field(default_factory=list)  # na pergunta atual
    hidden_options: list[int] = field(default_factory=list)
    first_wrong: int | None = None
    second_chance: bool = False  # vale na pergunta atual


@dataclass
class HotPotato:
    players: list[Holder]  # a ordem da roda
    pool: list[Question]
    used: set[str]
    rng: random.Random
    powers: bool = False
    powerup_max: int = pw.MAX_HELD
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = 0
    potatoes: list[Potato] = field(default_factory=list)  # a principal (id 0) e, às vezes, a dourada
    direction: Literal[1, -1] = 1
    exploded: str | None = None
    exploded_potato: Potato | None = None
    winner: str | None = None
    # Poderes.
    held: dict[str, list[PowerUp]] = field(default_factory=dict)
    mythics: dict[str, list[PowerUp]] = field(default_factory=dict)
    starting: dict[str, PowerUp] = field(default_factory=dict)
    shields: set[str] = field(default_factory=set)  # segura o próximo erro de quem tem
    runs: dict[str, int] = field(default_factory=dict)  # acertos seguidos rumo ao próximo poder
    gifts: list[Gift] = field(default_factory=list)
    revived: list[str] = field(default_factory=list)

    @classmethod
    def create(
        cls,
        player_ids: list[str],
        pool: list[Question],
        used: set[str],
        rng: random.Random,
        now: float,
        powers: bool = False,
        powerup_max: int = pw.MAX_HELD,
    ) -> "HotPotato":
        game = cls(
            players=[Holder(pid) for pid in player_ids], pool=[q for q in pool if q.difficulty in DIFFICULTIES],
            used=used, rng=rng, powers=powers, powerup_max=powerup_max,
        )
        if powers:
            for pid in player_ids:
                game.starting[pid] = rng.choice(HELPS + SABOTAGES)
                game.held[pid] = [game.starting[pid]]
        game._enter("starting", now, START_SECONDS)
        return game

    # --- consultas --------------------------------------------------------

    def player(self, player_id: str) -> Holder | None:
        return next((p for p in self.players if p.id == player_id), None)

    def alive_ids(self) -> list[str]:
        return [p.id for p in self.players if p.alive]

    @property
    def main(self) -> Potato | None:
        return next((p for p in self.potatoes if not p.golden), None)

    @property
    def golden(self) -> Potato | None:
        return next((p for p in self.potatoes if p.golden), None)

    def potato(self, potato_id: int | None) -> Potato | None:
        return next((p for p in self.potatoes if p.id == potato_id), None)

    def held_by(self, player_id: str) -> list[Potato]:
        return [p for p in self.potatoes if p.holder == player_id]

    def burning(self, potato: Potato) -> bool:
        return self.phase == "playing" and potato.state == "asking"

    def fuse_at(self, potato: Potato, now: float) -> float:
        """Segundos de pavio que faltam agora."""
        if self.burning(potato):
            return max(0.0, potato.fuse_left - (now - potato.burn_from) * potato.burn_rate)
        return potato.fuse_left

    def potato_deadline(self, potato: Potato) -> float:
        if potato.state == "asking":
            return potato.burn_from + potato.fuse_left / potato.burn_rate
        return potato.state_ends_at

    def deadline(self) -> float:
        if self.phase == "playing" and self.potatoes:
            return min(self.potato_deadline(p) for p in self.potatoes)
        return self.phase_ends_at

    # --- ações ------------------------------------------------------------

    def answer(self, player_id: str, option: int, now: float, potato_id: int | None = None) -> None:
        if self.phase != "playing":
            raise HotPotatoError("Agora não dá para responder.")
        potato = self._mine(player_id, potato_id)
        if potato.state != "asking":
            raise HotPotatoError("Agora não dá para responder.")
        if option not in range(len(potato.question.options)) or option in potato.hidden_options or option == potato.first_wrong:
            raise HotPotatoError("Alternativa inválida.")
        if now >= self.potato_deadline(potato):
            return self._explode(potato, now)
        holder = self.player(player_id)
        self._burn(potato, now)
        correct = option == potato.question.answer
        if not correct and potato.second_chance and potato.first_wrong is None:
            potato.first_wrong = option  # tenta de novo, sem perder pavio
            potato.second_chance = False
            return
        potato.turn = HotPotatoTurn(
            player_id=player_id, option=option, correct=correct, correct_option=potato.question.answer,
            elapsed_ms=round((now - potato.state_started_at) * 1000),
        )
        if correct:
            holder.correct += 1
            potato.wrong_streak = 0
            self._count_run(player_id)
            if potato.need_right > 1:
                potato.need_right -= 1  # Bomba dupla: mais uma antes de passar
                return self._set_state(potato, "again", now, WRONG_SECONDS)
            return self._set_state(potato, "passing", now, PASS_SECONDS)
        holder.wrong += 1
        self.runs[player_id] = 0
        if potato.bomb:
            potato.need_right = DOUBLE_BOMB_RIGHTS  # errou: a Bomba dupla volta a pedir 2 seguidas
        if player_id in self.shields:
            self.shields.discard(player_id)
            potato.turn.shielded = True
            return self._set_state(potato, "wrong", now, WRONG_SECONDS)
        potato.wrong_streak += 1
        potato.fuse_left -= WRONG_PENALTY_SECONDS
        if potato.wrong_streak >= MAX_WRONG_STREAK or potato.fuse_left <= 0:
            return self._explode(potato, now)
        self._set_state(potato, "wrong", now, WRONG_SECONDS)

    def use(self, player_id: str, kind: PowerUp, now: float, potato_id: int | None = None) -> None:
        """Ajuda em si mesmo (com a batata na mão) ou sabotagem em quem está com a batata."""
        if not self.powers or self.phase in ("starting", "finished"):
            raise HotPotatoError("Agora não dá para usar habilidade.")
        me = self.player(player_id)
        if not me:
            raise HotPotatoError("Você não está na partida.")
        if kind == "resurrection":
            return self._resurrect(me)
        if kind == "double_potato":
            return self._double(me, now)
        if kind not in self.held.get(player_id, []):
            raise HotPotatoError("Você não tem essa habilidade.")
        if self.phase != "playing":
            raise HotPotatoError("Espere a próxima pergunta.")
        if kind in HELPS:
            potato = self._mine(player_id, potato_id)
        else:
            potato = self._target(player_id, potato_id)
        if potato.state != "asking":
            raise HotPotatoError("Espere a próxima pergunta.")
        if now >= self.potato_deadline(potato):
            raise HotPotatoError("O pavio acabou.")
        if any(u.kind == kind for u in potato.uses):
            raise HotPotatoError("Essa já foi usada nesta pergunta.")
        if kind == "shield" and player_id in self.shields:
            raise HotPotatoError("Seu Escudo já está armado.")
        if kind == "second_chance" and potato.first_wrong is not None:
            raise HotPotatoError("Você já errou esta.")
        if kind == "thermometer" and potato.thermometer:
            raise HotPotatoError("O Termômetro já está valendo.")
        if kind not in HELPS and any(u.by == player_id and u.kind not in HELPS for u in potato.uses):
            raise HotPotatoError("Uma sabotagem por pergunta.")
        self.held[player_id].remove(kind)
        potato.uses.append(PowerUpUse(kind=kind, by=player_id, target=None if kind in HELPS else potato.holder, reflected_by=None))
        self._apply(potato, kind, now)

    def drop(self, player_id: str, now: float) -> None:
        """Quem sai da sala está fora; se estava com uma batata, ela vai para o próximo."""
        p = self.player(player_id)
        if not p or not p.alive or self.phase == "finished":
            return
        p.out_round = self.round
        if len(self.alive_ids()) <= 1:
            return self._finish(now)
        for potato in self.held_by(player_id):
            self._hand_on(potato, player_id)
            if self.phase == "playing":
                self._ask(potato, now)

    def advance(self, now: float) -> None:
        """O tempo acabou: começa a partida, termina a explosão ou muda uma batata de estado
        (no asking, é o pavio dela que acabou)."""
        if self.phase == "starting":
            self.round = 1
            first = self.rng.choice(self.alive_ids())
            self.potatoes = [self._new_potato(0, first, FUSE_SECONDS)]
            self._enter("playing", now, 0)
            self._ask(self.potatoes[0], now)
        elif self.phase == "exploded":
            self._resume(now)
        elif self.phase == "playing" and self.potatoes:
            potato = min(self.potatoes, key=self.potato_deadline)
            if potato.state == "asking":
                self._explode(potato, now)
            elif potato.state == "passing":
                self._hand_on(potato, potato.holder)
                self._ask(potato, now)
            else:
                self._ask(potato, now)

    # --- transições -------------------------------------------------------

    def _enter(self, phase: Phase, now: float, seconds: float) -> None:
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds

    def _set_state(self, potato: Potato, state: State, now: float, seconds: float) -> None:
        potato.state = state
        potato.state_started_at = now
        potato.state_ends_at = now + seconds

    def _burn(self, potato: Potato, now: float) -> None:
        """Guarda o pavio que falta agora, para mudar o ritmo ou parar de queimar."""
        potato.fuse_left = self.fuse_at(potato, now)
        potato.burn_from = now

    def _new_potato(self, potato_id: int, holder: str, fuse: tuple[float, float], golden: bool = False, excluded: str | None = None) -> Potato:
        total = self.rng.uniform(*fuse)
        return Potato(id=potato_id, holder=holder, golden=golden, excluded=excluded, fuse_total=total, fuse_left=total)

    def _ask(self, potato: Potato, now: float) -> None:
        potato.question = self._draw()
        potato.turn = None
        potato.uses = []
        potato.hidden_options = []
        potato.first_wrong = None
        potato.second_chance = False
        potato.burn_from, potato.burn_rate = now, 1.0
        self.gifts = []
        self.revived = []
        self._set_state(potato, "asking", now, potato.fuse_left)

    def _hand_on(self, potato: Potato, after: str) -> None:
        """A batata vai para o próximo da roda; o que valia só com quem estava com ela acaba."""
        potato.holder = self._next_after(after, potato.excluded)
        potato.wrong_streak = 0
        potato.need_right = 1
        potato.bomb = False
        potato.thermometer = False

    def _explode(self, potato: Potato, now: float) -> None:
        for other in self.potatoes:
            if other is not potato and other.state == "asking":
                self._burn(other, now)  # a explosão para tudo: o pavio das outras congela
        potato.fuse_left = 0
        self.exploded = potato.holder
        self.exploded_potato = potato
        self.player(potato.holder).out_round = self.round
        self.gifts = []
        self._enter("exploded", now, EXPLODED_SECONDS)
        if self.powers:
            self._haunt()

    def _resume(self, now: float) -> None:
        """Depois da explosão: a principal recomeça com o próximo e um pavio novo; a dourada some.
        As outras batatas seguem, com pergunta nova, e as que estavam com quem saiu passam adiante."""
        if len(self.alive_ids()) <= 1:
            return self._finish(now)
        self.round += 1
        exploded, gone = self.exploded_potato, self.exploded
        if exploded.golden:
            self.potatoes.remove(exploded)
        else:
            fresh = self._new_potato(exploded.id, self._next_after(gone, None), FUSE_SECONDS)
            self.potatoes[self.potatoes.index(exploded)] = fresh
        for potato in self.potatoes:
            if not self.player(potato.holder).alive:
                self._hand_on(potato, potato.holder)
        self.exploded, self.exploded_potato = None, None
        self._enter("playing", now, 0)
        for potato in self.potatoes:
            self._ask(potato, now)

    def _finish(self, now: float) -> None:
        alive = self.alive_ids()
        self.winner = alive[0] if alive else None
        self.potatoes = []
        self._enter("finished", now, 0)

    def _next_after(self, player_id: str, excluded: str | None) -> str:
        """O próximo vivo da roda depois de `player_id` (que pode já estar fora), no sentido atual,
        pulando `excluded` (quem jogou a Batata dupla)."""
        ids = [p.id for p in self.players]
        start = ids.index(player_id)
        for step in range(1, len(ids) + 1):
            candidate = self.players[(start + step * self.direction) % len(ids)]
            if candidate.alive and candidate.id != excluded:
                return candidate.id
        return player_id

    def _farthest(self, from_id: str, excluded: str) -> str:
        """Quem está mais longe de `from_id` na roda dos vivos (sem contar `excluded`)."""
        alive = self.alive_ids()
        here = alive.index(from_id)

        def distance(pid: str) -> int:
            d = abs(alive.index(pid) - here)
            return min(d, len(alive) - d)

        candidates = [pid for pid in alive if pid != excluded]
        far = max(distance(pid) for pid in candidates)
        return self.rng.choice([pid for pid in candidates if distance(pid) == far])

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

    # --- poderes ----------------------------------------------------------

    def _mine(self, player_id: str, potato_id: int | None) -> Potato:
        """A batata que o jogador tem na mão (com as duas, ele diz qual)."""
        mine = self.held_by(player_id)
        if potato_id is not None:
            mine = [p for p in mine if p.id == potato_id]
        if not mine:
            raise HotPotatoError("A batata não está com você.")
        if len(mine) > 1:
            raise HotPotatoError("Você está com as duas batatas: escolha uma.")
        return mine[0]

    def _target(self, player_id: str, potato_id: int | None) -> Potato:
        """A batata que a sabotagem mira (com duas na roda, quem joga escolhe)."""
        targets = [p for p in self.potatoes if potato_id is None or p.id == potato_id]
        if len(targets) > 1:
            raise HotPotatoError("Tem duas batatas na roda: escolha em qual.")
        if not targets:
            raise HotPotatoError("Essa batata não está na roda.")
        if targets[0].holder == player_id:
            raise HotPotatoError("Sabotagem é para quem está com a batata.")
        return targets[0]

    def _apply(self, potato: Potato, kind: PowerUp, now: float) -> None:
        if kind == "fifty_fifty":
            q = potato.question
            alive = [i for i in range(len(q.options)) if i != q.answer and i != potato.first_wrong]
            potato.hidden_options = sorted(self.rng.sample(alive, min(pw.FIFTY_FIFTY_REMOVES, len(alive))))
        elif kind == "shield":
            self.shields.add(potato.holder)
        elif kind == "second_chance":
            potato.second_chance = True
        elif kind == "cold_water":
            self._burn(potato, now)
            potato.fuse_left += COLD_WATER_SECONDS
        elif kind == "reverse":
            self.direction = -self.direction
        elif kind == "thermometer":
            potato.thermometer = True
        elif kind == "free_pass":
            self._burn(potato, now)
            potato.turn = HotPotatoTurn(
                player_id=potato.holder, option=None, correct=True, correct_option=potato.question.answer,
                elapsed_ms=round((now - potato.state_started_at) * 1000), free_pass=True,
            )
            self._set_state(potato, "passing", now, PASS_SECONDS)
        elif kind == "accelerator":
            self._burn(potato, now)
            potato.burn_rate = ACCELERATOR_RATE
        elif kind == "short_fuse":
            self._burn(potato, now)
            potato.fuse_left -= SHORT_FUSE_SECONDS
            if potato.fuse_left <= 0:
                self._explode(potato, now)
        elif kind == "double_bomb":
            potato.bomb = True
            potato.need_right = DOUBLE_BOMB_RIGHTS

    def _double(self, me: Holder, now: float) -> None:
        """Batata dupla: entra a dourada, com quem está mais longe da principal na roda."""
        if "double_potato" not in self.mythics.get(me.id, []):
            raise HotPotatoError("Você não tem essa habilidade.")
        if self.phase != "playing" or not me.alive:
            raise HotPotatoError("Agora não dá para usar a Batata dupla.")
        if self.golden:
            raise HotPotatoError("Já tem uma Batata dupla na roda.")
        if len(self.alive_ids()) < DOUBLE_POTATO_MIN_ALIVE:
            raise HotPotatoError(f"A Batata dupla precisa de pelo menos {DOUBLE_POTATO_MIN_ALIVE} na roda.")
        self.mythics[me.id].remove("double_potato")
        holder = self._farthest(self.main.holder, me.id)
        golden = self._new_potato(1, holder, GOLDEN_FUSE_SECONDS, golden=True, excluded=me.id)
        self.potatoes.append(golden)
        self._ask(golden, now)

    def _count_run(self, player_id: str) -> None:
        if not self.powers:
            return
        self.runs[player_id] = self.runs.get(player_id, 0) + 1
        if self.runs[player_id] >= pw.STREAK_FOR_POWERUP:
            self.runs[player_id] = 0
            if self.rng.random() < DOUBLE_POTATO_CHANCE and "double_potato" not in self.mythics.get(player_id, []):
                self._give(player_id, "double_potato", "streak", mythic=True)
            else:
                self._give(player_id, self.rng.choice(HELPS + SABOTAGES), "streak")

    def _haunt(self) -> None:
        """A cada explosão (menos a última), quem está vivo ganha um poder e os fantasmas de antes
        ganham uma sabotagem (às vezes, a Ressurreição)."""
        if len(self.alive_ids()) <= 1:
            return
        for p in self.players:
            if p.alive:
                self._give(p.id, self.rng.choice(HELPS + SABOTAGES), "elimination")
                continue
            if p.id == self.exploded:
                continue
            mythic = self.rng.random() < RESURRECTION_CHANCE and "resurrection" not in self.mythics.get(p.id, [])
            self._give(p.id, "resurrection" if mythic else self.rng.choice(GHOST_SABOTAGES), "ghost", mythic=mythic)

    def _give(self, player_id: str, kind: PowerUp, reason: str, mythic: bool = False) -> None:
        """Com as mãos cheias, não ganha nada (o mítico não ocupa vaga)."""
        hand = self.mythics.setdefault(player_id, []) if mythic else self.held.setdefault(player_id, [])
        if not mythic and len(hand) >= self.powerup_max:
            return
        hand.append(kind)
        self.gifts.append(Gift(player_id=player_id, gain=PowerUpGain(kind=kind, reason=reason, mythic=mythic)))

    def _resurrect(self, me: Holder) -> None:
        if "resurrection" not in self.mythics.get(me.id, []):
            raise HotPotatoError("Você não tem essa habilidade.")
        if me.alive:
            raise HotPotatoError("A Ressurreição é para quem explodiu.")
        self.mythics[me.id].remove("resurrection")
        me.out_round = None
        self.revived.append(me.id)

    # --- ranking e visão --------------------------------------------------

    def places(self) -> dict[str, int]:
        """O vencedor, depois quem saiu mais tarde."""

        def key(p: Holder) -> tuple:
            return (p.id != self.winner, -(p.out_round if p.out_round is not None else 10**6), -p.correct)

        return {p.id: i + 1 for i, p in enumerate(sorted(self.players, key=key))}

    def view(self, now: float, player_ids: list[str], viewer: str | None = None) -> HotPotatoView:
        places = self.places() if self.phase == "finished" else {}
        timed = self.phase in ("starting", "exploded")
        exploded = self.exploded_potato if self.phase == "exploded" else None
        return HotPotatoView(
            phase=self.phase,
            phase_duration_ms=round((self.phase_ends_at - self.phase_started_at) * 1000) if timed else 0,
            phase_ends_in_ms=max(0, round((self.phase_ends_at - now) * 1000)) if timed else 0,
            round=self.round,
            potatoes=[self._potato_view(p, now, viewer) for p in self.potatoes],
            max_wrong_streak=MAX_WRONG_STREAK,
            penalty_seconds=WRONG_PENALTY_SECONDS,
            fuse_range=list(FUSE_SECONDS),
            exploded=self.exploded,
            exploded_golden=bool(exploded) and exploded.golden,
            winner=self.winner,
            players=[
                HotPotatoPlayer(player_id=p.id, out_round=p.out_round, correct=p.correct, wrong=p.wrong, place=places.get(p.id))
                for p in self.players
                if p.id in player_ids
            ],
            direction=self.direction,
            powers=self.powers,
            powerups=list(self.held.get(viewer, [])) if viewer else [],
            mythic_powerups=list(self.mythics.get(viewer, [])) if viewer else [],
            powerup_max=self.powerup_max,
            starting_powerup=self.starting.get(viewer) if viewer else None,
            shielded=sorted(self.shields & set(self.alive_ids())),
            gifts=list(self.gifts),
            revived=list(self.revived),
        )

    def _potato_view(self, potato: Potato, now: float, viewer: str | None) -> PotatoView:
        q = potato.question if self.phase == "playing" else None
        fuse = self.fuse_at(potato, now)
        deadline = self.potato_deadline(potato)
        mine = viewer is not None and viewer == potato.holder
        return PotatoView(
            id=potato.id,
            golden=potato.golden,
            excluded=potato.excluded,
            holder=potato.holder,
            state=potato.state,
            state_duration_ms=round((deadline - potato.state_started_at) * 1000),
            state_ends_in_ms=max(0, round((deadline - now) * 1000)),
            # O pavio é segredo: vai só o quanto já queimou, para a batata chiar e tremer mais.
            heat=0.0 if not potato.fuse_total else round(min(1.0, max(0.0, 1 - fuse / potato.fuse_total)), 3),
            burning=self.burning(potato),
            burn_per_second=round(potato.burn_rate / potato.fuse_total, 4) if potato.fuse_total else 0.0,
            fuse_ms=round(fuse * 1000) if mine and potato.thermometer else None,
            wrong_streak=potato.wrong_streak,
            need_right=potato.need_right,
            text=q.text if q else None,
            theme=q.theme if q else None,
            difficulty=q.difficulty if q else None,
            options=q.options if q else [],
            turn=potato.turn,
            uses=list(potato.uses) if q else [],
            hidden_options=list(potato.hidden_options) if q else [],
            first_wrong=potato.first_wrong if q else None,
            flashbang=bool(q) and mine and any(u.kind == "flashbang" for u in potato.uses),
        )
