"""Modo clássico: perguntas de múltipla escolha com pontos de QI.

Lógica pura: quem chama passa o relógio (`now`) e o main.py cuida das esperas.
"""

import json
import math
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

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

# A partida vai das fáceis às difíceis e termina com uma pergunta impossível.
DIFFICULTIES: tuple[Difficulty, ...] = ("easy", "medium", "hard")
FINAL_DIFFICULTY: Difficulty = "impossible"
OPTION_COUNT = {"easy": 4, "medium": 4, "hard": 4, "impossible": 6}
# Pontuação calibrada em partidas de verdade de 20 perguntas: com os bônus e antes da pergunta
# final, um jogador ruim termina perto de 55, um médio perto de 110 e um bom perto de 160-190.
STARTING_IQ = 50
REFERENCE_ROUNDS = 20
# Acerto rende do mínimo (respondeu no último instante) ao máximo (na hora).
CORRECT_POINTS = {"easy": (0, 0), "medium": (5, 11), "hard": (13, 22), "impossible": (35, 35)}
WRONG_PENALTY = {"easy": -15, "medium": -10, "hard": -5, "impossible": 0}
# Bônus. Acertar todas as fáceis rende 1 por fácil
# (sem escala: partida longa tem mais fáceis, mas é mais difícil gabaritar). Sequências de
# acertos contam só médias e difíceis; de erros, qualquer nível (não responder é erro).
# A pergunta final não entra em nenhuma. Repetir uma sequência na mesma partida vale a metade
# (arredondada para longe do zero).
PERFECT_EASY_BONUS = 1
STREAK_BONUS = {3: 3, 5: 10, 10: 20}
WRONG_STREAK_PENALTY = {3: -5, 5: -10}
# Quem responde nos primeiros segundos leva o máximo; depois o valor cai até o mínimo.
SPEED_GRACE_SECONDS = 3.0
NO_ANSWER_PENALTY = -10

# Velocidade do efeito de digitação; o tempo de resposta só começa depois.
TYPING_SECONDS_PER_CHAR = 0.035
MIN_READING_SECONDS = 1.5
MAX_READING_SECONDS = 6.0
# Telas de preparação: antes da 1ª pergunta e antes da final (o tempo só começa depois).
START_SECONDS = 5.0
LEVEL_SECONDS = 3.0  # apresentação rápida quando a dificuldade muda
INTRO_SECONDS = 5.0
BET_SECONDS = 12.0
# O relógio do jogador começa quando o estado chega (atrasado pela rede) e o clique ainda
# precisa voltar: sem essa folga, quem clica no último instante fica sem resposta.
LATE_SECONDS = 1.0
PREPARATION_PHASES = ("starting", "level", "intro", "betting")
# O resultado fica na tela o suficiente para ler a curiosidade e armar uma habilidade;
# se todo mundo tocar em "Pular", acaba antes.
RESULTS_SECONDS_PER_CHAR = 0.055
MIN_RESULTS_SECONDS = 10.0
MAX_RESULTS_SECONDS = 15.0
# Aposta: uma vez por partida, antes da pergunta do meio das difíceis. Cada um aposta até
# metade do QI que tem (atalhos em porcentagem ou um valor digitado); acertou, ganha o valor;
# errou ou não respondeu, perde. Quem não aposta a tempo fica com 0.
BET_PERCENTS = (25, 50, 75, 100)
BET_MAX_PERCENT = 100  # com odd 1,5 dá para apostar tudo
BET_ODDS = 1.5  # odd decimal: apostou 100 e acertou, recebe 150 (lucro 50); errou, perde os 100


Phase = Literal["starting", "level", "intro", "betting", "reading", "answering", "results", "finished"]


class GameError(Exception):
    """Erro esperado, com mensagem pronta para mostrar ao jogador."""


class Question(BaseModel):
    id: str
    theme: str
    difficulty: Difficulty
    text: str
    options: list[str]
    answer: int = Field(ge=0)
    fact: str = Field(min_length=1)  # curiosidade ou explicação, mostrada depois da resposta

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
class Answer:
    option: int
    at: float


