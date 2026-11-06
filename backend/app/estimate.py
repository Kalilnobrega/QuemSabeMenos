"""Chutômetro: perguntas de número. Cada um digita um chute; quanto mais perto da resposta, mais QI.

O erro é medido em % da resposta (ou da `scale` da pergunta, para anos e números pequenos, em que
a porcentagem da resposta não faz sentido). Os níveis seguem o clássico: fáceis, médias e difíceis,
na mesma divisão. Sem aposta nem final impossível.
Fases: starting → (answering → results) por pergunta, com level quando o nível muda → finished.
Não tem tempo de leitura: a pergunta já abre para chutar, e os 20 segundos já incluem ler.

Com poderes: os comuns do clássico que fazem sentido com número (ver `POWERS`), armados na revelação
para a próxima pergunta. "Acertar" é ganhar QI com o chute. A Segunda chance diz se a resposta é mais
alta ou mais baixa antes do novo chute.

Poderes só deste modo: Faixa e Sniper (na hora), Margem larga, Tecla quente, Cópia, Empurrão e
Troca-troca valem aqui. Tecla quebrada, Teclado mentiroso, Perfeccionista, Teclas fugitivas, Curto-circuito e Duplo
clique só existem como sabotagem armada: o teclado é do navegador.
"""

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from app import powerups as pw
from app.engine import Revealed, RoomError
from app.events import (
    EstimateGuess,
    EstimateLastWord,
    EstimateMath,
    EstimateRange,
    EstimateScoring,
    EstimateView,
    LastingPowerUp,
    LastWordGuess,
    MathKey,
    MathWatch,
    PowerUp,
    PowerUpGain,
    PowerUpUse,
)
from app.game import (
    LATE_SECONDS,
    LEVEL_SECONDS,
    START_SECONDS,
    legendary_steal_shares,
    results_seconds,
    split_by_difficulty,
    steal_share,
)
from app.game import point_scale as scale_for

ESTIMATES_DIR = Path(__file__).parent / "estimates"
ROUND_OPTIONS = (10, 15, 20)
ANSWER_SECONDS = 20.0
MATH_SECONDS = 30.0  # o alvo da Matemática tem mais tempo, e os outros assistem às contas
MAX_LOSS_FACTOR = 3  # a perda chega ao máximo no triplo do erro em que o ganho zera
# Sem 50/50, Alternativa falsa e Pedágio, que dependem de alternativas, e sem Tempo extra: a velocidade não dá QI.
# Investimento, Embaralhar, Lupa, Acelerador, Flashbang e Espiar também ficaram de fora, por escolha de jogo.
POWERS: tuple[PowerUp, ...] = (
    "shield",
    "double",
    "copy",
    "second_chance",
    "reverse",
    "backpack",
    "theme",
    "scratch",
    "steal",
    "mirror",
    "silence",
    "range",
    "wide_margin",
    "hot_keys",
    "broken_keys",
    "shuffled_keys",
    "perfectionist",
    "nudge",
    "sniper",
    "swap",
    "runaway_keys",
    "short_circuit",
    "double_click",
)
# Míticos: só chegam por sorteio, nunca como poder comum nem lendário.
MYTHICS: tuple[PowerUp, ...] = ("math", "last_word")
MYTHIC_CHANCE = (0.02, 0.08)  # (para quem não é lanterna, para o lanterna)
LAST_WORD_SECONDS = 10.0  # o tempo de quem fala por último, depois de ver os chutes
LAST_WORD_STAKE = 10  # o QI da aposta com cada um dos outros
LAST_WORD_MAX_STAKE = 40  # em sala grande a aposta se divide, para não decidir a partida sozinha
MATH_KEYS = 9
MATH_MAX_VALUE = 1e12  # acima disso o visor não cabe
MATH_MAX_USES = 3
MATH_MULTIPLIERS = (2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 50, 100, 1000)
TARGETED: frozenset[PowerUp] = pw.TARGETED | {
    "math",
    "broken_keys",
    "shuffled_keys",
    "perfectionist",
    "nudge",
    "swap",
    "runaway_keys",
    "short_circuit",
    "double_click",
}
INSTANT: frozenset[PowerUp] = pw.INSTANT | {"range", "sniper", "last_word"}
# As sabotagens em versão lendária, menos a Troca-troca, que só existe entre duas pessoas.
LEGENDARY: tuple[PowerUp, ...] = tuple(kind for kind in POWERS if kind in TARGETED and kind != "swap")
SNIPER_FACTOR = 2  # a zona de ganho fica desse tanto menor, e o ganho desse tanto maior
EXACT_POWER_LEVELS = ("medium", "hard")  # cravar nesses níveis dá um poder
WIDE_MARGIN_FACTOR = 2  # a zona de ganho (e a de perda) fica desse tamanho
NUDGE_SHARE = (0.1, 0.3)  # o Empurrão anda uma fração sorteada da base do erro, para um lado sorteado
RANGE_OFF_CENTER = (0.15, 0.4)  # a Faixa tem a resposta a essa fração de uma das pontas


@dataclass(frozen=True)
class Scoring:
    """Pontos contínuos, em linha reta: o ganho cai de `max_points` (erro quase zero) até 0 em
    `break_even` % de erro; daí em diante perde, até `max_loss` no triplo desse erro (e não passa
    disso). Cravar soma `exact_bonus`. Sem chute, perde o máximo."""

    max_points: int
    exact_bonus: int
    break_even: float
    max_loss: int

    @property
    def max_loss_at(self) -> float:
        return self.break_even * MAX_LOSS_FACTOR


# Como no clássico: a fácil é obrigação (ganha pouco, perde muito) e a difícil vale o risco.
SCORING: dict[str, Scoring] = {
    "easy": Scoring(max_points=8, exact_bonus=4, break_even=20, max_loss=-20),
    "medium": Scoring(max_points=16, exact_bonus=8, break_even=30, max_loss=-15),
    "hard": Scoring(max_points=24, exact_bonus=12, break_even=35, max_loss=-10),
}

