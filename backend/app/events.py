"""Contrato dos eventos trocados entre servidor e cliente via Socket.IO.

Todo payload enviado ao cliente é um modelo Pydantic registrado em EVENT_MODELS.
O front gera seus tipos TypeScript a partir daqui (scripts/export_schema.py).
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Os ids batem com os arquivos em frontend/src/assets/avatars/<id>.svg.
Avatar = Literal[
    "burro", "cachorro", "coelho", "coruja", "galinha", "gato", "leao", "macaco",
    "ovelha", "panda", "pinguim", "porco", "raposa", "sapo", "urso", "vaca",
]

Difficulty = Literal["easy", "medium", "hard", "impossible"]
PowerUp = Literal[
    "fifty_fifty", "shield", "double", "peek", "extra_time", "second_chance", "reverse",
    "backpack", "theme", "investment",
    "scratch", "steal", "scramble", "accelerator", "mirror", "silence", "magnifier", "toll", "decoy", "flashbang",
    "resurrection", "duel",
]
GameMode = Literal["classic", "powers", "last_standing"]
MODE_OPTIONS: tuple[GameMode, ...] = ("classic", "powers", "last_standing")
SurvivalKind = Literal["true_false", "choices"]  # Último de pé: Verdadeiro ou Falso ou Alternativas
SURVIVAL_KIND_OPTIONS: tuple[SurvivalKind, ...] = ("true_false", "choices")

NICKNAME_MAX_LENGTH = 16
ROUND_OPTIONS = (10, 15, 20, 25, 30, 35)
ANSWER_OPTIONS = (10, 15, 20, 25, 30)  # segundos para responder
GRACE_OPTIONS = (0, 2, 3, 5)  # segundos de QI cheio
POWERUP_MAX_OPTIONS = (1, 2, 3)


class Pong(BaseModel):
    server_time: float


# --- Cliente → servidor -------------------------------------------------------

class Profile(BaseModel):
    nickname: str = Field(min_length=1, max_length=NICKNAME_MAX_LENGTH)
    avatar: Avatar


class CreateRoomRequest(Profile):
    pass


class JoinRoomRequest(Profile):
    code: str


class RejoinRoomRequest(BaseModel):
    code: str
    token: str


class UpdateSettingsRequest(BaseModel):
    """Só os campos enviados mudam."""

    mode: GameMode | None = None
    survival_kind: SurvivalKind | None = None
    powerup_max: int | None = None
    rounds: int | None = None
    answer_seconds: float | None = None
    speed_grace_seconds: float | None = None
    themes: list[str] | None = None


class SubmitAnswerRequest(BaseModel):
    option: int


class SubmitBetRequest(BaseModel):
    amount: int = Field(ge=0)


class ArmPowerUpRequest(BaseModel):
    """Na revelação: a habilidade vale na próxima pergunta. `target` só nas que miram alguém."""

    kind: PowerUp
    target: str | None = None
    legendary: bool = False  # a versão lendária de um ataque: vale em todos os outros, sem alvo
    theme: str | None = None  # Tema: um dos temas sorteados em `theme_choices`


class SubmitDuelBetRequest(BaseModel):
    """X1: o id do duelista em quem a plateia aposta."""

    choice: str


class UsePowerUpRequest(BaseModel):
    """Durante a pergunta (50/50 e Espiar): vale na hora."""

    kind: PowerUp


# --- Servidor → cliente -------------------------------------------------------

class PlayerView(BaseModel):
    id: str
    nickname: str
    avatar: Avatar
    connected: bool
    score: int
    answer_ms: int  # tempo total de resposta; desempata quem tem o mesmo QI
    streak: int  # > 0: acertos seguidos em médias/difíceis; < 0: erros seguidos


class RoomSettings(BaseModel):
    mode: GameMode
    mode_options: list[GameMode]
    survival_kind: SurvivalKind
    survival_kind_options: list[SurvivalKind]
    powerup_max: int
    powerup_max_options: list[int]
    rounds: int
    answer_seconds: float
    speed_grace_seconds: float  # respostas até aqui valem o máximo
    round_options: list[int]
    answer_options: list[int]
    grace_options: list[int]
    themes: list[str]
    theme_options: list[str]


class QuestionView(BaseModel):
    text: str
    options: list[str]
    theme: str
    difficulty: Difficulty


class Bonus(BaseModel):
    """Bônus da partida: gabaritar as fáceis, sequências de acertos (positivo) e sequências
    de erros (negativo). Uma sequência repetida na mesma partida vale a metade."""

    kind: Literal["perfect_easy", "streak", "wrong_streak", "investment"]
    count: int  # quantas fáceis, o tamanho da sequência ou o acerto do Investimento
    delta: int
    repeat: bool


class PowerUpUse(BaseModel):
    kind: PowerUp
    by: str  # id de quem usou (no roubo rebatido, quem rebateu e agora rouba)
    target: str | None  # id do alvo; None nas que valem para quem usou
    reflected_by: str | None  # quem devolveu com o Reverso (o alvo original)
    legendary: bool = False  # ataque lendário: pega todos menos quem jogou (target None)
    theme: str | None = None  # Tema: o tema escolhido para a pergunta


class LastingPowerUp(BaseModel):
    """Habilidade que vale por algumas perguntas (Tempo extra, Escudo, Segunda chance, Reverso)."""

    kind: PowerUp
    rounds_left: int  # contando a pergunta atual
    total: int


class PowerUpGain(BaseModel):
    kind: PowerUp
    reason: Literal["start", "streak", "comeback"]  # sorteio inicial, acertos seguidos ou lanterna
    legendary: bool = False
    mythic: bool = False


class Revival(BaseModel):
    """Ressurreição usada nesta revelação: o QI de antes e o de depois."""

    player_id: str
    before: int
    after: int


class RoundResult(BaseModel):
    player_id: str
    option: int | None  # None = não respondeu
    correct: bool
    elapsed_ms: int | None  # quanto levou para responder; None = não respondeu
    delta: int  # pontos da resposta, sem os bônus e sem a aposta (0 se o escudo segurou)
    bonuses: list[Bonus]
    bet: int | None  # None fora da rodada da aposta; 0 = não apostou
    bet_delta: int  # +bet × (bet_odds - 1) (para baixo) se acertou, -bet se errou ou não respondeu
    shielded: int
    stolen: int
    robbed: int
    tolled: int  # QI pago de Pedágio
    toll_received: int  # QI recebido de Pedágio de outros
    decoy: str | None  # Alternativa falsa em que o jogador caiu
    tricked: int  # QI ganho com quem caiu na sua Alternativa falsa
    doubled: bool  # o delta já vem com o Dobro
    first_option: int | None  # Segunda chance: a primeira escolha, que estava errada
    expired: list[PowerUp]  # Escudo, Segunda chance ou Reverso que quebraram sem ser usados
    gained: PowerUpGain | None


class DuelPick(BaseModel):
    player_id: str
    option: int | None  # None = não respondeu
    correct: bool
    elapsed_ms: int | None


class DuelView(BaseModel):
    """X1 em andamento. Fases: duel_betting (a plateia aposta) → duel_answering → duel_results,
    pergunta a pergunta, até alguém perder → duel_end (o acerto de contas)."""

    challenger: str
    rival: str
    question_number: int  # começa em 1; 0 durante a aposta
    total_questions: int
    kind: Literal["true_false", "hard", "impossible"] | None
    text: str | None
    options: list[str]
    theme: str | None
    answered: list[str]  # quem dos dois já respondeu
    picks: list[DuelPick]  # o que os dois marcaram, só depois de fechar a pergunta
    correct_option: int | None
    fact: str | None
    total_ms: dict[str, int]  # tempo somado de cada um, que desempata no fim
    can_bet: bool  # quem vê pode apostar agora
    my_bet: str | None
    bets: dict[str, str]  # quem apostou em quem, só no fim
    winner: str | None
    loser: str | None
    paid: int  # QI que quem perdeu pagou a quem ganhou
    from_bets: int  # o que quem ganhou levou de quem apostou contra ele
    favorite_bonus: int


class DuelChallenge(BaseModel):
    challenger: str
    rival: str


class GameView(BaseModel):
    """Fases de cada rodada: reading (texto aparecendo, respostas bloqueadas) →
    answering → results. Telas de preparação, em que a pergunta não é enviada: starting
    (antes da 1ª pergunta), level (quando a dificuldade muda), betting (aposta, só com o
    tema à mostra) e intro (antes da final).
    Depois da última rodada: finished."""

    round: int  # começa em 1
    total_rounds: int
    phase: Literal[
        "starting", "level", "intro", "betting", "reading", "answering", "results", "finished",
        "duel_betting", "duel_answering", "duel_results", "duel_end",
    ]
    phase_duration_ms: int
    phase_ends_in_ms: int  # relativo ao envio, para não depender do relógio do celular
    difficulty: Difficulty  # da pergunta da rodada (enviada também nas telas de preparação)
    theme: str
    question: QuestionView | None  # None em starting, level e intro
    answered: list[str]
    bet_round: int | None  # rodada com aposta (começa em 1)
    bet_percents: list[int]  # atalhos de aposta, em % do QI
    bet_max_percent: int  # aposta máxima, em % do QI (arredondada para baixo)
    bet_odds: float
    bets_placed: list[str]  # ids de quem já apostou; os valores só aparecem em results
    powerups: list[PowerUp]
    legendary_powerups: list[PowerUp]  # os seus ataques lendários guardados (contam no máximo)
    mythic_powerups: list[PowerUp]  # os seus poderes míticos guardados (contam no máximo)
    revivals: list[Revival]
    duels: list[DuelChallenge]  # X1 chamados nesta revelação, na ordem em que vão acontecer
    duel: DuelView | None
    powerup_max: int
    starting_powerup: PowerUp | None
    can_arm: bool  # dá para armar habilidade agora (revelação antes de uma pergunta comum)
    armed: PowerUpUse | None
    active: list[PowerUpUse]  # habilidades valendo nesta pergunta (o roubo só aparece para os outros na revelação)
    hidden_options: list[int]
    first_wrong: int | None  # Segunda chance: a sua primeira escolha, errada; dá para tentar de novo
    peek: list[int] | None  # Espiar: quantos outros escolheram cada alternativa até agora
    speed_grace_ms: int  # o seu tempo de QI cheio nesta pergunta (Tempo extra aumenta, Acelerador zera)
    lasting: list[LastingPowerUp]
    silenced_rounds: int  # Silêncio em você: perguntas que faltam, contando a atual; 0 = livre
    tolls: list[int] | None  # Pedágio em você: quanto custa responder cada alternativa
    flashbang: bool  # Flashbang em você: alguns segundos depois de liberar as respostas, só as letras aparecem
    theme_choices: list[str]  # Tema: os temas que dá para escolher para a próxima pergunta
    powers_round: bool  # as habilidades valem nesta pergunta (nem a aposta nem a final)
    ready: list[str]
    correct_option: int | None  # só aparece em results
    fact: str | None
    results: list[RoundResult]


class SurvivalPick(BaseModel):
    player_id: str
    option: int | None  # None = não respondeu
    correct: bool
    elapsed_ms: int | None
    lost_life: bool


class Survivor(BaseModel):
    player_id: str
    lives: int
    out_round: int | None  # rodada em que caiu; None = ainda vivo
    correct: int
    answer_ms: int  # tempo total de resposta; desempata quem caiu na mesma rodada
    place: int | None  # só no fim


class SurvivalView(BaseModel):
    """Último de pé. Fases: starting → (reading → answering → results) por pergunta, com level
    quando o nível muda; quando sobram 2: duel_intro → (duel_reading → duel_answering →
    duel_results) até um perder → finished. No V ou F não tem leitura: a frase vai junto com as
    respostas."""

    kind: SurvivalKind
    phase: Literal[
        "starting", "level", "reading", "answering", "results",
        "duel_intro", "duel_reading", "duel_answering", "duel_results", "finished",
    ]
    phase_duration_ms: int
    phase_ends_in_ms: int
    round: int  # frase atual, começa em 1
    duel_round: int  # frase do X1, começa em 1; 0 antes do X1
    easy_count: int  # quantas fáceis no começo
    medium_count: int  # quantas médias antes das difíceis
    max_lives: int
    difficulty: Difficulty
    text: str | None
    theme: str | None
    options: list[str]
    answered: list[str]
    my_answer: int | None
    picks: list[SurvivalPick]  # só na revelação
    correct_option: int | None
    fact: str | None
    spared: bool  # todos os vivos erraram: ninguém perdeu vida
    duelists: list[str]  # os dois do X1; vazio antes
    next_seconds: float | None  # X1: tempo para responder a frase atual
    winner: str | None
    survivors: list[Survivor]


class RoomState(BaseModel):
    """Enviado no evento `room_state` sempre que a sala muda."""

    code: str
    status: Literal["lobby", "playing"]
    host_id: str
    max_players: int
    min_players: int
    settings: RoomSettings
    players: list[PlayerView]
    game: GameView | None
    survival: SurvivalView | None


class Ack(BaseModel):
    # Mantém `ok` obrigatório no TS, para o front distinguir sucesso de erro.
    model_config = ConfigDict(json_schema_serialization_defaults_required=True)


class JoinedAck(Ack):
    """Resposta de create_room, join_room e rejoin_room quando dá certo."""

    ok: Literal[True] = True
    player_id: str
    token: str
    room: RoomState


class OkAck(Ack):
    ok: Literal[True] = True


class ErrorAck(Ack):
    ok: Literal[False] = False
    error: str


EVENT_MODELS: list[type[BaseModel]] = [
    Pong,
    CreateRoomRequest,
    JoinRoomRequest,
    RejoinRoomRequest,
    UpdateSettingsRequest,
    SubmitAnswerRequest,
    SubmitBetRequest,
    SubmitDuelBetRequest,
    ArmPowerUpRequest,
    UsePowerUpRequest,
    RoomState,
    JoinedAck,
    OkAck,
    ErrorAck,
]
