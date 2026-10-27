"""Modo clássico: perguntas de múltipla escolha com pontos de QI.

Lógica pura: quem chama passa o relógio (`now`) e o main.py cuida das esperas.
"""

import json
import math
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Literal, Protocol

from pydantic import BaseModel, Field, model_validator

from app import powerups
from app.events import (
    Bonus,
    Difficulty,
    GameView,
    LastingPowerUp,
    PowerUp,
    PowerUpGain,
    PowerUpUse,
    QuestionView,
    RoundResult,
)

QUESTIONS_DIR = Path(__file__).parent / "questions"

DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
FINAL_DIFFICULTY: Difficulty = "impossible"
OPTION_COUNT = {"easy": 4, "medium": 4, "hard": 4, "impossible": 6}
STARTING_IQ = 50
REFERENCE_ROUNDS = 20
# (mínimo, máximo): o máximo é para quem responde na carência.
CORRECT_POINTS = {"easy": (0, 0), "medium": (5, 11), "hard": (13, 22), "impossible": (35, 35)}
WRONG_PENALTY = {"easy": -15, "medium": -10, "hard": -5, "impossible": 0}
# Gabaritar as fáceis rende 1 por fácil, sem escala. Sequências de acertos contam só médias e
# difíceis; de erros, qualquer nível. Repetir uma sequência na mesma partida vale a metade.
PERFECT_EASY_BONUS = 1
STREAK_BONUS = {3: 3, 5: 10, 10: 20}
WRONG_STREAK_PENALTY = {3: -5, 5: -10}
SPEED_GRACE_SECONDS = 3.0
NO_ANSWER_PENALTY = -10

# Efeito de digitação; o tempo de resposta só começa depois.
TYPING_SECONDS_PER_CHAR = 0.035
MIN_READING_SECONDS = 1.5
MAX_READING_SECONDS = 6.0
START_SECONDS = 5.0
LEVEL_SECONDS = 3.0
INTRO_SECONDS = 5.0
BET_SECONDS = 12.0
# O relógio do jogador começa quando o estado chega (atrasado pela rede) e o clique ainda
# precisa voltar: sem essa folga, quem clica no último instante fica sem resposta.
LATE_SECONDS = 1.0
PREPARATION_PHASES = ("starting", "level", "intro", "betting")
# A revelação dura o suficiente para ler a curiosidade; acaba antes se todos pularem.
RESULTS_SECONDS_PER_CHAR = 0.055
MIN_RESULTS_SECONDS = 10.0
MAX_RESULTS_SECONDS = 15.0
# Aposta: uma por partida, antes da pergunta do meio das difíceis; quem não aposta fica com 0.
BET_PERCENTS = (25, 50, 75, 100)
BET_MAX_PERCENT = 100
BET_ODDS = 1.5  # apostou 100 e acertou: lucra 50; errou ou não respondeu: perde os 100


Phase = Literal["starting", "level", "intro", "betting", "reading", "answering", "results", "finished"]


def steal_share(target: RoundResult) -> int:
    """Roubo normal: 10 fixos e, se o alvo acertou, mais metade do que ele ganhou."""
    return powerups.STEAL_FIXED + max(0, int(target.delta * powerups.STEAL_GAIN_SHARE))


def legendary_steal_shares(targets: list[RoundResult], score_before: dict[str, int]) -> list[tuple[RoundResult, int]]:
    """Roubo lendário: 1,5 Roubo normal (pela média das vítimas) repartido entre elas; quem estava
    em 1º antes da pergunta (empate conta) pesa mais. Assim o ladrão não ganha mais em sala grande."""
    if not targets:
        return []
    pool = powerups.LEGENDARY_STEAL_POOL * sum(steal_share(t) for t in targets) / len(targets)
    top = max(score_before.get(t.player_id, 0) for t in targets)
    weights = [powerups.LEGENDARY_STEAL_TOP_WEIGHT if score_before.get(t.player_id, 0) == top else 1 for t in targets]
    total = sum(weights)
    return [(t, round(pool * w / total)) for t, w in zip(targets, weights)]


class GameError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


