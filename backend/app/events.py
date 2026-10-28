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
    "cold_water", "free_pass",  # só na Batata quente
    "mutiny", "infiltrator", "gag", "iron_captain", "tax",  # só nos Times
]
GameMode = Literal["classic", "powers", "last_standing", "hot_potato", "teams"]
MODE_OPTIONS: tuple[GameMode, ...] = ("classic", "powers", "teams", "last_standing", "hot_potato")
TeamPick = Literal["random", "host"]  # Times: sorteados no começo ou montados pelo anfitrião
TEAM_PICK_OPTIONS: tuple[TeamPick, ...] = ("random", "host")
TEAM_COUNT_OPTIONS = (2, 3, 4)
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
    survival_powers: bool | None = None
    team_count: int | None = None
    team_pick: TeamPick | None = None
    powerup_max: int | None = None
    rounds: int | None = None
    answer_seconds: float | None = None
    speed_grace_seconds: float | None = None
    themes: list[str] | None = None


class SetTeamRequest(BaseModel):
    """Times montados pelo anfitrião: põe um jogador num time (0 a team_count - 1)."""

    player_id: str
    team: int


class ChooseRepresentativeRequest(BaseModel):
    """Times: em quem do seu time você vota para ir sozinho na aposta ou na final."""

    choice: str


class SubmitAnswerRequest(BaseModel):
    option: int
    team: int | None = None  # Times: o Infiltrado votando no time adversário


class SubmitBetRequest(BaseModel):
    amount: int = Field(ge=0)


class ArmPowerUpRequest(BaseModel):
    """Na revelação: a habilidade vale na próxima pergunta. `target` só nas que miram alguém."""

    kind: PowerUp
    target: str | None = None
    legendary: bool = False  # a versão lendária de um ataque: vale em todos os outros, sem alvo
    theme: str | None = None  # Tema: um dos temas sorteados em `theme_choices`
    target_team: int | None = None  # Times: o time alvo


class SubmitDuelBetRequest(BaseModel):
    """X1: o id do duelista em quem a plateia aposta."""

    choice: str


class UsePowerUpRequest(BaseModel):
    """Durante a pergunta (50/50 e Espiar): vale na hora."""

    kind: PowerUp
    target_team: int | None = None  # Times: o time que o Espiar olha


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
    survival_powers: bool  # Último de pé, Batata quente e Times com poderes
    team_count: int
    team_count_options: list[int]
    team_pick: TeamPick
    team_pick_options: list[TeamPick]
    teams: dict[str, int]  # montados pelo anfitrião: id do jogador -> time; vazio no sorteio
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
    reason: Literal["start", "streak", "comeback", "ghost"]  # sorteio inicial, acertos seguidos, lanterna ou fantasma
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
    first_option: int | None = None  # Segunda chance: a primeira escolha, errada
    decoy: str | None = None  # Alternativa falsa em que caiu
    shielded: bool = False  # o Escudo segurou a vida
    stolen_by: str | None = None  # Roubo de vida: quem ficou com a vida perdida


class Gift(BaseModel):
    player_id: str
    gain: PowerUpGain


class Survivor(BaseModel):
    player_id: str
    lives: int  # -1 para quem está silenciado (não vê as vidas dos outros)
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
    # Com poderes: os mesmos campos do GameView, para o front usar os mesmos componentes.
    powers: bool
    powerups: list[PowerUp]
    legendary_powerups: list[PowerUp]  # sempre vazio: não tem lendário neste modo
    mythic_powerups: list[PowerUp]  # a Ressurreição dos fantasmas
    powerup_max: int
    starting_powerup: PowerUp | None
    can_arm: bool
    armed: PowerUpUse | None
    active: list[PowerUpUse]
    lasting: list[LastingPowerUp]
    hidden_options: list[int]
    first_wrong: int | None
    peek: list[int] | None
    flashbang: bool
    silenced_rounds: int
    theme_choices: list[str]
    powers_round: bool
    ready: list[str]
    revived: list[str]  # quem ressuscitou nesta revelação
    gifts: list[Gift]  # poderes ganhos nesta revelação