@dataclass
class Game:
    questions: list[Question]
    answer_seconds: float
    point_scale: float = 1.0  # ver point_scale()
    speed_grace_seconds: float = SPEED_GRACE_SECONDS
    round: int = -1  # índice da pergunta atual; -1 antes de começar
    phase: Phase = "reading"
    phase_started_at: float = 0
    phase_ends_at: float = 0
    answers: dict[str, Answer] = field(default_factory=dict)
    results: list[RoundResult] = field(default_factory=list)
    streaks: dict[str, Streak] = field(default_factory=dict)
    bets: dict[str, int] = field(default_factory=dict)  # só na rodada da aposta
    rng: random.Random = field(default_factory=random.Random)
    powers: bool = False
    powerup_max: int = powerups.MAX_HELD
    # Habilidades (ver powerups.py): guardadas, armadas para a próxima pergunta e valendo nesta.
    powerups: dict[str, list[PowerUp]] = field(default_factory=dict)
    starting_powerups: dict[str, PowerUp] = field(default_factory=dict)
    armed: dict[str, PowerUpUse] = field(default_factory=dict)
    active: list[PowerUpUse] = field(default_factory=list)
    hidden_options: dict[str, list[int]] = field(default_factory=dict)  # tiradas pelo 50/50
    first_wrong: dict[str, Answer] = field(default_factory=dict)  # Segunda chance: 1ª tentativa errada
    # Habilidades que duram mais de uma pergunta: perguntas comuns restantes de cada uma, por jogador.
    lasting: dict[str, dict[PowerUp, int]] = field(default_factory=dict)
    right_runs: dict[str, int] = field(default_factory=dict)  # acertos seguidos rumo à próxima
    last_runs: dict[str, int] = field(default_factory=dict)  # rodadas seguidas em último, longe
    ready: set[str] = field(default_factory=set)  # quem quer pular a revelação

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

    def deal_powerups(self, player_ids: list[str]) -> None:
        for pid in player_ids:
            kind = self.rng.choice(powerups.POWERUPS)
            self.powerups[pid] = [kind]
            self.starting_powerups[pid] = kind

    def arm(self, player_id: str, kind: PowerUp, target: str | None, player_ids: list[str]) -> None:
        if not self.can_arm:
            raise GameError("Agora não dá para usar habilidade.")
        if player_id in self.armed:
            raise GameError("Você já armou uma habilidade para a próxima pergunta.")
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
        held.remove(kind)
        self.armed[player_id] = PowerUpUse(kind=kind, by=player_id, target=target, reflected_by=None)

    def use_now(self, player_id: str, kind: PowerUp) -> None:
        """50/50 e Espiar: usados durante a pergunta, valem na hora."""
        if self.phase not in ("reading", "answering") or not self._counts_for_powers():
            raise GameError("Agora não dá para usar habilidade.")
        if kind not in powerups.INSTANT:
            raise GameError("Essa se arma na revelação.")
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
        return all(pid in self.ready for pid in player_ids)

    def start_round(self, now: float) -> None:
        self.round += 1
        self.answers = {}
        self.results = []
        self.bets = {}
        self.ready = set()
        self.first_wrong = {}
        self.hidden_options = {}
        armed = list(self.armed.values())
        self.armed = {}
        for use in armed:
            if use.kind in powerups.LASTING:
                self.lasting.setdefault(use.by, {})[use.kind] = powerups.LASTING[use.kind]
        reversers = {pid for pid in self.lasting if self._affects("reverse", pid)}
        self.active = powerups.reflect(armed, reversers)
        for use in self.active:
            if use.reflected_by:
                self.lasting[use.reflected_by].pop("reverse", None)
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
        if kind in powerups.LASTING:
            return self._counts_for_powers() and self.lasting.get(player_id, {}).get(kind, 0) > 0
        return any((use.target or use.by) == player_id for use in self._uses(kind))

    def _counts_for_powers(self) -> bool:
        """Pergunta comum, em que as habilidades valem (nem a aposta nem a final)."""
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
        grace = self.speed_grace_seconds
        if player_id in self._extra_time_ids():
            grace += powerups.EXTRA_GRACE_SECONDS
        return grace

    def deadline(self, player_id: str) -> float:
        return self.phase_started_at + self.answer_window(player_id)

    def answer(self, player_id: str, option: int, now: float) -> None:
        if self.phase != "answering" or now > self.deadline(player_id) + LATE_SECONDS:
            raise GameError("Agora não dá para responder.")
        if player_id in self.answers:
            raise GameError("Você já respondeu.")
        tried = self.first_wrong.get(player_id)
        if (
            not 0 <= option < len(self.question.options)
            or option in self.hidden_options.get(player_id, [])
            or (tried and tried.option == option)
        ):
            raise GameError("Alternativa inválida.")
        answer = Answer(option, min(now, self.deadline(player_id)))
        if option != self.question.answer and not tried and self._affects("second_chance", player_id):
            self.first_wrong[player_id] = answer
            self.lasting[player_id].pop("second_chance")
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
                delta *= powerups.DOUBLE_FACTOR
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
                    doubled=doubled,
                    first_option=first.option if first and answer is not first else None,
                    expired=[],
                    gained=None,
                )
            )
        by_id = {r.player_id: r for r in self.results}
        for use in self.active:
            thief, target = by_id.get(use.by), by_id.get(use.target or "")
            if use.kind != "steal" or not thief or not target:
                continue
            if target.delta < 0:
                thief.stolen += int(-target.delta * powerups.STEAL_LOSS_SHARE)
            elif target.delta > 0:
                share = int(target.delta * powerups.STEAL_GAIN_SHARE)
                thief.stolen += share
                target.robbed += share
        for player, result in zip(players, self.results):
            player.score += (
                result.delta + sum(b.delta for b in result.bonuses) + result.bet_delta + result.stolen - result.robbed
            )
        if self._counts_for_powers():
            self._wear_lasting()
        if self.powers and difficulty != FINAL_DIFFICULTY:
            self._powerup_gains(players)
        self._enter("results", now, results_seconds(self.question.fact))

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
                    if kind in powerups.BREAKABLE and result:
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
            if len(held) >= self.powerup_max:
                continue  # com as mãos cheias, a sequência continua valendo para depois
            kind = self.rng.choice(powerups.POWERUPS)
            held.append(kind)
            result.gained = PowerUpGain(kind=kind, reason=reason)
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
        silenced = bool(viewer) and not show_answer and self._affects("silence", viewer)
        peeking = bool(viewer) and self.phase == "answering" and self._affects("peek", viewer)
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
            else QuestionView(text=q.text, options=q.options, theme=q.theme, difficulty=q.difficulty),
            answered=[] if silenced else [*self.answers, *self.first_wrong.keys() - self.answers.keys()],
            bet_round=None if self.bet_round is None else self.bet_round + 1,
            bet_percents=list(BET_PERCENTS),
            bet_max_percent=BET_MAX_PERCENT,
            bet_odds=BET_ODDS,
            bets_placed=list(self.bets),
            powerups=list(self.powerups.get(viewer, [])) if viewer else [],
            powerup_max=self.powerup_max,
            starting_powerup=self.starting_powerups.get(viewer) if viewer else None,
            can_arm=self.can_arm,
            armed=self.armed.get(viewer) if viewer else None,
            active=self._visible_uses(viewer, show_answer),
            hidden_options=self.hidden_options.get(viewer, []) if viewer else [],
            first_wrong=self.first_wrong[viewer].option if viewer in self.first_wrong else None,
            peek=self._peek(viewer) if peeking else None,
            speed_grace_ms=round((self.grace_window(viewer) if viewer else self.speed_grace_seconds) * 1000),
            lasting=self._lasting_view(viewer) if viewer and not show_answer else [],
            powers_round=self._counts_for_powers(),
            ready=sorted(self.ready),
            correct_option=q.answer if show_answer else None,
            fact=q.fact if show_answer else None,
            results=self.results,
        )

    def _lasting_view(self, viewer: str) -> list[LastingPowerUp]:
        return [
            LastingPowerUp(kind=kind, rounds_left=left, total=powerups.LASTING[kind])
            for kind, left in self.lasting.get(viewer, {}).items()
            if self._affects(kind, viewer)
        ]

    def _peek(self, viewer: str) -> list[int]:
        """Primeira escolha de cada um dos outros, por alternativa."""
        counts = [0] * len(self.question.options)
        for pid, answer in {**self.answers, **self.first_wrong}.items():
            if pid != viewer:
                counts[answer.option] += 1
        return counts

    def _visible_uses(self, viewer: str | None, show_answer: bool) -> list[PowerUpUse]:
        """O roubo é surpresa: durante a pergunta só quem roubou sabe; o alvo descobre na revelação."""
        if show_answer:
            return self.active
        return [use for use in self.active if use.kind != "steal" or use.by == viewer]

    def _enter(self, phase: Phase, now: float, seconds: float):
        self.phase = phase
        self.phase_started_at = now
        self.phase_ends_at = now + seconds