Phase = Literal["starting", "level", "answering", "results", "finished"]


class EstimateError(RoomError):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


class EstimateQuestion(BaseModel):
    id: str
    theme: str
    difficulty: Literal["easy", "medium", "hard"]
    text: str
    answer: float
    unit: str | None = None  # aparece do lado do campo do chute ("km", "anos")
    scale: float | None = Field(default=None, gt=0)  # base do erro em %; sem ela, a própria resposta
    fact: str = Field(min_length=1)


class EstimateFile(BaseModel):
    theme: str
    questions: list[dict]


def load_estimates(directory: Path = ESTIMATES_DIR) -> list[EstimateQuestion]:
    """Lê estimates/<tema>.json. O id de cada pergunta é chute-<arquivo>-<posição>."""
    bank = []
    for path in sorted(directory.glob("*.json")):
        data = EstimateFile.model_validate(json.loads(path.read_text()))
        for i, raw in enumerate(data.questions, start=1):
            bank.append(EstimateQuestion(id=f"chute-{path.stem}-{i}", theme=data.theme, **raw))
    return bank


def error_base(question: EstimateQuestion) -> float:
    """O valor que vale 100% de erro."""
    return question.scale or abs(question.answer) or 1


def error_percent(question: EstimateQuestion, value: float) -> float:
    return abs(value - question.answer) / error_base(question) * 100


def answer_digits(answer: float) -> list[str]:
    """Os algarismos diferentes da resposta, como ela aparece escrita: 1500 tem 0, 1 e 5."""
    written = f"{abs(answer):.3f}".rstrip("0").rstrip(".")
    return sorted(set(written) - {"."})


def apply_math(value: float, key: MathKey) -> float:
    """A conta de uma tecla, como o navegador faz: 3 casas no máximo."""
    match key.op:
        case "add":
            result = value + key.value
        case "sub":
            result = value - key.value
        case "mul":
            result = value * key.value
        case "div":
            result = value / key.value
        case "square":
            result = value**2
        case "sqrt":
            result = math.sqrt(value)
    return round(result, 3)


def _two_digits(value: float) -> float:
    """Dois algarismos significativos, para a tecla ficar legível."""
    return float(f"{value:.2g}")


def math_path(start: float, answer: float) -> list[MathKey]:
    """Um caminho de contas do número inicial até perto da resposta: multiplica ou divide até a mesma
    escala e acerta o resto somando ou subtraindo. Quem achar outro caminho também vale."""
    path: list[MathKey] = []
    value = start
    size = abs(answer)
    while size and (abs(value) * 2 <= size or abs(value) >= size * 2):
        growing = abs(value) * 2 <= size
        room = size / abs(value) if growing else abs(value) / size
        factor = max(n for n in MATH_MULTIPLIERS if n <= room)
        step = MathKey(op="mul" if growing else "div", value=factor, uses=1)
        path.append(step)
        value = apply_math(value, step)
    rest = _two_digits(abs(answer - value))
    if rest:
        path.append(MathKey(op="add" if answer > value else "sub", value=rest, uses=1))
    return path


def _math_decoy(size: float, rng: random.Random) -> MathKey:
    """Uma tecla de despiste, na escala da resposta ou menor: as contas certas não saltam aos olhos."""
    kind = rng.choice(("add", "sub", "mul", "div", "square", "sqrt"))
    if kind in ("square", "sqrt"):
        return MathKey(op=kind, value=None, uses=1)
    if kind in ("mul", "div"):
        return MathKey(op=kind, value=rng.choice(MATH_MULTIPLIERS), uses=1)
    largest = max(0, math.floor(math.log10(size))) if size else 0
    return MathKey(op=kind, value=rng.randint(1, 9) * 10 ** rng.randint(0, largest), uses=1)


def draw_math(answer: float, rng: random.Random) -> EstimateMath:
    """O número inicial e as teclas, embaralhadas: o caminho e os despistes, com 1 a 3 usos cada."""
    start = rng.randint(2, 40)
    uses: dict[tuple[str, float | None], int] = {}
    for key in math_path(start, answer):
        uses[(key.op, key.value)] = uses.get((key.op, key.value), 0) + 1
    while len(uses) < MATH_KEYS:
        decoy = _math_decoy(abs(answer), rng)
        uses.setdefault((decoy.op, decoy.value), 0)
    keys = [
        # O caminho pode usar a mesma tecla mais de uma vez: ela nunca tem menos usos do que ele precisa.
        MathKey(op=op, value=value, uses=max(needed, rng.randint(1, MATH_MAX_USES)))
        for (op, value), needed in uses.items()
    ]
    rng.shuffle(keys)
    return EstimateMath(start=start, keys=keys, value=start)


def draw_range(question: EstimateQuestion, rng: random.Random) -> EstimateRange:
    """Tão larga quanto a zona de ganho, com pontas redondas e a resposta sempre fora do meio."""
    width = error_base(question) * SCORING[question.difficulty].break_even * 2 / 100
    below = rng.uniform(*RANGE_OFF_CENTER) * width
    if rng.random() < 0.5:
        below = width - below
    step = 10 ** math.floor(math.log10(width / 4))
    low = math.floor((question.answer - below) / step) * step
    high = math.ceil((question.answer - below + width) / step) * step
    if question.answer >= 0:
        low = max(0, low)
    return EstimateRange(low=round(low, 6), high=round(high, 6))


def guess_points(error: float | None, difficulty: str = "medium", scale: float = 1.0) -> int:
    """`scale`: como no clássico, partidas curtas valem mais por pergunta (20/N)."""
    rules = SCORING[difficulty]
    if error is None:
        points = rules.max_loss
    elif error == 0:
        points = rules.max_points + rules.exact_bonus
    elif error <= rules.break_even:
        points = rules.max_points * (1 - error / rules.break_even)
    else:
        beyond = (error - rules.break_even) / (rules.max_loss_at - rules.break_even)
        points = rules.max_loss * min(1.0, beyond)
    return _round(points * scale)