class HotPotatoTurn(BaseModel):
    """A última resposta de quem está com a batata."""

    player_id: str
    option: int | None  # None = Passe livre
    correct: bool
    correct_option: int
    elapsed_ms: int
    free_pass: bool = False  # passou sem responder
    shielded: bool = False  # errou, mas o Escudo segurou o pavio e a sequência de erros


class HotPotatoPlayer(BaseModel):
    player_id: str
    out_round: int | None  # rodada em que a batata explodiu na mão; None = na roda
    correct: int
    wrong: int
    place: int | None  # só no fim


class HotPotatoView(BaseModel):
    """Batata quente. Fases: starting → asking (quem está com a batata responde) → passing
    (acertou, a batata voa para o próximo) ou wrong (errou, outra pergunta) → … → exploded (o pavio
    acabou ou foram 3 erros seguidos) → asking da rodada seguinte … → finished."""

    phase: Literal["starting", "asking", "passing", "wrong", "exploded", "finished"]
    phase_duration_ms: int
    phase_ends_in_ms: int  # no asking, é o pavio: o front não deve mostrar
    round: int
    holder: str | None
    heat: float  # 0 a 1: quanto do pavio já queimou no envio
    burning: bool  # o pavio está queimando agora (para durante o passe e o erro)
    burn_per_second: float  # quanto o heat sobe por segundo enquanto queima
    wrong_streak: int
    max_wrong_streak: int
    penalty_seconds: float
    fuse_range: list[float]
    text: str | None
    theme: str | None
    difficulty: Difficulty | None
    options: list[str]
    turn: HotPotatoTurn | None
    exploded: str | None
    winner: str | None
    players: list[HotPotatoPlayer]
    direction: Literal[1, -1]  # 1 = sentido da roda; -1 = invertido
    # Com poderes. Ajudas: só quem está com a batata usa, na hora. Sabotagens: quem assiste joga em
    # quem está com a batata, valendo na pergunta atual.
    powers: bool
    powerups: list[PowerUp]
    mythic_powerups: list[PowerUp]  # a Ressurreição dos fantasmas
    powerup_max: int
    starting_powerup: PowerUp | None
    uses: list[PowerUpUse]  # poderes usados na pergunta atual
    hidden_options: list[int]  # 50/50 (de quem está com a batata; todos veem)
    first_wrong: int | None  # Segunda chance: a primeira escolha, errada
    shielded: list[str]  # quem está com o Escudo armado
    flashbang: bool  # Flashbang em você: só as letras das alternativas até a próxima pergunta
    gifts: list[Gift]  # poderes ganhos agora (no acerto ou na explosão)
    revived: list[str]  # quem ressuscitou desde a última pergunta


class TeamVote(BaseModel):
    player_id: str
    option: int | None  # na ordem da tela de quem vê; None = uma alternativa falsa que só o outro time viu
    infiltrator: bool = False  # voto do Infiltrado do outro time (vale 2)


class TeamPowerUse(BaseModel):
    kind: PowerUp
    by: str  # quem usou (o capitão)
    by_team: int
    target_team: int | None = None
    target_player: str | None = None  # Mordaça: quem fica sem votar; Infiltrado: quem se infiltra
    theme: str | None = None


