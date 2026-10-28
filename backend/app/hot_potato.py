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
"""

import random
from dataclasses import dataclass, field
from typing import Literal

from app import powerups as pw
from app.events import Gift, HotPotatoPlayer, HotPotatoTurn, HotPotatoView, PowerUp, PowerUpGain, PowerUpUse
from app.game import Question

START_SECONDS = 5.0
FUSE_SECONDS = (40.0, 60.0)
WRONG_PENALTY_SECONDS = 10.0
MAX_WRONG_STREAK = 3  # erros seguidos de quem está com a batata: explode na hora
PASS_SECONDS = 1.0  # a batata voando para o próximo (o pavio para)
WRONG_SECONDS = 1.2  # mostra o erro antes da próxima pergunta (o pavio para)
EXPLODED_SECONDS = 4.0
DIFFICULTIES = ("easy", "medium")

HELPS: tuple[PowerUp, ...] = ("fifty_fifty", "shield", "second_chance", "cold_water", "reverse", "free_pass")
SABOTAGES: tuple[PowerUp, ...] = ("accelerator", "scramble", "mirror", "magnifier", "flashbang")
COLD_WATER_SECONDS = 10.0
ACCELERATOR_RATE = 2.0  # o pavio queima 2x mais rápido até a próxima pergunta
RESURRECTION_CHANCE = 0.08

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
    powers: bool = False
    powerup_max: int = pw.MAX_HELD
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = 0
    holder: str | None = None
    direction: Literal[1, -1] = 1
    fuse_total: float = 0
    fuse_left: float = 0  # segundos de pavio em `burn_from`
    burn_from: float = 0  # desde quando o pavio queima no ritmo `burn_rate`
    burn_rate: float = 1.0
    wrong_streak: int = 0
    question: Question | None = None
    turn: HotPotatoTurn | None = None  # a última resposta, para a tela de passe ou erro
    exploded: str | None = None
    winner: str | None = None
    # Poderes.
    held: dict[str, list[PowerUp]] = field(default_factory=dict)
    mythics: dict[str, list[PowerUp]] = field(default_factory=dict)
    starting: dict[str, PowerUp] = field(default_factory=dict)
    uses: list[PowerUpUse] = field(default_factory=list)  # na pergunta atual
    hidden_options: list[int] = field(default_factory=list)
    first_wrong: int | None = None
    second_chance: bool = False  # vale na pergunta atual
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

    def player(self, player_id: str) -> Holder | None:
        return next((p for p in self.players if p.id == player_id), None)

    def alive_ids(self) -> list[str]:
        return [p.id for p in self.players if p.alive]

    def fuse_at(self, now: float) -> float:
        """Segundos de pavio que faltam agora."""
        if self.phase == "asking":
            return max(0.0, self.fuse_left - (now - self.burn_from) * self.burn_rate)
        return self.fuse_left

    def deadline(self) -> float:
        if self.phase == "asking":
            return self.burn_from + self.fuse_left / self.burn_rate
        return self.phase_ends_at

    # --- ações ------------------------------------------------------------

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase != "asking":
            raise HotPotatoError("Agora não dá para responder.")
        if player_id != self.holder:
            raise HotPotatoError("A batata não está com você.")
        if option not in range(len(self.question.options)) or option in self.hidden_options or option == self.first_wrong:
            raise HotPotatoError("Alternativa inválida.")
        if now >= self.deadline():
            return self._explode(now)
        holder = self.player(player_id)
        self._burn(now)
        correct = option == self.question.answer
        if not correct and self.second_chance and self.first_wrong is None:
            self.first_wrong = option  # tenta de novo, sem perder pavio
            self.second_chance = False
            return
        self.turn = HotPotatoTurn(
            player_id=player_id, option=option, correct=correct, correct_option=self.question.answer,
            elapsed_ms=round((now - self.phase_started_at) * 1000),
        )
        if correct:
            holder.correct += 1
            self.wrong_streak = 0
            self._count_run(player_id)
            self._enter("passing", now, PASS_SECONDS)
            return
        holder.wrong += 1
        self.runs[player_id] = 0
        if player_id in self.shields:
            self.shields.discard(player_id)
            self.turn.shielded = True
            return self._enter("wrong", now, WRONG_SECONDS)
        self.wrong_streak += 1
        self.fuse_left -= WRONG_PENALTY_SECONDS
        if self.wrong_streak >= MAX_WRONG_STREAK or self.fuse_left <= 0:
            return self._explode(now)
        self._enter("wrong", now, WRONG_SECONDS)

    def use(self, player_id: str, kind: PowerUp, now: float) -> None:
        """Ajuda em si mesmo (com a batata na mão) ou sabotagem em quem está com a batata."""
        if not self.powers or self.phase in ("starting", "finished"):
            raise HotPotatoError("Agora não dá para usar habilidade.")
        me = self.player(player_id)
        if not me:
            raise HotPotatoError("Você não está na partida.")
        if kind == "resurrection":
            return self._resurrect(me)
        if kind not in self.held.get(player_id, []):
            raise HotPotatoError("Você não tem essa habilidade.")
        if self.phase != "asking":
            raise HotPotatoError("Espere a próxima pergunta.")
        if now >= self.deadline():
            raise HotPotatoError("O pavio acabou.")
        if any(u.kind == kind for u in self.uses):
            raise HotPotatoError("Essa já foi usada nesta pergunta.")
        if kind in HELPS:
            if player_id != self.holder:
                raise HotPotatoError("Ajuda só com a batata na mão.")
            if kind == "shield" and player_id in self.shields:
                raise HotPotatoError("Seu Escudo já está armado.")
            if kind == "second_chance" and self.first_wrong is not None:
                raise HotPotatoError("Você já errou esta.")
            target = None
        else:
            if player_id == self.holder:
                raise HotPotatoError("Sabotagem é para quem está com a batata.")
            if any(u.by == player_id and u.kind in SABOTAGES for u in self.uses):
                raise HotPotatoError("Uma sabotagem por pergunta.")
            target = self.holder
        self.held[player_id].remove(kind)
        self.uses.append(PowerUpUse(kind=kind, by=player_id, target=target, reflected_by=None))
        self._apply(kind, now)

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

    def _burn(self, now: float) -> None:
        """Guarda o pavio que falta agora, para mudar o ritmo ou parar de queimar."""
        self.fuse_left = self.fuse_at(now)
        self.burn_from = now

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
        self.uses = []
        self.hidden_options = []
        self.first_wrong = None
        self.second_chance = False
        self.gifts = []
        self.revived = []
        self.burn_from, self.burn_rate = now, 1.0
        self._enter("asking", now, self.fuse_left)

    def _explode(self, now: float) -> None:
        self.fuse_left = 0
        self.exploded = self.holder
        self.player(self.holder).out_round = self.round
        self.gifts = []
        self._enter("exploded", now, EXPLODED_SECONDS)
        if self.powers:
            self._haunt()

    def _finish(self, now: float) -> None:
        alive = self.alive_ids()
        self.winner = alive[0] if alive else None
        self.holder = None
        self._enter("finished", now, 0)

    def _next_after(self, player_id: str) -> str:
        """O próximo vivo da roda depois de `player_id` (que pode já estar fora), no sentido atual."""
        ids = [p.id for p in self.players]
        start = ids.index(player_id)
        for step in range(1, len(ids) + 1):
            candidate = self.players[(start + step * self.direction) % len(ids)]
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

    # --- poderes ----------------------------------------------------------

    def _apply(self, kind: PowerUp, now: float) -> None:
        if kind == "fifty_fifty":
            q = self.question
            alive = [i for i in range(len(q.options)) if i != q.answer and i != self.first_wrong]
            self.hidden_options = sorted(self.rng.sample(alive, min(pw.FIFTY_FIFTY_REMOVES, len(alive))))
        elif kind == "shield":
            self.shields.add(self.holder)
        elif kind == "second_chance":
            self.second_chance = True
        elif kind == "cold_water":
            self._burn(now)
            self.fuse_left += COLD_WATER_SECONDS
        elif kind == "reverse":
            self.direction = -self.direction
        elif kind == "free_pass":
            self._burn(now)
            self.turn = HotPotatoTurn(
                player_id=self.holder, option=None, correct=True, correct_option=self.question.answer,
                elapsed_ms=round((now - self.phase_started_at) * 1000), free_pass=True,
            )
            self._enter("passing", now, PASS_SECONDS)
        elif kind == "accelerator":
            self._burn(now)
            self.burn_rate = ACCELERATOR_RATE

    def _count_run(self, player_id: str) -> None:
        if not self.powers:
            return
        self.runs[player_id] = self.runs.get(player_id, 0) + 1
        if self.runs[player_id] >= pw.STREAK_FOR_POWERUP:
            self.runs[player_id] = 0
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
            self._give(p.id, "resurrection" if mythic else self.rng.choice(SABOTAGES), "ghost", mythic=mythic)

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
        q = self.question if self.phase in ("asking", "passing", "wrong") else None
        places = self.places() if self.phase == "finished" else {}
        fuse = self.fuse_at(now)
        burning = self.phase == "asking"
        return HotPotatoView(
            phase=self.phase,
            phase_duration_ms=round((self.deadline() - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((self.deadline() - now) * 1000)),
            round=self.round,
            holder=self.holder,
            # O pavio é segredo: vai só o quanto já queimou, para a batata chiar e tremer mais.
            heat=0.0 if not self.fuse_total else round(min(1.0, max(0.0, 1 - fuse / self.fuse_total)), 3),
            burning=burning,
            burn_per_second=round(self.burn_rate / self.fuse_total, 4) if self.fuse_total else 0.0,
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
            direction=self.direction,
            powers=self.powers,
            powerups=list(self.held.get(viewer, [])) if viewer else [],
            mythic_powerups=list(self.mythics.get(viewer, [])) if viewer else [],
            powerup_max=self.powerup_max,
            starting_powerup=self.starting.get(viewer) if viewer else None,
            uses=list(self.uses) if q else [],
            hidden_options=list(self.hidden_options) if q else [],
            first_wrong=self.first_wrong if q else None,
            shielded=sorted(self.shields & set(self.alive_ids())),
            flashbang=bool(q) and viewer == self.holder and any(u.kind == "flashbang" for u in self.uses),
            gifts=list(self.gifts),
            revived=list(self.revived),
        )