def _round(value: float) -> int:
    """Meio ponto arredonda para longe do zero (2,5 → 3 e −2,5 → −3), sem o arredondamento do banqueiro."""
    return int(math.copysign(math.floor(abs(value) + 0.5), value))


class Scorable(Protocol):
    id: str
    score: int
    answer_ms: int


@dataclass
class Estimate(Revealed):
    rule_error = EstimateError

    questions: list[EstimateQuestion]
    point_scale: float = 1.0  # 20/N, como no clássico
    phase: Phase = "starting"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    round: int = -1  # índice da pergunta atual
    guesses: dict[str, tuple[float, float]] = field(default_factory=dict)  # chute e quando
    results: list[EstimateGuess] = field(default_factory=list)
    ready: set[str] = field(default_factory=set)
    first_guesses: dict[str, tuple[float, float]] = field(default_factory=dict)  # Segunda chance: o chute que errou
    # Poderes (ver powerups.py para o que cada um faz no clássico).
    powers: bool = False
    powerup_max: int = pw.MAX_HELD
    rng: random.Random = field(default_factory=random.Random)
    bank: list[EstimateQuestion] = field(default_factory=list)  # para o Tema trocar a próxima pergunta
    used: set[str] = field(default_factory=set)
    held: dict[str, list[PowerUp]] = field(default_factory=dict)
    legendaries: dict[str, list[PowerUp]] = field(default_factory=dict)
    mythics: dict[str, list[PowerUp]] = field(default_factory=dict)
    math_puzzles: dict[str, EstimateMath] = field(default_factory=dict)  # Matemática: de quem foi atingido
    last_word_by: str | None = None  # Palavra final: quem fala por último nesta pergunta
    last_word_opened_at: float | None = None  # quando todos terminaram e chegou a vez dele
    last_word_draft: str = ""
    starting: dict[str, PowerUp] = field(default_factory=dict)
    extra_slots: dict[str, int] = field(default_factory=dict)
    armed: dict[str, PowerUpUse] = field(default_factory=dict)
    active: list[PowerUpUse] = field(default_factory=list)
    lasting: dict[str, dict[PowerUp, int]] = field(default_factory=dict)  # perguntas que faltam, contando a atual
    lasting_total: dict[str, dict[PowerUp, int]] = field(default_factory=dict)
    used_lasting: dict[str, set[PowerUp]] = field(default_factory=dict)  # as que já valeram: não quebram
    silences: list[tuple[PowerUpUse, int]] = field(default_factory=list)
    right_runs: dict[str, int] = field(default_factory=dict)
    last_runs: dict[str, int] = field(default_factory=dict)
    leaders: set[str] = field(default_factory=set)  # o Reverso de quem está em 1º dura menos
    theme_choices: list[str] = field(default_factory=list)
    ranges: dict[str, EstimateRange] = field(default_factory=dict)  # Faixa: de quem usou nesta pergunta

    @classmethod
    def create(
        cls,
        pool: list[EstimateQuestion],
        rounds: int,
        used: set[str],
        rng: random.Random,
        now: float,
        player_ids: list[str] | None = None,
        powers: bool = False,
        powerup_max: int = pw.MAX_HELD,
    ) -> "Estimate":
        """Sorteia as perguntas das fáceis às difíceis, como no clássico, preferindo as que a sala ainda não viu."""
        questions = []
        for difficulty, count in split_by_difficulty(rounds).items():
            fresh = [q for q in pool if q.difficulty == difficulty and q.id not in used]
            stale = [q for q in pool if q.difficulty == difficulty and q.id in used]
            rng.shuffle(fresh)
            rng.shuffle(stale)
            questions += (fresh + stale)[:count]
        game = cls(
            questions=questions,
            point_scale=scale_for(rounds),
            powers=powers,
            powerup_max=powerup_max,
            rng=rng,
            bank=pool,
            used=used,
        )
        used |= {q.id for q in game.questions}
        if powers:
            for pid in player_ids or []:
                game.starting[pid] = rng.choice(POWERS)
                game.held[pid] = [game.starting[pid]]
        game._enter("starting", now, START_SECONDS)
        return game

    @property
    def question(self) -> EstimateQuestion:
        return self.questions[self.round]

    def guess(self, player_id: str, value: float, now: float) -> None:
        if self.phase != "answering":
            raise EstimateError("Agora não dá para chutar.")
        if player_id in self.guesses:
            raise EstimateError("Você já chutou.")
        if player_id == self.last_word_by and self.last_word_opened_at is None:
            raise EstimateError("Espere os outros: a palavra final é sua.")
        limit = (
            self.phase_ends_at
            if player_id == self.last_word_by
            else self.phase_started_at + self.answer_window(player_id)
        )
        if now > limit + LATE_SECONDS:
            raise EstimateError("O tempo acabou.")
        guessed = (value, min(now, limit))
        q = self.question
        lost = guess_points(self._scored_error(player_id, error_percent(q, value)), q.difficulty, self.point_scale) <= 0
        if lost and player_id not in self.first_guesses and self._affects("second_chance", player_id):
            self.first_guesses[player_id] = guessed
            self.used_lasting.setdefault(player_id, set()).add("second_chance")
            return
        self.guesses[player_id] = guessed

    def answer_window(self, player_id: str) -> float:
        """Segundos que o jogador tem para chutar: o alvo da Matemática tem mais."""
        return MATH_SECONDS if player_id in self.math_puzzles else ANSWER_SECONDS

    def time_is_up(self, player_id: str, now: float) -> bool:
        """Sem tempo, mas a pergunta continua: esperando o alvo da Matemática ou a Palavra final."""
        if player_id == self.last_word_by:
            return False  # o prazo dele só começa quando todos terminam
        return (
            self.phase == "answering"
            and player_id not in self.guesses
            and now > self.phase_started_at + self.answer_window(player_id) + LATE_SECONDS
        )

    def others_time_up_at(self) -> float | None:
        """Quando acaba o tempo de quem não é alvo, se a pergunta segue depois disso para esperar um alvo."""
        if self.phase != "answering" or self.last_word_opened_at is not None:
            return None
        if not self.math_puzzles and not self.last_word_by:
            return None
        return self.phase_started_at + ANSWER_SECONDS + LATE_SECONDS

    def math_steps(self, player_id: str, steps: list[int]) -> None:
        """Matemática: refaz as contas no servidor, para quem assiste e para valer se o tempo acabar."""
        puzzle = self.math_puzzles.get(player_id)
        if self.phase != "answering" or not puzzle or player_id in self.guesses:
            raise EstimateError("Agora não dá para fazer contas.")
        value = puzzle.start
        for index in steps:
            if not 0 <= index < len(puzzle.keys):
                raise EstimateError("Essa tecla não existe.")
            key = puzzle.keys[index]
            if steps.count(index) > key.uses:
                raise EstimateError("Essa tecla já acabou.")
            if key.op == "sqrt" and value < 0:
                raise EstimateError("Não dá para tirar a raiz desse número.")
            value = apply_math(value, key)
            if abs(value) > MATH_MAX_VALUE:
                raise EstimateError("Esse número não cabe no visor.")
        self.math_puzzles[player_id] = puzzle.model_copy(update={"steps": steps, "value": value})

    def everyone_answered(self, connected: list[str], now: float | None = None) -> bool:
        """Quem ficou sem tempo não segura a pergunta. Quem tem a Palavra final só conta depois de abrir."""
        waiting_last_word = self.last_word_by if self.last_word_opened_at is None else None
        return all(
            pid == waiting_last_word or pid in self.guesses or (now is not None and self.time_is_up(pid, now))
            for pid in connected
        )

    def open_last_word(self, now: float, connected: list[str]) -> bool:
        """Todos terminaram: é a vez de quem tem a Palavra final, que precisa estar na sala."""
        pid = self.last_word_by
        if self.phase != "answering" or not pid or self.last_word_opened_at is not None:
            return False
        if pid not in connected or pid in self.guesses:
            return False
        self.last_word_opened_at = now
        self.phase_ends_at = now + LAST_WORD_SECONDS
        return True

    def last_word_typing(self, player_id: str, draft: str) -> None:
        """Palavra final: a sala assiste ao que está sendo digitado."""
        if player_id != self.last_word_by or self.last_word_opened_at is None or self.phase != "answering":
            raise EstimateError("Agora não é a sua palavra final.")
        self.last_word_draft = draft

    def everyone_ready(self, connected: list[str]) -> bool:
        """Quem está silenciado não vê a revelação: não precisa tocar em Pular."""
        return all(pid in self.ready or self.is_silenced(pid) for pid in connected)

    # --- poderes ----------------------------------------------------------

    @property
    def powers_round(self) -> bool:
        return self.powers and self.phase not in ("starting", "finished")

    @property
    def has_next_round(self) -> bool:
        return self.round + 1 < len(self.questions)

    @property
    def can_arm(self) -> bool:
        return self.powers and self.phase == "results" and self.has_next_round

    def capacity(self, player_id: str) -> int:
        return self.powerup_max + self.extra_slots.get(player_id, 0)

    def silence_left(self, player_id: str) -> int:
        if not self.powers_round:
            return 0
        return max((left for use, left in self.silences if self._hit_by(use, player_id)), default=0)

    def is_silenced(self, player_id: str) -> bool:
        return self.silence_left(player_id) > 0

    def _affects(self, kind: PowerUp, player_id: str) -> bool:
        if not self.powers_round:
            return False
        if kind == "silence":
            return self.is_silenced(player_id)
        if kind in pw.LASTING:
            return self.lasting.get(player_id, {}).get(kind, 0) > 0
        return any(
            use.kind == kind
            and (self._hit_by(use, player_id) if use.legendary else (use.target or use.by) == player_id)
            for use in self.active
        )

    @staticmethod
    def _hit_by(use: PowerUpUse, player_id: str) -> bool:
        """A sabotagem lendária não tem alvo: pega todos menos quem jogou."""
        return use.by != player_id if use.legendary else use.target == player_id

    def arm(
        self,
        player_id: str,
        kind: PowerUp,
        target: str | None,
        player_ids: list[str],
        theme: str | None,
        legendary: bool = False,
    ) -> None:
        if kind == "backpack" and not legendary:
            return self._open_backpack(player_id)
        if not self.can_arm:
            raise EstimateError("Agora não dá para usar poder.")
        if self.is_silenced(player_id):
            raise EstimateError("Silenciado: sem poderes por enquanto.")
        if player_id in self.armed:
            raise EstimateError("Você já armou um poder para a próxima pergunta.")
        if legendary:
            held = self.legendaries.get(player_id, [])
            if kind not in held:
                raise EstimateError("Você não tem esse poder.")
            held.remove(kind)
            self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=None, reflected_by=None, legendary=True)
            return
        held = self.mythics.get(player_id, []) if kind == "math" else self.held.get(player_id, [])
        if kind not in held:
            raise EstimateError("Você não tem esse poder.")
        if kind in INSTANT:
            raise EstimateError("Essa se usa na hora da pergunta.")
        if kind in TARGETED:
            if target is None or target == player_id or target not in player_ids:
                raise EstimateError("Escolha em quem usar.")
        else:
            target = None
        if kind == "theme":
            if theme not in self.theme_choices:
                raise EstimateError("Escolha um dos temas.")
            if any(use.kind == "theme" for use in self.armed.values()):
                raise EstimateError("Alguém já escolheu o tema da próxima pergunta.")
            self._swap_next_question(theme)
        else:
            theme = None
        held.remove(kind)
        self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=target, reflected_by=None, theme=theme)

    def disarm(self, player_id: str) -> None:
        """Trocar: o poder armado volta para a mão. O Tema não volta, porque a próxima já foi trocada."""
        use = self.armed.get(player_id)
        if not use or not self.can_arm:
            raise EstimateError("Não tem poder para trocar agora.")
        if use.kind == "theme":
            raise EstimateError("O tema da próxima já foi trocado: não dá para voltar.")
        del self.armed[player_id]
        hands = self.mythics if use.kind == "math" else self.legendaries if use.legendary else self.held
        hands.setdefault(player_id, []).append(use.kind)
        self.ready.discard(player_id)

    def use_now(self, player_id: str, kind: PowerUp) -> None:
        """Faixa, Sniper e Palavra final: durante a pergunta, valem na hora."""
        if self.phase != "answering" or not self.powers:
            raise EstimateError("Agora não dá para usar poder.")
        if kind not in INSTANT:
            raise EstimateError("Essa se arma na revelação.")
        if self.is_silenced(player_id):
            raise EstimateError("Silenciado: sem poderes por enquanto.")
        held = (self.mythics if kind in MYTHICS else self.held).get(player_id, [])
        if kind not in held:
            raise EstimateError("Você não tem esse poder.")
        if player_id in self.guesses or player_id in self.first_guesses:
            raise EstimateError("Você já chutou.")
        if self._affects(kind, player_id):
            raise EstimateError("Já está valendo.")
        if kind == "last_word":
            if self.last_word_by:
                raise EstimateError("Alguém já tem a palavra final desta pergunta.")
            if player_id in self.math_puzzles:
                raise EstimateError("Com a Matemática não dá: faça as contas.")
            self.last_word_by = player_id
        held.remove(kind)
        if kind == "range":
            self.ranges[player_id] = draw_range(self.question, self.rng)
        self.active.append(PowerUpUse(kind=kind, by=player_id, target=None, reflected_by=None))

    def _open_backpack(self, player_id: str) -> None:
        """Mochila: vale na hora, sem ocupar a vez de armar. Uma vaga a mais e um poder comum."""
        if not self.powers or self.phase != "results":
            raise EstimateError("Agora não dá para usar poder.")
        if self.is_silenced(player_id):
            raise EstimateError("Silenciado: sem poderes por enquanto.")
        held = self.held.get(player_id, [])
        if "backpack" not in held:
            raise EstimateError("Você não tem esse poder.")
        if self.extra_slots.get(player_id, 0) >= pw.BACKPACK_MAX_EXTRA:
            raise EstimateError("Sua Mochila já está no tamanho máximo.")
        held.remove("backpack")
        self.extra_slots[player_id] = self.extra_slots.get(player_id, 0) + 1
        held.append(self.rng.choice([kind for kind in POWERS if kind != "backpack"]))

    def _swap_next_question(self, theme: str) -> None:
        upcoming = self.round + 1
        current = self.questions[upcoming]
        if current.theme == theme:
            return
        pool = [
            q for q in self.bank if q.theme == theme and q.difficulty == current.difficulty and q.id not in self.used
        ]
        if not pool:
            raise EstimateError("Acabaram as perguntas desse tema.")
        question = self.rng.choice(pool)
        self.used.add(question.id)
        self.questions[upcoming] = question

    def _draw_theme_choices(self) -> list[str]:
        if not self.powers or not self.has_next_round:
            return []
        upcoming = self.questions[self.round + 1]
        themes = sorted(
            {q.theme for q in self.bank if q.difficulty == upcoming.difficulty and q.id not in self.used}
            | {upcoming.theme}
        )
        return sorted(self.rng.sample(themes, min(pw.THEME_CHOICES, len(themes))))

    def _start_powers(self) -> None:
        """Começo de uma pergunta: o que foi armado passa a valer (o Reverso devolve)."""
        self.silences = [(use, left - 1) for use, left in self.silences if left > 1]
        self.theme_choices = []
        armed = list(self.armed.values())
        self.armed = {}
        for use in armed:
            if use.kind in pw.LASTING:
                rounds = pw.LASTING[use.kind]
                if use.kind == "reverse" and use.by in self.leaders:
                    rounds = pw.REVERSE_LEADER_ROUNDS
                self.lasting.setdefault(use.by, {})[use.kind] = rounds
                self.lasting_total.setdefault(use.by, {})[use.kind] = rounds
                self.used_lasting.get(use.by, set()).discard(use.kind)
        reversers = {pid for pid in self.lasting if self._affects("reverse", pid)}
        self.active = pw.reflect(armed, reversers, TARGETED - {"math"})
        for use in self.active:
            if use.reflected_by:
                self.lasting[use.reflected_by].pop("reverse", None)
            if use.kind == "silence":
                self.silences.append((use, pw.SILENCE_ROUNDS))
            if use.kind == "math":
                self.math_puzzles[use.target] = draw_math(self.question.answer, self.rng)

    def _settle_steals(self, players: list[Scorable]) -> None:
        """Depois dos pontos de cada chute: o Roubo depende do resultado, e o lendário, do placar antes dele."""
        score_before = {p.id: p.score for p in players}
        by_id = {g.player_id: g for g in self.results}
        for use in self.active:
            thief = by_id.get(use.by)
            if use.kind != "steal" or not thief:
                continue
            if use.legendary:
                shares = legendary_steal_shares([g for g in self.results if g is not thief], score_before)
            else:
                target = by_id.get(use.target)
                shares = [(target, steal_share(target))] if target else []
            for target, share in shares:
                if target.shielded:
                    continue
                thief.stolen += share
                target.robbed += share

    def _settle_last_word(self) -> None:
        """O tudo ou nada: mais perto que todos (empate vale), tira QI de cada um; senão, paga a cada um."""
        speaker = next((g for g in self.results if g.player_id == self.last_word_by), None)
        others = [g for g in self.results if g is not speaker]
        if not speaker or not others:
            return
        stake = min(LAST_WORD_STAKE, LAST_WORD_MAX_STAKE // len(others))
        # Quem copiou fica de fora: a aposta é contra quem chutou por conta própria.
        errors = [g.error_percent for g in others if g.error_percent is not None and not g.copied_from]
        won = (
            speaker.error_percent is not None
            and not speaker.copied_from
            and all(speaker.error_percent <= error for error in errors)
        )
        for other in others:
            if won and other.shielded:
                continue  # o Escudo segura, como no Roubo
            other.last_word = -stake if won else stake
            speaker.last_word += stake if won else -stake

    def _scored_error(self, player_id: str, error: float) -> float:
        """O erro que vale para os pontos: mudar o tamanho das zonas é o mesmo que mudar o erro."""
        return error * self._zone_shrink(player_id)

    def _zone_shrink(self, player_id: str | None) -> float:
        """Margem larga e Sniper mexem nas zonas de quem usou, e juntos se cancelam."""
        if player_id is None:
            return 1
        wide = 1 / WIDE_MARGIN_FACTOR if self._affects("wide_margin", player_id) else 1
        return wide * (SNIPER_FACTOR if self._affects("sniper", player_id) else 1)

    def _swap_guesses(self, players: list[Scorable]) -> tuple[dict[str, tuple[float, float]], dict[str, float]]:
        """Os chutes que valem, com a Troca-troca: só o número troca, e só se os dois chutaram.
        Devolvida pelo Reverso, ela fica sem efeito. Também diz o chute original de quem trocou."""
        guesses = {}
        for player in players:
            guessed = self.guesses.get(player.id) or self.first_guesses.get(player.id)
            puzzle = self.math_puzzles.get(player.id)
            if not guessed and puzzle:  # o tempo acabou: vale o que está no visor
                guessed = (puzzle.value, self.phase_started_at + MATH_SECONDS)
            if guessed:
                guesses[player.id] = guessed
        originals: dict[str, float] = {}
        for use in self.active:
            mine, theirs = guesses.get(use.by), guesses.get(use.target)
            if use.kind != "swap" or use.by == use.target or not mine or not theirs:
                continue
            originals.setdefault(use.by, mine[0])
            originals.setdefault(use.target, theirs[0])
            guesses[use.by], guesses[use.target] = (theirs[0], mine[1]), (mine[0], theirs[1])
        return guesses, originals

    def _apply_nudges(self, guesses: dict[str, tuple[float, float]], player_ids: list[str]) -> dict[str, float]:
        """Empurra os chutes e devolve o valor de antes, de quem andou."""
        before = {}
        for pid in player_ids:
            if pid in guesses and (shift := self._nudge(pid)):
                before[pid] = guesses[pid][0]
                guesses[pid] = (round(guesses[pid][0] + shift, 3), guesses[pid][1])
        return before

    def _apply_copies(
        self, guesses: dict[str, tuple[float, float]], copiers: list[str]
    ) -> dict[str, tuple[str, float]]:
        """Cópia: fica com o melhor chute de quem não copiou, se for melhor que o próprio. Quem não
        chutou não copia. Devolve de quem veio o chute e o que o jogador tinha chutado."""
        copied = {}
        rivals = {pid: guess for pid, guess in guesses.items() if pid not in copiers}
        if not rivals:
            return copied
        distance = lambda guess: abs(guess[0] - self.question.answer)
        best = min(rivals, key=lambda pid: distance(rivals[pid]))
        for pid in copiers:
            own = guesses.get(pid)
            if own and distance(rivals[best]) < distance(own):
                copied[pid] = (best, own[0])
                guesses[pid] = (rivals[best][0], own[1])
        return copied

    def _nudge(self, player_id: str) -> float:
        """Quanto os Empurrões em cima do jogador mexem no chute."""
        return sum(
            # Dois algarismos significativos: o chute não vira um número cheio de casas na régua.
            float(f"{self.rng.choice((-1, 1)) * error_base(self.question) * self.rng.uniform(*NUDGE_SHARE):.2g}")
            for use in self.active
            if use.kind == "nudge" and self._hit_by(use, player_id)
        )

    def _wear_lasting(self) -> None:
        """O Escudo que segurou acaba, e todas as que duram gastam uma pergunta. As que chegam ao fim sem uso quebram."""
        by_id = {g.player_id: g for g in self.results}
        for pid, kinds in self.lasting.items():
            result = by_id.get(pid)
            if result and result.shielded:
                kinds.pop("shield", None)
            for kind in list(kinds):
                kinds[kind] -= 1
                if kinds[kind] <= 0:
                    del kinds[kind]
                    if kind in pw.BREAKABLE and kind not in self.used_lasting.get(pid, set()) and result:
                        result.expired.append(kind)

    def _gains(self, players: list[Scorable], earned: set[str], exact_guesses: set[str]) -> None:
        """Um poder por cravada nas médias e difíceis, a cada 3 chutes seguidos que ganham QI, ou a cada
        3 rodadas muito atrás. No máximo um por pergunta: a sequência que sobrar vale na próxima."""
        exact_pays = self.question.difficulty in EXACT_POWER_LEVELS
        behind = pw.trailing(players)
        by_id = {g.player_id: g for g in self.results}
        for player in players:
            right = self.right_runs[player.id] = self.right_runs.get(player.id, 0) + 1 if player.id in earned else 0
            last = self.last_runs[player.id] = self.last_runs.get(player.id, 0) + 1 if player.id in behind else 0
            if exact_pays and player.id in exact_guesses:
                reason = "exact"
            elif right >= pw.STREAK_FOR_POWERUP:
                reason = "streak"
            elif last >= pw.COMEBACK_ROUNDS:
                reason = "comeback"
            else:
                continue
            held = self.held.setdefault(player.id, [])
            legendaries = self.legendaries.setdefault(player.id, [])
            mythics = self.mythics.setdefault(player.id, [])
            if len(held) + len(legendaries) + len(mythics) >= self.capacity(player.id):
                continue  # com as mãos cheias, a sequência continua valendo para depois
            trailing = player.id in behind
            roll = self.rng.random()
            mythic_edge = MYTHIC_CHANCE[1 if trailing else 0]
            mythic = roll < mythic_edge
            legendary = not mythic and roll < mythic_edge + (
                pw.LEGENDARY_TRAILING_CHANCE if trailing else pw.LEGENDARY_CHANCE
            )
            if mythic:
                kind = self.rng.choice(MYTHICS)
                mythics.append(kind)
            else:
                kind = self.rng.choice(LEGENDARY if legendary else POWERS)
                (legendaries if legendary else held).append(kind)
            by_id[player.id].gained = PowerUpGain(kind=kind, reason=reason, legendary=legendary, mythic=mythic)
            if reason == "streak":
                self.right_runs[player.id] = 0
            elif reason == "comeback":
                self.last_runs[player.id] = 0

    def advance(self, now: float, players: list[Scorable]) -> None:
        """Passa para a próxima fase. O main.py chama quando o tempo acaba (ou todos fizeram a sua parte)."""
        if self.phase == "level":
            self._enter("answering", now, self._longest_window())
        elif self.phase == "answering":
            self._close(now, players)
        elif self.phase in ("starting", "results"):
            if self.round + 1 >= len(self.questions):
                self._enter("finished", now, 0)
                return
            self.round += 1
            self.guesses = {}
            self.first_guesses = {}
            self.ranges = {}
            self.math_puzzles = {}
            self.last_word_by = self.last_word_opened_at = None
            self.last_word_draft = ""
            self.results = []
            self.ready = set()
            if self.powers:
                self._start_powers()
            if self.round > 0 and self.question.difficulty != self.questions[self.round - 1].difficulty:
                self._enter("level", now, LEVEL_SECONDS)
            else:
                self._enter("answering", now, self._longest_window())

    def _longest_window(self) -> float:
        return MATH_SECONDS if self.math_puzzles else ANSWER_SECONDS

    def _boosted_gain(self, player_id: str, points: int) -> int:
        """Segunda chance e Sniper só mexem no ganho."""
        if points <= 0:
            return points
        if self.first_guesses.get(player_id) and player_id in self.guesses:
            points = int(points * pw.SECOND_CHANCE_SHARE)
        if self._affects("sniper", player_id):
            points *= SNIPER_FACTOR
        return points

    def _close(self, now: float, players: list[Scorable]) -> None:
        q = self.question
        self.results = []
        earned = set()  # quem ganhou QI com o chute, antes de Escudo e Roubo: é o "acerto" dos poderes
        exact_guesses = set()
        final_guesses, originals = self._swap_guesses(players)
        copiers = [p.id for p in players if self._affects("copy", p.id)]
        nudged = self._apply_nudges(final_guesses, [p.id for p in players if p.id not in copiers])
        copied = self._apply_copies(final_guesses, copiers)
        nudged |= self._apply_nudges(final_guesses, copiers)
        for player in players:
            first = self.first_guesses.get(player.id)
            retried = player.id in self.guesses
            guessed = final_guesses.get(player.id)
            copy = copied.get(player.id)
            if guessed is None:
                error, elapsed = None, ANSWER_SECONDS
            else:
                error, elapsed = error_percent(q, guessed[0]), max(0.0, guessed[1] - self.phase_started_at)
            scored = None if error is None else self._scored_error(player.id, error)
            delta = guess_points(scored, q.difficulty, self.point_scale)
            if error == 0 and not copy:
                exact_guesses.add(player.id)
            if delta > 0 and not copy:  # o acerto foi de outro: não vale para a sequência
                earned.add(player.id)
            delta = self._boosted_gain(player.id, delta)
            doubled = self._affects("double", player.id)
            if doubled and error == 0:  # o bônus de cravar conta uma vez só
                delta += self._boosted_gain(player.id, _round(SCORING[q.difficulty].max_points * self.point_scale))
            elif doubled:
                hard_loss = delta < 0 and q.difficulty == "hard"
                delta *= pw.DOUBLE_HARD_LOSS_FACTOR if hard_loss else pw.DOUBLE_FACTOR
            shielded = -delta if delta < 0 and self._affects("shield", player.id) else 0
            player.answer_ms += round(elapsed * 1000)
            self.results.append(
                EstimateGuess(
                    player_id=player.id,
                    value=guessed[0] if guessed else None,
                    error_percent=None if error is None else round(error, 1),
                    exact=error == 0,
                    delta=delta + shielded,
                    elapsed_ms=round(elapsed * 1000) if guessed else None,
                    shielded=shielded,
                    stolen=0,
                    robbed=0,
                    doubled=doubled,
                    first_value=first[0] if first and retried else None,
                    nudged_from=nudged.get(player.id),
                    swapped_from=originals.get(player.id),
                    copied_from=copy[0] if copy else None,
                    copied_own=copy[1] if copy else None,
                    last_word=0,
                    expired=[],
                    gained=None,
                )
            )
        if self.powers:
            self._settle_steals(players)
            self._settle_last_word()
        by_id = {g.player_id: g for g in self.results}
        for player in players:
            player.score += by_id[player.id].total
        if self.powers:
            top = max((p.score for p in players), default=0)
            self.leaders = {p.id for p in players if p.score == top}
            self._wear_lasting()
            if self.has_next_round:
                self._gains(players, earned, exact_guesses)
            self.theme_choices = self._draw_theme_choices()
        # Do mais perto para o mais longe; quem não chutou fica no fim.
        self.results.sort(key=lambda r: (r.error_percent is None, r.error_percent or 0, r.elapsed_ms or 0))
        self._enter("results", now, results_seconds(q.fact, self.powers))

    def deadline(self) -> float:
        return self.phase_ends_at + (LATE_SECONDS if self.phase == "answering" else 0)

    def view(self, now: float, viewer: str | None = None) -> EstimateView:
        q = self.question if self.round >= 0 else None
        silenced = self.silence_left(viewer) if viewer else 0
        reveal = self.phase in ("results", "finished") and q is not None and not silenced
        mine = self.guesses.get(viewer) if viewer else None
        first = self.first_guesses.get(viewer) if viewer else None
        answering = self.phase == "answering"
        retrying = answering and first is not None and mine is None
        ends_at = self.phase_ends_at
        started_at = self.phase_started_at
        time_up = bool(viewer) and self.time_is_up(viewer, now)
        if self.last_word_opened_at is not None:
            started_at = self.last_word_opened_at  # a contagem da palavra final é só dela
        elif answering and viewer and viewer not in self.guesses and not time_up and viewer != self.last_word_by:
            ends_at = self.phase_started_at + self.answer_window(viewer)  # o seu prazo, não o do alvo
        return EstimateView(
            phase=self.phase,
            phase_duration_ms=round((ends_at - started_at) * 1000),
            phase_ends_in_ms=max(0, round((ends_at - now) * 1000)),
            round=self.round + 1,
            total_rounds=len(self.questions),
            theme=q.theme if q else None,
            difficulty=q.difficulty if q else self.questions[0].difficulty,
            text=q.text if q and self.phase not in ("starting", "level") else None,
            unit=q.unit if q else None,
            answered=[] if silenced else list(self.guesses),
            my_guess=mine[0] if mine else None,
            first_guess=first[0] if retrying else None,
            retry_hint=("higher" if q.answer > first[0] else "lower") if retrying else None,
            answer=q.answer if reveal else None,
            reference=error_base(q) if reveal else None,
            fact=q.fact if reveal else None,
            guesses=self.results if reveal else [],
            scoring=self._scoring_view(q.difficulty if q else self.questions[0].difficulty, viewer),
            ready=sorted(self.ready),
            powers=self.powers,
            powerups=list(self.held.get(viewer, [])) if viewer else [],
            legendary_powerups=list(self.legendaries.get(viewer, [])) if viewer else [],
            mythic_powerups=list(self.mythics.get(viewer, [])) if viewer else [],
            powerup_max=self.capacity(viewer) if viewer else self.powerup_max,
            power_run=self.right_runs.get(viewer, 0) if viewer else 0,
            power_run_goal=pw.STREAK_FOR_POWERUP,
            starting_powerup=self.starting.get(viewer) if viewer else None,
            can_arm=self.can_arm and not silenced,
            armed=self.armed.get(viewer) if viewer else None,
            active=[] if silenced and self.phase == "results" else self._visible_uses(viewer),
            lasting=self._lasting_view(viewer) if viewer and self.phase != "results" else [],
            range_hint=self.ranges.get(viewer) if answering and viewer else None,
            hot_digits=answer_digits(q.answer) if answering and viewer and self._affects("hot_keys", viewer) else None,
            math=self.math_puzzles.get(viewer) if answering and viewer else None,
            math_watch=self._math_watch(viewer, now) if answering and viewer and not silenced else [],
            last_word=self._last_word_view() if answering and self.last_word_by and not silenced else None,
            time_up=time_up,
            silenced_rounds=silenced,
            theme_choices=self.theme_choices,
            powers_round=self.powers_round,
        )

    def _last_word_view(self) -> EstimateLastWord:
        """Os chutes (e o visor de quem fez contas) só aparecem quando chega a vez da palavra final."""
        guesses = []
        if self.last_word_opened_at is not None:
            answer = self.question.answer
            values = {pid: guess[0] for pid, guess in self.guesses.items()}
            values |= {pid: p.value for pid, p in self.math_puzzles.items() if pid not in self.guesses}
            for pid, value in sorted(values.items(), key=lambda item: item[1]):
                if pid != self.last_word_by:
                    side = "exact" if value == answer else "higher" if answer > value else "lower"
                    guesses.append(LastWordGuess(player_id=pid, value=value, side=side))
        return EstimateLastWord(
            player_id=self.last_word_by,
            open=self.last_word_opened_at is not None,
            guesses=guesses,
            draft=self.last_word_draft,
        )

    def _math_watch(self, viewer: str, now: float) -> list[MathWatch]:
        """Quem já chutou ou ficou sem tempo assiste a quem ainda faz contas."""
        if viewer not in self.guesses and not self.time_is_up(viewer, now):
            return []
        return [
            MathWatch(player_id=pid, math=puzzle)
            for pid, puzzle in self.math_puzzles.items()
            if pid != viewer and pid not in self.guesses
        ]

    def _lasting_view(self, viewer: str) -> list[LastingPowerUp]:
        lasting = [
            LastingPowerUp(kind=kind, rounds_left=left, total=self.lasting_total[viewer][kind])
            for kind, left in self.lasting.get(viewer, {}).items()
            if self._affects(kind, viewer)
        ]
        if silence_left := self.silence_left(viewer):
            lasting.append(LastingPowerUp(kind="silence", rounds_left=silence_left, total=pw.SILENCE_ROUNDS))
        return lasting

    def _visible_uses(self, viewer: str | None) -> list[PowerUpUse]:
        """Roubo, Empurrão e Troca-troca são surpresa até a revelação, e o Reverso armado só o dono vê."""
        if not self.powers_round:
            return []
        uses = [use for use in self.active if use.kind != "reverse" or use.by == viewer]
        if self.phase == "results":
            return uses
        return [use for use in uses if use.kind not in ("steal", "nudge", "swap") or use.by == viewer]

    def _scoring_view(self, difficulty: str, viewer: str | None) -> EstimateScoring:
        """Com Margem larga ou Sniper, a régua de quem usou mostra as zonas desse jogador."""
        rules = SCORING[difficulty]
        widen = 1 / self._zone_shrink(viewer)
        gain = SNIPER_FACTOR if viewer and self._affects("sniper", viewer) else 1
        return EstimateScoring(
            max_points=_round(rules.max_points * self.point_scale * gain),
            exact_bonus=_round(rules.exact_bonus * self.point_scale * gain),
            break_even_percent=rules.break_even * widen,
            max_loss=_round(rules.max_loss * self.point_scale),
            max_loss_percent=rules.max_loss_at * widen,
        )