class TeamSide(BaseModel):
    """Um time na partida. Os votos dos outros times só aparecem na revelação; antes, só quem já votou."""

    id: int  # 0 a 3: nome e cor do time
    members: list[str]
    score: int  # o QI do time
    captain: str | None  # capitão desta pergunta (o voto vale 2); None nas de representante
    representative: str | None  # quem responde sozinho na aposta e na final
    votes: list[TeamVote]
    voted: list[str]
    locked: bool  # o time já respondeu (todos votaram, ou o representante respondeu)
    option: int | None  # a resposta do time: a sua assim que trava; a dos outros na revelação
    choices: dict[str, str]  # escolha do representante: quem votou em quem (só no seu time)
    bet: int | None  # aposta do representante; a dos outros só na revelação
    harmony: int  # perguntas seguidas com todo mundo votando na certa, rumo ao bônus de Sintonia
    next_captain: str | None  # na revelação: o capitão da próxima, que escolhe o poder
    mutiny_left: int  # Motim: perguntas sem capitão que faltam
    iron: bool  # Capitão de ferro: só o capitão vota
    # Poderes do time (só do seu).
    powerups: list[PowerUp]
    mythic_powerups: list[PowerUp]
    powerup_max: int
    armed: TeamPowerUse | None
    lasting: list[LastingPowerUp]
    # Só na revelação:
    correct: bool | None
    decoy_pick: bool  # a resposta do time foi uma alternativa falsa
    delta: int  # pontos da pergunta (acerto, erro, ou sem resposta)
    captain_delta: int
    harmony_delta: int
    bet_delta: int
    shielded: int  # o que o Escudo segurou
    doubled: bool
    second_chance: bool  # acertou na segunda tentativa (vale metade)
    stolen: int  # Roubo: o que este time levou
    robbed: int  # Roubo: o que tiraram deste time
    tolled: int  # Pedágio pago
    toll_received: int
    tricked: int  # Alternativa falsa: o que este time ganhou com quem caiu
    tax: int  # Imposto: + quem recebeu, − quem pagou
    duel_delta: int
    gained: PowerUpGain | None


class TeamPlayerStat(BaseModel):
    player_id: str
    team: int
    votes: int  # perguntas em que votou
    right: int  # votos na certa
    captain_right: int
    captain_rounds: int
    represented: int  # vezes que foi representante
    represented_right: int


class TeamMatchView(BaseModel):
    """Times: o time responde junto, por votos, e tem um QI só. Fases: starting → (level) →
    reading → answering → results por pergunta; na aposta e na final, antes vem choosing (o time
    escolhe o representante) e, na aposta, betting. Depois da última: finished."""

    phase: Literal[
        "starting", "level", "choosing", "betting", "intro", "reading", "answering", "results", "finished",
        "duel_choosing", "duel_betting", "duel_answering", "duel_results", "duel_end",
    ]
    phase_duration_ms: int
    phase_ends_in_ms: int
    round: int  # começa em 1
    total_rounds: int
    solo: bool  # pergunta de representante (aposta ou final)
    bet_round: bool
    difficulty: Difficulty
    theme: str
    question: QuestionView | None
    correct_option: int | None
    fact: str | None
    bet_percents: list[int]
    bet_max_percent: int
    bet_odds: float
    captain_bonus: int
    harmony_streak: int
    harmony_bonus: int
    teams: list[TeamSide]
    my_team: int | None
    stats: list[TeamPlayerStat]
    ready: list[str]
    # Poderes (a mão de cada time fica no TeamSide dele).
    powers: bool
    can_arm: bool  # você pode escolher o poder do seu time agora
    can_use: bool  # você pode usar 50/50 ou Espiar agora
    uses: list[TeamPowerUse]  # poderes valendo nesta pergunta que você pode ver
    theme_choices: list[str]
    hidden_options: list[int]  # 50/50 do seu time
    first_wrong: int | None  # Segunda chance: a primeira resposta errada do seu time
    tolls: list[int] | None  # Pedágio no seu time: preço de cada alternativa
    gagged: bool  # Mordaça em você
    infiltrating: int | None  # você é o Infiltrado neste time
    infiltrate_question: QuestionView | None  # a pergunta como o time infiltrado vê
    effects: list[PowerUp]  # sabotagens visuais no seu time (Embaralhar, Espelho, Lupa, Raspadinha, Flashbang)
    silenced: bool  # Silêncio no seu time: você não vê o voto dos colegas
    peeking: int | None  # Espiar: o time cujos votos você está vendo
    duel: DuelView | None
    duel_teams: list[int]  # os dois times do X1


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
    hot_potato: HotPotatoView | None
    team_match: TeamMatchView | None


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
    SetTeamRequest,
    ChooseRepresentativeRequest,
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