class Question(BaseModel):
    id: str
    theme: str
    difficulty: Difficulty
    text: str
    options: list[str]
    answer: int = Field(ge=0)
    fact: str = Field(min_length=1)

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
    """15 → 5/5/5; 10 → 3/3/4; 20 → 6/7/7. As sobras vão para as mais difíceis, uma em cada."""
    leftover = rounds % 3
    return {d: rounds // 3 + (1 if i >= len(DIFFICULTIES) - leftover else 0) for i, d in enumerate(DIFFICULTIES)}


def pick_questions(bank: list[Question], rounds: int, used: set[str], rng: random.Random) -> list[Question]:
    """Sorteia as perguntas da partida, das fáceis às difíceis, evitando as já usadas na sala.

    São `rounds` perguntas normais e, quando o banco tem alguma, uma pergunta final impossível
    extra no fim (15 rodadas → 16 perguntas).
    As alternativas são embaralhadas para a certa não ficar sempre na mesma posição.
    """
    has_final = any(q.difficulty == FINAL_DIFFICULTY for q in bank)
    counts = split_by_difficulty(rounds)
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
    return min(MAX_RESULTS_SECONDS, max(MIN_RESULTS_SECONDS, 7 + len(fact) * RESULTS_SECONDS_PER_CHAR))


def max_bet(score: int) -> int:
    return max(0, score * BET_MAX_PERCENT // 100)


def bet_win(amount: int) -> int:
    return int(amount * (BET_ODDS - 1))


def bet_round(questions: list[Question]) -> int | None:
    """Índice da pergunta com aposta: a do meio das difíceis (6 difíceis → a 4ª)."""
    hard = [i for i, q in enumerate(questions) if q.difficulty == "hard"]
    return hard[len(hard) // 2] if hard else None


def point_scale(rounds: int) -> float:
    """Partidas curtas valem mais por pergunta e longas valem menos, para o QI final ficar
    na mesma faixa em qualquer tamanho (a tabela vale como está numa partida de 20)."""
    return REFERENCE_ROUNDS / rounds


def points(difficulty: Difficulty, correct: bool | None, remaining_fraction: float = 0, scale: float = 1.0) -> int:
    """correct=None significa que não respondeu. A pergunta final não muda com a escala."""
    if difficulty == FINAL_DIFFICULTY:
        scale = 1.0
    if correct is None:
        return round(NO_ANSWER_PENALTY * scale)
    if not correct:
        return round(WRONG_PENALTY[difficulty] * scale)
    low, high = CORRECT_POINTS[difficulty]
    return round((low + (high - low) * max(0.0, min(1.0, remaining_fraction))) * scale)


class Scorable(Protocol):
    id: str
    score: int
    answer_ms: int  # tempo total de resposta na partida, para desempate
    streak: int  # > 0: acertos seguidos; < 0: erros seguidos


@dataclass
class Streak:
    right: int = 0
    wrong: int = 0
    perfect_easy: bool = True
    awarded: dict[tuple[str, int], int] = field(default_factory=dict)  # quantas vezes ganhou cada um


@dataclass
class Decoy:
    """Alternativas falsas de um jogador nesta pergunta. Por dentro, as falsas são os índices
    depois das verdadeiras; `order` diz em que posição da tela cada uma aparece."""

    texts: list[str]
    order: list[int]  # posição na tela → índice por dentro
    payees: list[tuple[str, int]]  # quem ganha QI se ele cair, e quanto
    mirrors: list[int]  # Espiar: cada falsa copia a contagem de uma alternativa errada


@dataclass
class Answer:
    option: int
    at: float


@dataclass
class Game:
    questions: list[Question]
    answer_seconds: float
    point_scale: float = 1.0
    speed_grace_seconds: float = SPEED_GRACE_SECONDS
    round: int = -1  # índice da pergunta atual; -1 antes de começar
    phase: Phase = "reading"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    answers: dict[str, Answer] = field(default_factory=dict)
    results: list[RoundResult] = field(default_factory=list)
    streaks: dict[str, Streak] = field(default_factory=dict)
    bets: dict[str, int] = field(default_factory=dict)
    rng: random.Random = field(default_factory=random.Random)
    powers: bool = False
    powerup_max: int = powerups.MAX_HELD
    # Habilidades (ver powerups.py): guardadas, armadas para a próxima pergunta e valendo nesta.
    powerups: dict[str, list[PowerUp]] = field(default_factory=dict)
    legendaries: dict[str, list[PowerUp]] = field(default_factory=dict)
    starting_powerups: dict[str, PowerUp] = field(default_factory=dict)
    armed: dict[str, PowerUpUse] = field(default_factory=dict)
    active: list[PowerUpUse] = field(default_factory=list)
    hidden_options: dict[str, list[int]] = field(default_factory=dict)  # tiradas pelo 50/50
    first_wrong: dict[str, Answer] = field(default_factory=dict)  # Segunda chance: 1ª tentativa errada
    # Habilidades que duram mais de uma pergunta: perguntas comuns restantes de cada uma, por jogador.
    lasting: dict[str, dict[PowerUp, int]] = field(default_factory=dict)
    lasting_total: dict[str, dict[PowerUp, int]] = field(default_factory=dict)
    used_lasting: dict[str, set[PowerUp]] = field(default_factory=dict)  # as que já valeram: não quebram
    # Silêncios valendo e quantas perguntas comuns faltam em cada um, contando a atual.
    silences: list[tuple[PowerUpUse, int]] = field(default_factory=list)
    extra_slots: dict[str, int] = field(default_factory=dict)  # vagas a mais da Mochila
    investments: dict[str, int] = field(default_factory=dict)  # acertos seguidos de cada Investimento
    tolls: dict[str, list[tuple[str, list[int]]]] = field(default_factory=dict)  # alvo -> (quem recebe, preços)
    decoys: dict[str, Decoy | None] = field(default_factory=dict)
    # Tema: perguntas que ainda dá para pôr no lugar da próxima, e os temas sorteados nesta revelação.
    bank: list[Question] = field(default_factory=list)
    used: set[str] = field(default_factory=set)
    theme_choices: list[str] = field(default_factory=list)
    leaders: set[str] = field(default_factory=set)  # em 1º depois da última rodada (o empate conta)
    right_runs: dict[str, int] = field(default_factory=dict)  # acertos seguidos rumo à próxima
    last_runs: dict[str, int] = field(default_factory=dict)  # rodadas seguidas em último, longe
    ready: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.bet_round = bet_round(self.questions)

    @property
    def is_bet_round(self) -> bool:
        return self.round == self.bet_round

    @property
    def question(self) -> Question:
        return self.questions[self.round]

    @property
    def has_next_round(self) -> bool:
        return self.round + 1 < len(self.questions)

    @property
    def can_arm(self) -> bool:
        """Na revelação, se a próxima pergunta é comum (nem a aposta nem a final)."""
        if not self.powers or self.phase != "results" or not self.has_next_round:
            return False
        upcoming = self.round + 1
        return upcoming != self.bet_round and self.questions[upcoming].difficulty != FINAL_DIFFICULTY

    def capacity(self, player_id: str) -> int:
        return self.powerup_max + self.extra_slots.get(player_id, 0)

    def deal_powerups(self, player_ids: list[str]) -> None:
        dealt = [kind for kind in powerups.POWERUPS if kind not in powerups.NOT_DEALT]
        for pid in player_ids:
            kind = self.rng.choice(dealt)
            self.powerups[pid] = [kind]
            self.starting_powerups[pid] = kind

    def arm(
        self,
        player_id: str,
        kind: PowerUp,
        target: str | None,
        player_ids: list[str],
        legendary: bool = False,
        theme: str | None = None,
    ) -> None:
        if kind == "backpack" and not legendary:
            self._open_backpack(player_id)
            return
        if not self.can_arm:
            raise GameError("Agora não dá para usar habilidade.")
        if self.is_silenced(player_id):
            raise GameError("Silenciado: sem habilidades por enquanto.")
        if player_id in self.armed:
            raise GameError("Você já armou uma habilidade para a próxima pergunta.")
        if legendary:
            held = self.legendaries.get(player_id, [])
            if kind not in held:
                raise GameError("Você não tem essa habilidade.")
            held.remove(kind)
            self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=None, reflected_by=None, legendary=True)
            return
        held = self.powerups.get(player_id, [])
        if kind not in held:
            raise GameError("Você não tem essa habilidade.")
        if kind in powerups.INSTANT:
            raise GameError("Essa se usa na hora da pergunta.")
        if kind in powerups.TARGETED:
            if target is None or target == player_id or target not in player_ids:
                raise GameError("Escolha em quem usar.")
        else:
            target = None
        if kind == "investment":
            if self.questions[self.round + 1].difficulty == "easy":
                raise GameError("O Investimento só vale a partir das médias.")
            if player_id in self.investments:
                raise GameError("Seu Investimento ainda está valendo.")
        if kind == "theme":
            if theme not in self.theme_choices:
                raise GameError("Escolha um dos temas.")
            if any(use.kind == "theme" for use in self.armed.values()):
                raise GameError("Alguém já escolheu o tema da próxima pergunta.")
            self._swap_next_question(theme)
        else:
            theme = None
        held.remove(kind)
        self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=target, reflected_by=None, theme=theme)

    def _open_backpack(self, player_id: str) -> None:
        """Mochila: vale na hora, sem ocupar a vez de armar. Uma vaga a mais e um poder comum."""
        if not self.powers or self.phase != "results":
            raise GameError("Agora não dá para usar habilidade.")
        if self.is_silenced(player_id):
            raise GameError("Silenciado: sem habilidades por enquanto.")
        held = self.powerups.get(player_id, [])
        if "backpack" not in held:
            raise GameError("Você não tem essa habilidade.")
        if self.extra_slots.get(player_id, 0) >= powerups.BACKPACK_MAX_EXTRA:
            raise GameError("Sua Mochila já está no tamanho máximo.")
        held.remove("backpack")
        self.extra_slots[player_id] = self.extra_slots.get(player_id, 0) + 1
        held.append(self.rng.choice([kind for kind in powerups.POWERUPS if kind != "backpack"]))

    def _swap_next_question(self, theme: str) -> None:
        upcoming = self.round + 1
        current = self.questions[upcoming]
        if current.theme == theme:
            return
        pool = [q for q in self.bank if q.theme == theme and q.difficulty == current.difficulty and q.id not in self.used]
        if not pool:
            raise GameError("Acabaram as perguntas desse tema.")
        question = self.rng.choice(pool)
        self.used.add(question.id)
        self.questions[upcoming] = _shuffle_options(question, self.rng)

    def _draw_theme_choices(self) -> list[str]:
        if not self.powers or not self.has_next_round:
            return []
        upcoming = self.questions[self.round + 1]
        themes = sorted(
            {q.theme for q in self.bank if q.difficulty == upcoming.difficulty and q.id not in self.used}
            | {upcoming.theme}
        )
        return sorted(self.rng.sample(themes, min(powerups.THEME_CHOICES, len(themes))))

    def use_now(self, player_id: str, kind: PowerUp) -> None:
        """50/50 e Espiar: usados durante a pergunta, valem na hora."""
        if self.phase not in ("reading", "answering") or not self._counts_for_powers():
            raise GameError("Agora não dá para usar habilidade.")
        if kind not in powerups.INSTANT:
            raise GameError("Essa se arma na revelação.")
        if self.is_silenced(player_id):
            raise GameError("Silenciado: sem habilidades por enquanto.")
        held = self.powerups.get(player_id, [])
        if kind not in held:
            raise GameError("Você não tem essa habilidade.")
        if player_id in self.answers:
            raise GameError("Você já respondeu.")
        if self._affects(kind, player_id):
            raise GameError("Já está valendo.")
        held.remove(kind)
        self.active.append(PowerUpUse(kind=kind, by=player_id, target=None, reflected_by=None))
        if kind == "fifty_fifty":
            q = self.question
            self.hidden_options[player_id] = powerups.fifty_fifty(len(q.options), q.answer, self.rng)

    def mark_ready(self, player_id: str) -> None:
        if self.phase != "results":
            raise GameError("Agora não dá para pular.")
        self.ready.add(player_id)

    def everyone_ready(self, player_ids: list[str]) -> bool:
        """Quem está silenciado não vê a revelação: não precisa tocar em Pular."""
        return all(pid in self.ready or self.is_silenced(pid) for pid in player_ids)

    def start_round(self, now: float) -> None:
        if self.round >= 0 and self._counts_for_powers():
            self.silences = [(use, left - 1) for use, left in self.silences if left > 1]
        self.round += 1
        self.answers = {}
        self.results = []
        self.bets = {}
        self.ready = set()
        self.first_wrong = {}
        self.hidden_options = {}
        self.tolls = {}
        self.decoys = {}
        self.theme_choices = []
        armed = list(self.armed.values())
        self.armed = {}
        for use in armed:
            if use.kind == "investment":
                self.investments[use.by] = 0
            if use.kind in powerups.LASTING:
                rounds = powerups.LASTING[use.kind]
                if use.kind == "reverse" and use.by in self.leaders:
                    rounds = powerups.REVERSE_LEADER_ROUNDS
                self.lasting.setdefault(use.by, {})[use.kind] = rounds
                self.lasting_total.setdefault(use.by, {})[use.kind] = rounds
                self.used_lasting.get(use.by, set()).discard(use.kind)
        reversers = {pid for pid in self.lasting if self._affects("reverse", pid)}
        self.active = powerups.reflect(armed, reversers)
        for use in self.active:
            if use.reflected_by:
                self.lasting[use.reflected_by].pop("reverse", None)
            if use.kind == "silence":
                self.silences.append((use, powerups.SILENCE_ROUNDS))
        if self.round == 0:
            self._enter("starting", now, START_SECONDS)
        elif self.question.difficulty == FINAL_DIFFICULTY:
            self._enter("intro", now, INTRO_SECONDS)
        elif self.question.difficulty != self.questions[self.round - 1].difficulty:
            self._enter("level", now, LEVEL_SECONDS)
        elif self.is_bet_round:
            self._enter("betting", now, BET_SECONDS)
        else:
            self.begin_reading(now)

    def begin_reading(self, now: float) -> None:
        self._enter("reading", now, reading_seconds(self.question.text))

    def open_answers(self, now: float) -> None:
        # A fase dura o prazo mais longo (Tempo extra); cada um tem o seu (ver answer_window).
        longest = max([self.answer_seconds, *(self.answer_window(pid) for pid in self._extra_time_ids())])
        self._enter("answering", now, longest)

    def _uses(self, kind: PowerUp) -> list[PowerUpUse]:
        return [use for use in self.active if use.kind == kind]

    def _affects(self, kind: PowerUp, player_id: str) -> bool:
        """A habilidade vale para o jogador nesta pergunta (como alvo, ou para si nas que não miram)."""
        if kind == "silence":
            return self.is_silenced(player_id)
        if kind in powerups.LASTING:
            return self._counts_for_powers() and self.lasting.get(player_id, {}).get(kind, 0) > 0
        return any(
            use.by != player_id if use.legendary else (use.target or use.by) == player_id for use in self._uses(kind)
        )

    def silence_left(self, player_id: str) -> int:
        """Perguntas comuns de Silêncio que faltam para o jogador, contando a atual (e a revelação dela).
        Na aposta ele fica livre e volta a ficar silenciado depois. Um Silêncio novo em quem já está
        silenciado recomeça a contagem, não soma."""
        if not self._counts_for_powers():
            return 0
        hits = (left for use, left in self.silences if (use.by != player_id if use.legendary else use.target == player_id))
        return max(hits, default=0)

    def is_silenced(self, player_id: str) -> bool:
        return self.silence_left(player_id) > 0

    def _decoy_for(self, player_id: str) -> Decoy | None:
        """Alternativas falsas no jogador nesta pergunta, sorteadas na primeira vez que alguém olha."""
        if player_id not in self.decoys:
            payees = [
                (use.reflected_by or use.by, powerups.LEGENDARY_DECOY_BONUS if use.legendary else powerups.DECOY_BONUS)
                for use in self._uses("decoy")
                if (use.by != player_id if use.legendary else use.target == player_id)
            ]
            self.decoys[player_id] = self._make_decoy(payees) if payees and self._counts_for_powers() else None
        return self.decoys[player_id]

    def _make_decoy(self, payees: list[tuple[str, int]]) -> Decoy | None:
        q = self.question
        texts = powerups.decoys(q.options[q.answer], q.options, self._similar_options(q), self.rng)
        if not texts:
            return None
        order = list(range(len(q.options) + len(texts)))
        self.rng.shuffle(order)
        wrong = [i for i in range(len(q.options)) if i != q.answer]
        return Decoy(texts=texts, order=order, payees=payees, mirrors=[self.rng.choice(wrong) for _ in texts])

    def _similar_options(self, q: Question) -> list[str]:
        """Alternativas de perguntas do mesmo tema, das mais parecidas com `q` para as menos:
        começar igual ("Que ator…") e ter palavras em comum contam."""

        def words(text: str) -> set[str]:
            return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 4}

        head, mine = q.text.lower().split()[:2], words(q.text)
        others = [o for o in self.bank if o.theme == q.theme and o.text != q.text]
        self.rng.shuffle(others)
        others.sort(key=lambda o: -(3 * (o.text.lower().split()[:2] == head) + len(mine & words(o.text))))
        return [option for other in others[:12] for option in other.options]

    def _tolls_on(self, player_id: str) -> list[tuple[str, list[int]]]:
        """Pedágios no jogador nesta pergunta: quem recebe e o preço de cada alternativa.
        Sorteados na primeira vez que alguém olha, para ficarem iguais até o fim da rodada."""
        if player_id not in self.tolls:
            tolls = []
            for use in self._uses("toll"):
                if use.by != player_id if use.legendary else use.target == player_id:
                    low, high = powerups.LEGENDARY_TOLL_PRICES if use.legendary else powerups.TOLL_PRICES
                    prices = [self.rng.randint(low, high) for _ in self.question.options]
                    tolls.append((use.reflected_by or use.by, prices))
            self.tolls[player_id] = tolls
        return self.tolls[player_id]

    def _counts_for_powers(self) -> bool:
        return self.powers and not self.is_bet_round and self.question.difficulty != FINAL_DIFFICULTY

    def _extra_time_ids(self) -> list[str]:
        return [pid for pid in self.lasting if self._affects("extra_time", pid)]

    def answer_window(self, player_id: str) -> float:
        """Segundos que o jogador tem para responder: Tempo extra soma, Acelerador corta."""
        seconds = self.answer_seconds
        if player_id in self._extra_time_ids():
            seconds += powerups.EXTRA_SECONDS
        if self._affects("accelerator", player_id):
            seconds *= powerups.ACCELERATOR_FACTOR
        return seconds

    def grace_window(self, player_id: str) -> float:
        if self._affects("accelerator", player_id) or self._affects("silence", player_id):
            return 0.0
        if player_id in self._extra_time_ids():
            return self.answer_window(player_id)  # QI cheio o tempo todo
        return self.speed_grace_seconds

    def deadline(self, player_id: str) -> float:
        return self.phase_started_at + self.answer_window(player_id)

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase != "answering" or now > self.deadline(player_id) + LATE_SECONDS:
            raise GameError("Agora não dá para responder.")
        if player_id in self.answers:
            raise GameError("Você já respondeu.")
        tried = self.first_wrong.get(player_id)
        decoy = self._decoy_for(player_id)
        if not 0 <= option < len(self.question.options) + (len(decoy.texts) if decoy else 0):
            raise GameError("Alternativa inválida.")
        if decoy:
            option = decoy.order[option]
        if (
            option in self.hidden_options.get(player_id, [])
            or (tried and tried.option == option)
        ):
            raise GameError("Alternativa inválida.")
        answer = Answer(option, min(now, self.deadline(player_id)))
        if option != self.question.answer and not tried and self._affects("second_chance", player_id):
            self.first_wrong[player_id] = answer
            self.used_lasting.setdefault(player_id, set()).add("second_chance")
            return
        self.answers[player_id] = answer

    def bet(self, player: Scorable, amount: int, now: float) -> None:
        if self.phase != "betting" or now > self.phase_ends_at + LATE_SECONDS:
            raise GameError("Agora não dá para apostar.")
        if player.id in self.bets:
            raise GameError("Você já apostou.")
        if not 0 <= amount <= max_bet(player.score):
            raise GameError(f"Dá para apostar de 0 a {max_bet(player.score)} de QI.")
        self.bets[player.id] = amount

    def everyone_bet(self, players: list[Scorable]) -> bool:
        """Quem não tem QI para apostar não precisa esperar."""
        return all(p.id in self.bets or max_bet(p.score) == 0 for p in players)

    def everyone_answered(self, player_ids: list[str]) -> bool:
        return all(pid in self.answers for pid in player_ids)

    def answers_close_at(self, player_ids: list[str]) -> float | None:
        """Quando o último prazo de quem ainda não respondeu acaba (com a folga); None se todos já."""
        pending = [self.deadline(pid) + LATE_SECONDS for pid in player_ids if pid not in self.answers]
        return max(pending, default=None)

    def speed_fraction(self, elapsed: float, player_id: str | None = None) -> float:
        """1 dentro da carência, caindo até 0 no fim do tempo de resposta (o do jogador, se dado)."""
        grace = self.grace_window(player_id) if player_id else self.speed_grace_seconds
        window = self.answer_window(player_id) if player_id else self.answer_seconds
        decay = window - grace
        if elapsed <= grace or decay <= 0:
            return 1.0
        return max(0.0, 1 - (elapsed - grace) / decay)

    def close_round(self, players: list[Scorable], now: float) -> None:
        """Calcula os pontos da rodada e aplica no placar dos jogadores."""
        difficulty = self.question.difficulty
        self.results = []
        for player in players:
            first = self.first_wrong.get(player.id)
            # Na segunda chance, quem não tentou de novo fica com o erro da primeira.
            answer = self.answers.get(player.id) or first
            if answer is None:
                correct, delta = False, points(difficulty, None, scale=self.point_scale)
                elapsed = self.answer_window(player.id)
            else:
                correct = answer.option == self.question.answer
                elapsed = answer.at - self.phase_started_at
                delta = points(difficulty, correct, self.speed_fraction(elapsed, player.id), self.point_scale)
                if correct and first:
                    delta = int(delta * powerups.SECOND_CHANCE_SHARE)
            doubled = self._affects("double", player.id)
            if doubled:
                hard_loss = delta < 0 and difficulty == "hard"
                delta *= powerups.DOUBLE_HARD_LOSS_FACTOR if hard_loss else powerups.DOUBLE_FACTOR
            shielded = -delta if delta < 0 and self._affects("shield", player.id) else 0
            bet = self.bets.get(player.id, 0) if self.is_bet_round else None
            player.answer_ms += round(max(0.0, elapsed) * 1000)
            self.results.append(
                RoundResult(
                    player_id=player.id,
                    option=answer.option if answer else None,
                    correct=correct,
                    elapsed_ms=round(elapsed * 1000) if answer else None,
                    delta=delta + shielded,
                    bonuses=self._bonuses(player, difficulty, correct),
                    bet=bet,
                    bet_delta=(bet_win(bet) if correct else -bet) if bet else 0,
                    shielded=shielded,
                    stolen=0,
                    robbed=0,
                    tolled=0,
                    toll_received=0,
                    decoy=None,
                    tricked=0,
                    doubled=doubled,
                    first_option=first.option if first and answer is not first else None,
                    expired=[],
                    gained=None,
                )
            )
        by_id = {r.player_id: r for r in self.results}
        if self._counts_for_powers():
            self._pay_investments(by_id)
        real = len(self.question.options)
        for result in self.results:
            decoy = self._decoy_for(result.player_id)
            if decoy and result.option is not None and result.option >= real:
                result.decoy = decoy.texts[result.option - real]
                for payee, bonus in decoy.payees:
                    if payee in by_id:
                        by_id[payee].tricked += bonus
        for result in self.results:
            for payee, prices in self._tolls_on(result.player_id):
                price = min(prices) if result.option is None or result.option >= real else prices[result.option]
                result.tolled += price
                if payee in by_id:
                    by_id[payee].toll_received += price
        score_before = {p.id: p.score for p in players}
        for use in self.active:
            thief = by_id.get(use.by)
            if use.kind != "steal" or not thief:
                continue
            if use.legendary:
                shares = legendary_steal_shares([r for r in self.results if r is not thief], score_before)
            else:
                target = by_id.get(use.target)
                shares = [(target, steal_share(target))] if target else []
            for target, share in shares:
                if target.shielded:
                    continue
                thief.stolen += share
                target.robbed += share
        for player, result in zip(players, self.results):
            player.score += (
                result.delta
                + sum(b.delta for b in result.bonuses)
                + result.bet_delta
                + result.stolen
                - result.robbed
                + result.toll_received
                - result.tolled
                + result.tricked
            )
        top = max((p.score for p in players), default=0)
        self.leaders = {p.id for p in players if p.score == top}
        if self._counts_for_powers():
            self._wear_lasting()
        if self.powers and difficulty != FINAL_DIFFICULTY:
            self._powerup_gains(players)
        self.theme_choices = self._draw_theme_choices()
        self._enter("results", now, results_seconds(self.question.fact))

    def _pay_investments(self, by_id: dict[str, RoundResult]) -> None:
        for pid, hits in list(self.investments.items()):
            result = by_id.get(pid)
            if not result:
                continue
            if not result.correct:
                del self.investments[pid]
                continue
            hits += 1
            bonus = powerups.INVESTMENT_BONUS[hits - 1]
            result.bonuses.append(Bonus(kind="investment", count=hits, delta=bonus, repeat=False))
            if hits == len(powerups.INVESTMENT_BONUS):
                del self.investments[pid]
            else:
                self.investments[pid] = hits

    def _wear_lasting(self) -> None:
        """Fim de uma pergunta comum: o Escudo que segurou um erro acaba, e todas as que duram
        gastam uma pergunta. Escudo, Segunda chance e Reverso que chegam ao fim sem uso quebram."""
        by_id = {r.player_id: r for r in self.results}
        for pid, kinds in self.lasting.items():
            result = by_id.get(pid)
            if result and result.shielded:
                kinds.pop("shield", None)
            for kind in list(kinds):
                kinds[kind] -= 1
                if kinds[kind] <= 0:
                    del kinds[kind]
                    if kind in powerups.BREAKABLE and kind not in self.used_lasting.get(pid, set()) and result:
                        result.expired.append(kind)

    def _powerup_gains(self, players: list[Scorable]) -> None:
        """Habilidades ganhas por acertos seguidos ou por estar muito atrás (depois do placar)."""
        behind = powerups.trailing(players)
        for player, result in zip(players, self.results):
            right = self.right_runs[player.id] = self.right_runs.get(player.id, 0) + 1 if result.correct else 0
            last = self.last_runs[player.id] = self.last_runs.get(player.id, 0) + 1 if player.id in behind else 0
            if right >= powerups.STREAK_FOR_POWERUP:
                reason = "streak"
            elif last >= powerups.COMEBACK_ROUNDS:
                reason = "comeback"
            else:
                continue
            held = self.powerups.setdefault(player.id, [])
            legendaries = self.legendaries.setdefault(player.id, [])
            if len(held) + len(legendaries) >= self.capacity(player.id):
                continue  # com as mãos cheias, a sequência continua valendo para depois
            chance = powerups.LEGENDARY_TRAILING_CHANCE if player.id in behind else powerups.LEGENDARY_CHANCE
            legendary = self.rng.random() < chance
            if legendary:
                kind = self.rng.choice(sorted(powerups.TARGETED))
                legendaries.append(kind)
            else:
                kind = self.rng.choice(powerups.POWERUPS)
                held.append(kind)
            result.gained = PowerUpGain(kind=kind, reason=reason, legendary=legendary)
            if reason == "streak":
                self.right_runs[player.id] = 0
            else:
                self.last_runs[player.id] = 0

    def _bonuses(self, player: Scorable, difficulty: Difficulty, correct: bool) -> list[Bonus]:
        """Atualiza as sequências do jogador e devolve os bônus que ele ganhou nesta rodada."""
        if difficulty == FINAL_DIFFICULTY:
            return []
        streak = self.streaks.setdefault(player.id, Streak())
        bonuses = []

        def award(kind: str, count: int, value: int) -> None:
            times = streak.awarded.get((kind, count), 0)
            streak.awarded[(kind, count)] = times + 1
            if times:
                value = int(math.copysign(math.ceil(abs(value) / 2), value))
            bonuses.append(Bonus(kind=kind, count=count, delta=value, repeat=times > 0))

        streak.wrong = 0 if correct else streak.wrong + 1
        if streak.wrong in WRONG_STREAK_PENALTY:
            award("wrong_streak", streak.wrong, round(WRONG_STREAK_PENALTY[streak.wrong] * self.point_scale))
        if difficulty == "easy":
            streak.perfect_easy &= correct
            easy = [i for i, q in enumerate(self.questions) if q.difficulty == "easy"]
            if streak.perfect_easy and self.round == easy[-1]:
                award("perfect_easy", len(easy), len(easy) * PERFECT_EASY_BONUS)
        else:
            streak.right = streak.right + 1 if correct else 0
            if streak.right in STREAK_BONUS:
                award("streak", streak.right, round(STREAK_BONUS[streak.right] * self.point_scale))
        player.streak = streak.right or -streak.wrong
        return bonuses

    def finish(self, now: float) -> None:
        self._enter("finished", now, 0)

    def view(self, now: float, viewer: str | None = None) -> GameView:
        """`viewer`: de quem são as habilidades e as alternativas tiradas que aparecem."""
        q = self.question
        show_answer = self.phase in ("results", "finished")
        ends_at = self.phase_ends_at
        if self.phase == "answering" and viewer:
            ends_at = self.deadline(viewer)  # Tempo extra e Acelerador mudam o prazo de cada um
        silence_left = self.silence_left(viewer) if viewer else 0
        # Silenciado não vê a revelação: nem a resposta certa, nem os resultados, nem a curiosidade.
        hidden = silence_left > 0 and show_answer
        peeking = bool(viewer) and self.phase == "answering" and self._affects("peek", viewer)
        decoy = self._decoy_for(viewer) if viewer and self.phase not in (*PREPARATION_PHASES, "finished") else None
        options, screen = self._screen(decoy)
        mine = self.first_wrong.get(viewer) if viewer else None
        return GameView(
            round=self.round + 1,
            total_rounds=len(self.questions),
            phase=self.phase,
            phase_duration_ms=round((ends_at - self.phase_started_at) * 1000),
            phase_ends_in_ms=max(0, round((ends_at - now) * 1000)),
            difficulty=q.difficulty,
            theme=q.theme,
            question=None
            if self.phase in PREPARATION_PHASES
            else QuestionView(text=q.text, options=options, theme=q.theme, difficulty=q.difficulty),
            answered=[] if silence_left else [*self.answers, *self.first_wrong.keys() - self.answers.keys()],
            bet_round=None if self.bet_round is None else self.bet_round + 1,
            bet_percents=list(BET_PERCENTS),
            bet_max_percent=BET_MAX_PERCENT,
            bet_odds=BET_ODDS,
            bets_placed=list(self.bets),
            powerups=list(self.powerups.get(viewer, [])) if viewer else [],
            legendary_powerups=list(self.legendaries.get(viewer, [])) if viewer else [],
            powerup_max=self.capacity(viewer) if viewer else self.powerup_max,
            starting_powerup=self.starting_powerups.get(viewer) if viewer else None,
            can_arm=self.can_arm and not silence_left,
            armed=self.armed.get(viewer) if viewer else None,
            active=[] if hidden else self._visible_uses(viewer, show_answer),
            hidden_options=[screen(i) for i in self.hidden_options.get(viewer, [])] if viewer else [],
            first_wrong=screen(mine.option) if mine else None,
            peek=self._peek(viewer, decoy) if peeking else None,
            speed_grace_ms=round((self.grace_window(viewer) if viewer else self.speed_grace_seconds) * 1000),
            lasting=self._lasting_view(viewer) if viewer and not show_answer else [],
            silenced_rounds=silence_left,
            tolls=self._toll_view(viewer, decoy) if viewer and self.phase in ("reading", "answering") else None,
            flashbang=bool(viewer) and self.phase in ("reading", "answering") and self._affects("flashbang", viewer),
            theme_choices=self.theme_choices,
            powers_round=self._counts_for_powers(),
            ready=sorted(self.ready),
            correct_option=screen(q.answer) if show_answer and not hidden else None,
            fact=q.fact if show_answer and not hidden else None,
            results=[] if hidden else [self._result_view(r, viewer, screen) for r in self.results],
        )

    def _screen(self, decoy: Decoy | None) -> tuple[list[str], Callable[[int | None], int | None]]:
        """Alternativas na ordem da tela de quem vê, e como achar a posição de cada uma.
        Sem Alternativa falsa é a ordem normal; as falsas de outro jogador não aparecem."""
        q = self.question
        real = len(q.options)
        if not decoy:
            return q.options, lambda i: i if i is not None and i < real else None
        everything = [*q.options, *decoy.texts]
        return [everything[i] for i in decoy.order], lambda i: decoy.order.index(i) if i is not None else None

    def _result_view(
        self, result: RoundResult, viewer: str | None, screen: Callable[[int | None], int | None]
    ) -> RoundResult:
        """Escolhas na ordem da tela de quem vê; a falsa em que outro caiu não tem lugar nela."""
        real = len(self.question.options)
        own = result.player_id == viewer

        def place(option: int | None) -> int | None:
            return None if option is None or (not own and option >= real) else screen(option)

        return result.model_copy(update={"option": place(result.option), "first_option": place(result.first_option)})

    def _lasting_view(self, viewer: str) -> list[LastingPowerUp]:
        lasting = [
            LastingPowerUp(kind=kind, rounds_left=left, total=self.lasting_total[viewer][kind])
            for kind, left in self.lasting.get(viewer, {}).items()
            if self._affects(kind, viewer)
        ]
        if viewer in self.investments:
            total = len(powerups.INVESTMENT_BONUS)
            lasting.append(LastingPowerUp(kind="investment", rounds_left=total - self.investments[viewer], total=total))
        if silence_left := self.silence_left(viewer):
            lasting.append(LastingPowerUp(kind="silence", rounds_left=silence_left, total=powerups.SILENCE_ROUNDS))
        return lasting

    def _toll_view(self, viewer: str, decoy: Decoy | None) -> list[int] | None:
        tolls = self._tolls_on(viewer) if self._counts_for_powers() else []
        if not tolls:
            return None
        prices = [sum(p[i] for _, p in tolls) for i in range(len(self.question.options))]
        if decoy:
            # Responder uma falsa custa o menor pedágio, como não responder.
            prices += [min(prices)] * len(decoy.texts)
            prices = [prices[i] for i in decoy.order]
        return prices

    def _peek(self, viewer: str, decoy: Decoy | None) -> list[int]:
        """Primeira escolha de cada um dos outros, por alternativa. As falsas copiam uma errada."""
        real = len(self.question.options)
        counts = [0] * real
        for pid, answer in {**self.answers, **self.first_wrong}.items():
            if pid != viewer and answer.option < real:
                counts[answer.option] += 1
        if not decoy:
            return counts
        return [counts[i] if i < real else counts[decoy.mirrors[i - real]] for i in decoy.order]

    def _visible_uses(self, viewer: str | None, show_answer: bool) -> list[PowerUpUse]:
        """O roubo é surpresa: durante a pergunta só quem roubou sabe; o alvo descobre na revelação.
        O Reverso armado só aparece para o dono; os outros só descobrem quando ele devolve."""
        uses = [use for use in self.active if use.kind != "reverse" or use.by == viewer]
        if show_answer:
            return uses
        return [use for use in uses if use.kind != "steal" or use.by == viewer]

    def _enter(self, phase: Phase, now: float, seconds: float):
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds
