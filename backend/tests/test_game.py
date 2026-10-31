import random
from dataclasses import dataclass

import pytest

from app import duel as x1
from app import powerups
from app.events import PowerUpGain
from app.game import (
    MAX_READING_SECONDS,
    MAX_RESULTS_SECONDS,
    MIN_RESULTS_SECONDS,
    MIN_READING_SECONDS,
    BET_SECONDS,
    LATE_SECONDS,
    Game,
    GameError,
    Question,
    bet_round,
    bet_win,
    load_bank,
    max_bet,
    pick_questions,
    point_scale,
    points,
    reading_seconds,
    results_seconds,
    split_by_difficulty,
)


@dataclass
class P:
    id: str
    score: int = 0
    answer_ms: int = 0
    streak: int = 0


def question(qid: str, difficulty: str = "easy", answer: int = 0) -> Question:
    return Question(
        id=qid,
        theme="Teste",
        difficulty=difficulty,
        text="Quanto é 1+1?",
        options=["2", "3", "4", "5"],
        answer=answer,
        fact="Dois é o único primo par.",
    )


def test_points_follow_the_rules():
    assert points("easy", True, 1) == 0  # fácil não dá QI, só tira
    assert points("medium", True, 1) == 11
    assert points("medium", True, 0) == 5
    assert points("hard", True, 1) == 22
    assert points("hard", True, 0.5) == 18
    assert points("hard", True, 0) == 13
    assert points("impossible", True, 1) == 35
    assert points("impossible", True, 0) == 35  # sem bônus de tempo
    assert points("easy", False) == -15
    assert points("medium", False) == -10
    assert points("hard", False) == -5
    assert points("impossible", False) == 0
    assert points("easy", None) == -10


def test_split_by_difficulty():
    assert split_by_difficulty(15) == {"easy": 5, "medium": 5, "hard": 5}
    assert split_by_difficulty(10) == {"easy": 3, "medium": 3, "hard": 4}
    assert split_by_difficulty(20) == {"easy": 6, "medium": 7, "hard": 7}
    assert split_by_difficulty(35) == {"easy": 11, "medium": 12, "hard": 12}
    assert split_by_difficulty(25) == {"easy": 8, "medium": 8, "hard": 9}


def test_bank_is_valid_and_has_every_difficulty():
    bank = load_bank()
    assert len({q.id for q in bank}) == len(bank)
    assert len({q.text for q in bank}) == len(bank), "pergunta repetida"
    for difficulty in ("easy", "medium", "hard"):
        assert sum(q.difficulty == difficulty for q in bank) >= 10  # o máximo de rodadas é 30
    assert sum(q.difficulty == "impossible" for q in bank) >= 1
    for q in bank:
        assert len(set(q.options)) == len(q.options), q.id


def test_pick_questions_goes_from_easy_to_hard_and_avoids_used():
    bank = load_bank()
    first = pick_questions(bank, 15, set(), random.Random(1))
    assert [q.difficulty for q in first] == ["easy"] * 5 + ["medium"] * 5 + ["hard"] * 5 + ["impossible"]
    assert len(first[-1].options) == 6

    second = pick_questions(bank, 15, {q.id for q in first}, random.Random(2))
    assert not {q.id for q in first} & {q.id for q in second}


def test_pick_questions_keeps_the_right_answer_after_shuffling():
    original = {q.id: q for q in load_bank()}
    for q in pick_questions(list(original.values()), 30, set(), random.Random(3)):
        source = original[q.id]
        assert q.options[q.answer] == source.options[source.answer]


def test_without_impossible_questions_the_game_uses_only_the_three_levels():
    bank = [q for q in load_bank() if q.difficulty != "impossible"]
    picked = pick_questions(bank, 15, set(), random.Random(4))
    assert [q.difficulty for q in picked] == ["easy"] * 5 + ["medium"] * 5 + ["hard"] * 5


def test_question_needs_the_right_number_of_options():
    with pytest.raises(ValueError, match="6 alternativas"):
        Question(id="x", theme="T", difficulty="impossible", text="?", options=["a", "b", "c", "d"], answer=0, fact="f")
    with pytest.raises(ValueError, match="4 alternativas"):
        Question(id="x", theme="T", difficulty="easy", text="?", options=list("abcdef"), answer=0, fact="f")


def test_reading_time_grows_with_text_but_is_capped():
    assert reading_seconds("Oi?") == MIN_READING_SECONDS
    assert reading_seconds("x" * 1000) == MAX_READING_SECONDS


def test_round_flow_and_scoring():
    game = Game(questions=[question("q1", "medium", answer=2)], answer_seconds=10)
    ana, bia, caio = P("ana"), P("bia"), P("caio")

    game.start_round(now=0)
    game.begin_reading(now=0)  # pula a contagem de abertura
    assert game.phase == "reading"
    with pytest.raises(GameError):
        game.answer("ana", 2, now=0.5)  # bloqueado enquanto o texto aparece

    game.open_answers(now=2)
    game.answer("ana", 2, now=4)  # certa, 2 s depois de liberar: dentro da carência
    game.answer("bia", 0, now=5)  # errada
    with pytest.raises(GameError, match="já respondeu"):
        game.answer("ana", 1, now=5)
    assert not game.everyone_answered(["ana", "bia", "caio"])

    game.close_round([ana, bia, caio], now=12)
    assert (ana.score, bia.score, caio.score) == (11, -10, -10)
    assert (ana.answer_ms, bia.answer_ms, caio.answer_ms) == (2000, 3000, 10000)
    view = game.view(now=12)
    assert view.correct_option == 2
    assert view.fact == "Dois é o único primo par."
    assert not game.has_next_round


def play(game: Game, players: list[P], picks: dict[str, int | None]) -> dict[str, list[tuple[str, int, int]]]:
    """Joga a próxima rodada inteira; picks: alternativa de cada jogador (None = não respondeu).
    Devolve os bônus de cada um como (tipo, contagem, pontos)."""
    game.round += 1
    game.answers = {}
    game.open_answers(now=0)
    for pid, option in picks.items():
        if option is not None:
            game.answer(pid, option, now=1)
    game.close_round(players, now=20)
    return {r.player_id: [(b.kind, b.count, b.delta) for b in r.bonuses] for r in game.results}


def test_perfect_easy_bonus_comes_on_the_last_easy_question():
    game = Game(questions=[question(f"e{i}") for i in range(3)] + [question("m", "medium")], answer_seconds=10)
    ana, bia = P("ana"), P("bia")
    assert play(game, [ana, bia], {"ana": 0, "bia": 1}) == {"ana": [], "bia": []}
    assert play(game, [ana, bia], {"ana": 0, "bia": 0}) == {"ana": [], "bia": []}
    assert play(game, [ana, bia], {"ana": 0, "bia": 0}) == {"ana": [("perfect_easy", 3, 3)], "bia": []}
    assert ana.score == 3


def test_right_streaks_count_medium_and_hard_and_repeats_pay_half():
    qs = [question(f"m{i}", "medium") for i in range(4)] + [question(f"h{i}", "hard") for i in range(4)]
    game = Game(questions=qs, answer_seconds=10)
    ana = P("ana")
    got = [play(game, [ana], {"ana": 0})["ana"] for _ in range(3)]
    assert got == [[], [], [("streak", 3, 3)]] and ana.streak == 3
    assert play(game, [ana], {"ana": 1})["ana"] == [] and ana.streak == -1  # errou: zera
    got = [play(game, [ana], {"ana": 0})["ana"] for _ in range(3)]
    assert got == [[], [], [("streak", 3, 2)]]  # repetida: metade de 3, arredondada para cima
    assert ana.streak == 3


def test_wrong_streaks_take_iq_and_no_answer_counts_as_wrong():
    game = Game(questions=[question(f"e{i}") for i in range(6)], answer_seconds=10, point_scale=2)
    bia = P("bia")
    got = [play(game, [bia], {"bia": pick})["bia"] for pick in (1, None, 1, 1, 1, 0)]
    assert got == [[], [], [("wrong_streak", 3, -10)], [], [("wrong_streak", 5, -20)], []]  # escala 2
    assert bia.streak == 0


def test_repeated_wrong_streak_takes_half():
    game = Game(questions=[question(f"e{i}") for i in range(7)], answer_seconds=10)
    bia = P("bia")
    got = [play(game, [bia], {"bia": pick})["bia"] for pick in (1, 1, 1, 0, 1, 1, 1)]
    assert got[2] == [("wrong_streak", 3, -5)] and got[6] == [("wrong_streak", 3, -3)]


def test_final_question_does_not_touch_streaks():
    final = Question(id="i", theme="T", difficulty="impossible", text="?", options=list("abcdef"), answer=0, fact="f")
    game = Game(questions=[question("m", "medium"), final], answer_seconds=10)
    ana = P("ana")
    play(game, [ana], {"ana": 0})
    assert play(game, [ana], {"ana": 1})["ana"] == [] and ana.streak == 1


def test_speed_bonus_starts_decaying_after_the_grace_period():
    game = Game(questions=[question("q1", "hard")], answer_seconds=10)
    assert game.speed_fraction(0) == game.speed_fraction(3) == 1
    assert game.speed_fraction(6.5) == 0.5
    assert game.speed_fraction(10) == 0
    assert points("hard", True, game.speed_fraction(6.5)) == 18


def test_shorter_matches_are_worth_more_per_question():
    assert point_scale(20) == 1 and point_scale(10) == 2
    assert points("hard", True, 1, scale=point_scale(10)) == 44
    assert points("medium", False, scale=point_scale(35)) == -6
    assert points("impossible", True, 1, scale=point_scale(10)) == 35  # a final não muda


def test_game_opens_with_a_countdown_before_the_first_question():
    game = Game(questions=[question("q1"), question("q2")], answer_seconds=10)
    game.start_round(now=0)
    assert game.view(now=1).phase == "starting" and game.view(now=1).question is None
    game.begin_reading(now=5)
    assert game.view(now=5).phase == "reading"
    game.open_answers(now=6)
    game.close_round([], now=16)
    game.start_round(now=20)
    assert game.view(now=20).phase == "reading"  # só a 1ª rodada tem a contagem


def test_level_change_gets_a_short_presentation():
    game = Game(questions=[question("e1"), question("e2"), question("m1", "medium")], answer_seconds=10)
    game.round = 0  # pula a contagem de abertura
    game.start_round(now=0)
    assert game.phase == "reading"  # mesma dificuldade: direto
    game.start_round(now=10)
    view = game.view(now=10)
    assert view.phase == "level" and view.difficulty == "medium" and view.question is None


def test_final_question_starts_with_an_intro_without_the_question():
    final = Question(
        id="f", theme="T", difficulty="impossible", text="?", options=list("abcdef"), answer=0, fact="f"
    )
    game = Game(questions=[question("q1"), final], answer_seconds=10)
    game.round = 0  # pula a contagem de abertura
    game.start_round(now=0)
    view = game.view(now=1)
    assert view.phase == "intro" and view.question is None
    with pytest.raises(GameError):
        game.answer("ana", 0, now=1)
    game.begin_reading(now=4)
    assert game.view(now=4).question.text == "?"


def test_answer_after_deadline_is_rejected():
    game = Game(questions=[question("q1")], answer_seconds=10)
    game.start_round(now=0)
    game.open_answers(now=1)
    with pytest.raises(GameError):
        game.answer("ana", 0, now=11 + LATE_SECONDS + 0.1)


def test_last_instant_clicks_still_count_despite_the_network():
    game = Game(questions=[question("q1")], answer_seconds=10)
    game.start_round(now=0)
    game.open_answers(now=1)
    game.answer("ana", 0, now=11 + LATE_SECONDS / 2)  # clicou com 0 s na tela, chegou atrasado
    ana = P("ana", 0)
    game.close_round([ana], now=11 + LATE_SECONDS)
    assert game.results[0].correct and game.results[0].option == 0  # vale como resposta no fim do tempo


def test_results_last_longer_for_longer_facts():
    assert results_seconds("Curta.") == MIN_RESULTS_SECONDS
    assert results_seconds("x" * 1000) == MAX_RESULTS_SECONDS
    assert MIN_RESULTS_SECONDS < results_seconds("x" * 100) < MAX_RESULTS_SECONDS


def test_view_hides_answer_until_results():
    game = Game(questions=[question("q1")], answer_seconds=10)
    game.start_round(now=0)
    game.begin_reading(now=0)
    view = game.view(now=0.5)
    assert view.correct_option is None
    assert view.fact is None
    assert view.round == 1 and view.total_rounds == 1
    assert view.phase_ends_in_ms == round((reading_seconds("Quanto é 1+1?") - 0.5) * 1000)


def test_bet_comes_before_the_middle_hard_question():
    qs = [question("e"), question("m", "medium")] + [question(f"h{i}", "hard") for i in range(6)]
    assert bet_round(qs) == 2 + 3  # 6 difíceis: a 4ª
    assert bet_round([question("h", "hard")]) == 0
    assert bet_round([question("e")]) is None


def test_bet_is_capped_at_the_whole_iq():
    assert max_bet(150) == 150 and max_bet(51) == 51
    assert max_bet(0) == max_bet(-20) == 0


def test_bet_pays_odds_of_one_and_a_half():
    assert bet_win(100) == 50 and bet_win(25) == 12 and bet_win(1) == 0


def test_betting_phase_shows_only_the_theme():
    qs = [question("h0", "hard"), question("h1", "hard")]
    game = Game(questions=qs, answer_seconds=10)
    game.round = 0
    game.start_round(now=0)
    view = game.view(now=1)
    assert view.phase == "betting" and view.question is None and view.theme == "Teste"
    assert game.phase_ends_at == BET_SECONDS
    assert view.bet_round == 2


def test_bets_pay_on_right_answers_and_cost_on_wrong_or_missing_ones():
    qs = [question("h0", "hard"), question("h1", "hard")]
    game = Game(questions=qs, answer_seconds=10)
    ana, bia, caio, dani = P("ana", 100), P("bia", 100), P("caio", 100), P("dani", -5)
    game.round = 0
    game.start_round(now=0)
    with pytest.raises(GameError, match="0 a 100"):
        game.bet(ana, 101, now=1)
    game.bet(ana, 50, now=1)
    with pytest.raises(GameError, match="já apostou"):
        game.bet(ana, 10, now=1)
    game.bet(bia, 25, now=1)
    assert not game.everyone_bet([ana, bia, caio, dani])
    game.bet(caio, 10, now=2)
    assert game.everyone_bet([ana, bia, caio, dani])  # dani não tem QI para apostar
    assert game.view(now=2).bets_placed == ["ana", "bia", "caio"]
    with pytest.raises(GameError):
        game.bet(dani, 0, now=BET_SECONDS + LATE_SECONDS + 1)  # fora da fase

    game.begin_reading(now=3)
    game.open_answers(now=4)
    game.answer("ana", 0, now=5)  # certa, na carência: +22
    game.answer("bia", 1, now=5)  # errada: -5
    game.close_round([ana, bia, caio, dani], now=14)
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["ana"].bet, by_id["ana"].bet_delta, ana.score) == (50, 25, 147)
    assert (by_id["bia"].bet, by_id["bia"].bet_delta, bia.score) == (25, -25, 70)
    assert (by_id["caio"].bet, by_id["caio"].bet_delta, caio.score) == (10, -10, 80)  # não respondeu
    assert (by_id["dani"].bet, by_id["dani"].bet_delta) == (0, 0)


def test_other_rounds_have_no_bet():
    game = Game(questions=[question("h0", "hard"), question("h1", "hard")], answer_seconds=10)
    ana = P("ana", 100)
    play(game, [ana], {"ana": 0})
    assert game.results[0].bet is None
    game.start_round(now=0)  # round 1 = aposta
    assert game.phase == "betting"


def reveal(game: Game, players: list[P], picks: dict[str, int | None]) -> None:
    """Abre a próxima rodada pelo caminho normal (ativando as habilidades armadas) e revela."""
    game.start_round(now=0)
    game.open_answers(now=0)
    for pid, option in picks.items():
        if option is not None:
            game.answer(pid, option, now=1)
    game.close_round(players, now=20)


def test_everyone_starts_with_one_random_powerup():
    game = Game(powers=True, questions=[question("q")], answer_seconds=10, rng=random.Random(1))
    game.deal_powerups(["ana", "bia"])
    for pid in ("ana", "bia"):
        view = game.view(now=0, viewer=pid)
        assert len(view.powerups) == 1 and view.starting_powerup == view.powerups[0]
    assert game.view(now=0).powerups == []  # ninguém vê as habilidades dos outros


def test_powerups_are_armed_on_the_reveal_and_count_on_the_next_question():
    game = Game(powers=True, questions=[question("e0"), question("e1")], answer_seconds=10)
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": ["shield", "steal"], "bia": []}
    with pytest.raises(GameError, match="Agora não"):
        game.arm("ana", "shield", None, ["ana", "bia"])  # ainda não é a revelação
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    assert game.can_arm
    with pytest.raises(GameError, match="não tem"):
        game.arm("bia", "shield", None, ["ana", "bia"])
    with pytest.raises(GameError, match="Escolha em quem"):
        game.arm("ana", "steal", "ana", ["ana", "bia"])
    game.arm("ana", "steal", "bia", ["ana", "bia"])
    with pytest.raises(GameError, match="já armou"):
        game.arm("ana", "shield", None, ["ana", "bia"])
    assert game.view(now=0, viewer="ana").powerups == ["shield"]
    assert game.view(now=0, viewer="ana").armed.target == "bia"
    assert game.view(now=0, viewer="bia").armed is None

    reveal(game, [ana, bia], {"ana": 0, "bia": 1})  # bia erra a fácil: -15, e ana leva 10 dela
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["ana"].stolen, ana.score) == (10, 62)  # + 2 de gabaritar as fáceis
    assert (by_id["bia"].delta, by_id["bia"].robbed, bia.score) == (-15, 10, 25)
    assert not game.can_arm  # acabou a partida


def test_steal_takes_ten_plus_half_of_a_right_answer_from_the_target():
    game = Game(powers=True, questions=[question("m0", "medium"), question("m1", "medium")], answer_seconds=10)
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": ["steal"], "bia": []}
    reveal(game, [ana, bia], {"ana": 1, "bia": 1})  # os dois erram a média: -10
    game.arm("ana", "steal", "bia", ["ana", "bia"])
    game.start_round(now=0)
    assert game.view(now=0, viewer="bia").active == []  # o alvo só descobre na revelação
    assert [u.kind for u in game.view(now=0, viewer="ana").active] == ["steal"]
    game.open_answers(now=0)
    game.answer("ana", 1, now=1)
    game.answer("bia", 0, now=1)  # bia acerta na carência: +11, ana leva 10 + 5
    game.close_round([ana, bia], now=20)
    assert [u.kind for u in game.view(now=20, viewer="bia").active] == ["steal"]
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["bia"].delta, by_id["bia"].robbed, bia.score) == (11, 15, 36)
    assert (by_id["ana"].stolen, ana.score) == (15, 45)  # errou: -10, +15 roubados


def test_shield_holds_the_penalty_and_blocks_a_steal():
    game = Game(powers=True, questions=[question("e0"), question("e1")], answer_seconds=10)
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": ["steal"], "bia": ["shield"]}
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    game.arm("ana", "steal", "bia", ["ana", "bia"])
    game.arm("bia", "shield", None, ["ana", "bia"])
    reveal(game, [ana, bia], {"ana": 0, "bia": None})
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["bia"].delta, by_id["bia"].shielded, bia.score) == (0, 10, 50)
    assert (by_id["ana"].stolen, ana.score) == (0, 52)  # só o bônus das fáceis


def test_fifty_fifty_is_used_during_the_question_and_only_for_who_used_it():
    game = Game(powers=True, questions=[question("e0"), question("e1", answer=3)], answer_seconds=10)
    ana, bia = P("ana"), P("bia")
    game.powerups = {"ana": ["fifty_fifty"]}
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    with pytest.raises(GameError, match="na hora da pergunta"):
        game.arm("ana", "fifty_fifty", None, ["ana", "bia"])
    game.start_round(now=0)
    game.use_now("ana", "fifty_fifty")  # ainda lendo: já vale
    hidden = game.view(now=0, viewer="ana").hidden_options
    assert len(hidden) == 2 and 3 not in hidden and game.powerups["ana"] == []
    assert game.view(now=0, viewer="bia").hidden_options == []
    assert [u.kind for u in game.view(now=0, viewer="bia").active] == ["fifty_fifty"]  # todo mundo vê o anúncio
    game.open_answers(now=0)
    with pytest.raises(GameError, match="inválida"):
        game.answer("ana", hidden[0], now=1)
    game.answer("ana", 3, now=1)
    with pytest.raises(GameError, match="não tem"):
        game.use_now("ana", "fifty_fifty")

def test_no_powerups_before_the_bet_or_the_final():
    qs = [question("h0", "hard"), question("h1", "hard")]
    qs.append(Question(id="x", theme="T", difficulty="impossible", text="?", options=list("abcdef"), answer=0, fact="f"))
    game = Game(powers=True, questions=qs, answer_seconds=10)
    ana = P("ana", 100)
    game.powerups = {"ana": ["shield"]}
    play(game, [ana], {"ana": 0})
    assert game.bet_round == 1 and not game.can_arm
    play(game, [ana], {"ana": 0})
    assert not game.can_arm  # a próxima é a final


def test_three_right_in_a_row_earns_a_powerup_up_to_two():
    game = Game(powers=True, questions=[question(f"e{i}") for i in range(7)], answer_seconds=10, rng=random.Random(1))
    ana = P("ana")
    game.powerups = {"ana": []}
    gains = []
    for _ in range(7):
        play(game, [ana], {"ana": 0})
        gains.append(game.results[0].gained)
    assert [g is not None for g in gains] == [False, False, True, False, False, True, False]
    assert gains[2].reason == "streak"
    assert len(game.powerups["ana"]) + len(game.legendaries["ana"]) == 2  # cheio: o 3º não vem


def test_far_behind_last_place_earns_a_powerup_every_three_rounds():
    game = Game(powers=True, questions=[question(f"e{i}") for i in range(4)], answer_seconds=10)
    ana, bia, caio = P("ana", 100), P("bia", 80), P("caio", 0)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    for _ in range(3):
        play(game, [ana, bia, caio], {"ana": 1, "bia": 1, "caio": 1})  # todos erram
    caio_gain = next(r.gained for r in game.results if r.player_id == "caio")
    assert caio_gain is not None and caio_gain.reason == "comeback"
    assert all(r.gained is None for r in game.results if r.player_id != "caio")


def test_trailing_needs_a_big_gap_to_the_top_two():
    from app.powerups import trailing

    assert trailing([P("a", 100), P("b", 90), P("c", 50)]) == {"c"}
    assert trailing([P("a", 100), P("b", 60), P("c", 40)]) == {"c"}  # 20 atrás já conta
    assert trailing([P("a", 100), P("b", 55), P("c", 40)]) == set()  # perto do 2º
    assert trailing([P("a", 100), P("b", 40)]) == {"b"}  # com 2, compara com o 1º


class LuckyRng(random.Random):
    """Sempre tira a lendária (random() = 0) e a primeira opção de cada sorteio."""

    def random(self) -> float:
        return 0.0

    def choice(self, seq):
        return seq[0]


class Roll(LuckyRng):
    """Sorteio de raridade fixo em `roll`; o resto como o LuckyRng."""

    def __init__(self, roll: float) -> None:
        super().__init__()
        self.roll = roll

    def random(self) -> float:
        return self.roll


def test_gains_can_be_legendary_attacks_more_often_for_the_far_behind_last():
    game = Game(powers=True, questions=[question(f"e{i}") for i in range(4)], answer_seconds=10, rng=Roll(0.05))
    ana, bia, caio = P("ana", 100), P("bia", 80), P("caio", 0)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    for _ in range(3):
        play(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 1})
    gains = {r.player_id: r.gained for r in game.results}
    assert gains["ana"] == PowerUpGain(kind="accelerator", reason="streak", legendary=True)
    assert gains["caio"] == PowerUpGain(kind="resurrection", reason="comeback", mythic=True)
    assert game.legendaries["ana"] == ["accelerator"] and game.powerups["ana"] == []
    assert game.view(now=0, viewer="ana").legendary_powerups == ["accelerator"]

    # Lanterna: Ressurreição até 6%, X1 até 14%, lendária até 34%. Os outros: X1 até 2%, lendária até 8%.
    for roll, behind, kind in (
        (0.01, False, "duel"), (0.04, False, "legendary"), (0.1, False, None),
        (0.03, True, "resurrection"), (0.1, True, "duel"), (0.2, True, "legendary"), (0.4, True, None),
    ):
        game = Game(powers=True, questions=[question(f"e{i}") for i in range(4)], answer_seconds=10, rng=Roll(roll))
        ana, bia = P("ana", 0 if behind else 100), P("bia", 100 if behind else 0)
        game.powerups = {"ana": [], "bia": []}
        for _ in range(3):
            play(game, [ana, bia], {"ana": 0, "bia": 1})
        gained = game.results[0].gained
        got = gained.kind if gained.mythic else "legendary" if gained.legendary else None
        assert got == kind, (roll, behind)


def test_legendary_attack_hits_everyone_else_and_ignores_the_reverse():
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10)
    ana, bia, caio = P("ana", 50), P("bia", 50), P("caio", 50)
    game.powerups = {"ana": [], "bia": ["reverse"], "caio": []}
    game.legendaries = {"ana": ["mirror"]}
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 1, "caio": 0})  # bia fora do 1º: Reverso de 3
    with pytest.raises(GameError, match="não tem"):
        game.arm("ana", "scratch", None, ["ana", "bia", "caio"], legendary=True)
    game.arm("ana", "mirror", None, ["ana", "bia", "caio"], legendary=True)
    game.arm("bia", "reverse", None, ["ana", "bia", "caio"])
    assert game.legendaries["ana"] == []
    game.start_round(now=0)
    assert [(u.kind, u.target, u.legendary) for u in game.active if u.kind == "mirror"] == [("mirror", None, True)]
    assert game._affects("mirror", "bia") and game._affects("mirror", "caio") and not game._affects("mirror", "ana")
    assert game.lasting["bia"]["reverse"] == 3  # não segurou: continua guardado


def test_legendary_steal_splits_one_and_a_half_steals_with_more_from_the_leader():
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10)
    ana, bia, caio, davi = P("ana", 50), P("bia", 50), P("caio", 50), P("davi", 50)
    game.powerups = {"ana": [], "bia": [], "caio": [], "davi": []}
    game.legendaries = {"ana": ["steal"]}
    everyone = ["ana", "bia", "caio", "davi"]
    reveal(game, [ana, bia, caio, davi], {"ana": 0, "bia": 0, "caio": 1, "davi": 1})  # bia fica em 1º
    game.arm("ana", "steal", None, everyone, legendary=True)
    # bia acerta +11 (parte de 10 + 5), caio e davi erram (10 cada): pote = 1,5 × 35/3 = 17,5
    reveal(game, [ana, bia, caio, davi], {"ana": 1, "bia": 0, "caio": 1, "davi": 1})
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["bia"].robbed, by_id["caio"].robbed, by_id["davi"].robbed) == (9, 4, 4)  # bia pesa 2
    assert by_id["ana"].stolen == 17


def test_legendary_steal_skips_a_shield_that_held_an_error():
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10)
    ana, bia, caio = P("ana", 50), P("bia", 50), P("caio", 50)
    game.powerups = {"ana": [], "bia": [], "caio": ["shield"]}
    game.legendaries = {"ana": ["steal"]}
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    game.arm("ana", "steal", None, ["ana", "bia", "caio"], legendary=True)
    game.arm("caio", "shield", None, ["ana", "bia", "caio"])
    reveal(game, [ana, bia, caio], {"ana": 1, "bia": 0, "caio": 1})  # bia acerta +11; caio erra com escudo
    by_id = {r.player_id: r for r in game.results}
    # pote = 1,5 × (15 + 10) / 2 = 18,75, empatados em 1º: metade para cada; a do caio se perde
    assert by_id["bia"].robbed == 9 and by_id["caio"].robbed == 0
    assert by_id["ana"].stolen == 9


def test_everyone_ready_skips_the_reveal():
    game = Game(powers=True, questions=[question("e0"), question("e1")], answer_seconds=10)
    with pytest.raises(GameError):
        game.mark_ready("ana")
    play(game, [P("ana"), P("bia")], {"ana": 0, "bia": 0})
    game.mark_ready("ana")
    assert not game.everyone_ready(["ana", "bia"])
    game.mark_ready("bia")
    assert game.everyone_ready(["ana", "bia"])
    game.start_round(now=0)
    assert game.ready == set()


def test_classic_mode_has_no_powerups():
    game = Game(questions=[question(f"e{i}") for i in range(4)], answer_seconds=10)
    ana = P("ana")
    for _ in range(3):
        play(game, [ana], {"ana": 0})
        assert game.results[0].gained is None
    assert not game.can_arm and game.powerups == {}


def test_the_host_can_change_how_many_powerups_fit():
    game = Game(powers=True, powerup_max=3, questions=[question(f"e{i}") for i in range(9)], answer_seconds=10, rng=random.Random(1))
    ana = P("ana")
    game.powerups = {"ana": []}
    for _ in range(9):
        play(game, [ana], {"ana": 0})
    assert len(game.powerups["ana"]) + len(game.legendaries["ana"]) == 3
    assert game.view(now=0, viewer="ana").powerup_max == 3


def armed_game(n: int, difficulty: str = "medium", answer: int = 0) -> tuple[Game, P, P]:
    """Partida com poderes de `n` perguntas; a 1ª já foi revelada e dá para armar."""
    game = Game(powers=True, questions=[question(f"q{i}", difficulty, answer) for i in range(n)], answer_seconds=10)
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": [], "bia": []}
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    return game, ana, bia


def arm(game: Game, pid: str, kind: str, target: str | None = None) -> None:
    game.powerups[pid].append(kind)
    game.arm(pid, kind, target, ["ana", "bia"])


def test_double_doubles_right_and_wrong_answers():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "double")
    arm(game, "bia", "double")
    reveal(game, [ana, bia], {"ana": 0, "bia": 1})  # média: +11 na carência, -10 errando
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["ana"].delta, by_id["ana"].doubled) == (22, True)
    assert by_id["bia"].delta == -20


def test_double_triples_a_wrong_hard_answer():
    game, ana, bia = armed_game(5, "hard")
    arm(game, "ana", "double")
    arm(game, "bia", "double")
    reveal(game, [ana, bia], {"ana": 0, "bia": 1})  # difícil: +22 na carência, -5 errando
    by_id = {r.player_id: r for r in game.results}
    assert by_id["ana"].delta == 44
    assert by_id["bia"].delta == -15


def test_second_chance_lets_you_retry_for_half():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "second_chance")
    game.start_round(now=0)
    game.open_answers(now=0)
    game.answer("ana", 1, now=1)  # errou: ainda não acabou
    assert game.view(now=1, viewer="ana").first_wrong == 1
    assert not game.everyone_answered(["ana"]) and "ana" in game.view(now=1, viewer="bia").answered
    with pytest.raises(GameError, match="inválida"):
        game.answer("ana", 1, now=1.5)
    game.answer("ana", 0, now=2)
    game.close_round([ana, bia], now=20)
    result = game.results[0]
    assert (result.correct, result.delta, result.first_option) == (True, 5, 1)  # 11 → metade

    arm(game, "ana", "second_chance")
    game.start_round(now=0)
    game.open_answers(now=0)
    game.answer("ana", 2, now=1)  # errou e não tentou de novo: fica com o erro
    game.close_round([ana, bia], now=20)
    assert (game.results[0].option, game.results[0].delta) == (2, -10)


def test_peek_shows_what_the_others_picked():
    game, ana, bia = armed_game(2)
    game.powerups["ana"].append("peek")
    game.start_round(now=0)
    game.open_answers(now=0)
    game.answer("bia", 3, now=1)
    assert game.view(now=1, viewer="ana").peek is None
    game.use_now("ana", "peek")
    assert game.view(now=1, viewer="ana").peek == [0, 0, 0, 1]
    assert game.view(now=1, viewer="bia").peek is None
    game.answer("ana", 0, now=2)
    with pytest.raises(GameError, match="já respondeu"):
        game.powerups["ana"].append("fifty_fifty")
        game.use_now("ana", "fifty_fifty")

def test_extra_time_gives_more_time_and_full_iq_for_three_common_questions():
    game, ana, bia = armed_game(6)
    arm(game, "ana", "extra_time")
    for left in (3, 2, 1):
        game.start_round(now=0)
        game.open_answers(now=0)
        assert game.answer_window("ana") == 15 and game.answer_window("bia") == 10
        assert game.grace_window("ana") == 15  # QI cheio o tempo todo
        assert [(x.kind, x.rounds_left) for x in game.view(now=0, viewer="ana").lasting] == [("extra_time", left)]
        assert game.phase_ends_at == 15
        with pytest.raises(GameError, match="Agora não"):
            game.answer("bia", 0, now=10 + LATE_SECONDS + 0.1)  # o prazo da Bia é o normal
        game.answer("ana", 0, now=14)
        assert game.answers_close_at(["ana", "bia"]) == 10 + LATE_SECONDS
        game.close_round([ana, bia], now=20)
    game.start_round(now=0)
    assert game.answer_window("ana") == 10  # acabou


def test_accelerator_cuts_the_time_to_a_third_and_removes_full_iq():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "accelerator", "bia")
    game.start_round(now=0)
    game.open_answers(now=0)
    assert game.answer_window("bia") == pytest.approx(10 / 3) and game.grace_window("bia") == 0
    assert game.view(now=0, viewer="bia").phase_ends_in_ms == pytest.approx(3333, abs=1)
    assert game.view(now=0, viewer="ana").phase_ends_in_ms == 10000
    game.answer("bia", 0, now=10 / 6)
    game.close_round([ana, bia], now=20)
    assert {r.player_id: r.delta for r in game.results}["bia"] == 8  # metade do tempo: 5 + 6 × 0,5


def test_silence_hides_who_answered_and_removes_full_iq():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "silence", "bia")
    game.start_round(now=0)
    game.open_answers(now=0)
    assert game.grace_window("bia") == 0 and game.grace_window("ana") == game.speed_grace_seconds
    game.answer("ana", 0, now=1)
    assert game.view(now=1, viewer="bia").answered == []
    assert game.view(now=1, viewer="ana").answered == ["ana"]
    game.answer("bia", 0, now=1)
    game.close_round([ana, bia], now=20)
    deltas = {r.player_id: r.delta for r in game.results}
    assert deltas["ana"] > deltas["bia"]


def test_silence_lasts_two_questions_and_hides_the_reveal():
    game, ana, bia = armed_game(4)
    arm(game, "ana", "silence", "bia")
    reveal(game, [ana, bia], {"ana": 0, "bia": 1})
    seen = game.view(now=20, viewer="bia")
    assert (seen.silenced_rounds, seen.results, seen.correct_option, seen.fact, seen.can_arm) == (2, [], None, None, False)
    assert game.view(now=20, viewer="ana").results != []
    with pytest.raises(GameError, match="Silenciado"):
        arm(game, "bia", "double")
    game.mark_ready("ana")
    assert game.everyone_ready(["ana", "bia"])  # quem está silenciado não segura o Pular

    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    assert game.view(now=20, viewer="bia").silenced_rounds == 1
    assert [(l.kind, l.rounds_left) for l in game._lasting_view("bia")] == [("silence", 1)]
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    seen = game.view(now=20, viewer="bia")
    assert seen.silenced_rounds == 0 and seen.results != []


def test_silence_blocks_instant_powerups_and_restarts_instead_of_stacking():
    game, ana, bia = armed_game(5)
    arm(game, "ana", "silence", "bia")
    game.powerups["bia"].append("fifty_fifty")
    game.start_round(now=0)
    with pytest.raises(GameError, match="Silenciado"):
        game.use_now("bia", "fifty_fifty")
    game.open_answers(now=0)
    game.close_round([ana, bia], now=20)
    arm(game, "ana", "silence", "bia")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    assert game.silence_left("bia") == 2


def test_silence_pauses_for_the_bet_and_comes_back_after():
    qs = [question("m0", "medium"), question("m1", "medium"), *(question(f"h{i}", "hard") for i in range(2, 5))]
    game = Game(powers=True, questions=qs, answer_seconds=10)
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": [], "bia": []}
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    arm(game, "ana", "silence", "bia")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    game.start_round(now=0)
    assert game.phase == "betting" and not game.is_silenced("bia")
    game.bet(bia, 10, now=1)
    game.begin_reading(now=2)
    game.open_answers(now=2)
    game.close_round([ana, bia], now=20)
    assert game.view(now=20, viewer="bia").results != []
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    assert game.view(now=20, viewer="bia").silenced_rounds == 1
    assert game.view(now=20, viewer="bia").results == []


def test_legendary_silence_hits_everyone_but_the_caster():
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(4)], answer_seconds=10)
    ana, bia, caio = P("ana", 50), P("bia", 50), P("caio", 50)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    game.legendaries = {"ana": ["silence"]}
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    game.arm("ana", "silence", None, ["ana", "bia", "caio"], legendary=True)
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    assert (game.silence_left("ana"), game.silence_left("bia"), game.silence_left("caio")) == (0, 2, 2)


def test_reverse_sends_sabotage_back_once():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "scramble", "bia")
    arm(game, "bia", "reverse")
    game.start_round(now=0)
    scramble = next(u for u in game.active if u.kind == "scramble")
    assert (scramble.by, scramble.target, scramble.reflected_by) == ("ana", "ana", "bia")


def test_reversed_steal_robs_the_thief():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "steal", "bia")
    arm(game, "bia", "reverse")
    reveal(game, [ana, bia], {"ana": 1, "bia": 0})  # ana erra: -10, e quem rouba agora é a bia
    by_id = {r.player_id: r for r in game.results}
    assert (by_id["bia"].stolen, by_id["ana"].delta, by_id["ana"].robbed) == (10, -10, 10)


def test_shield_lasts_two_questions_and_breaks_if_unused():
    game, ana, bia = armed_game(8)
    arm(game, "ana", "shield")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})  # acertou: o escudo continua
    assert game.results[0].expired == []
    game.start_round(now=0)
    assert [(x.kind, x.rounds_left) for x in game.view(now=0, viewer="ana").lasting] == [("shield", 1)]
    game.round -= 1
    reveal(game, [ana, bia], {"ana": 1, "bia": 0})  # errou: o escudo segura e acaba
    assert game.results[0].shielded == 10 and game.results[0].expired == []
    reveal(game, [ana, bia], {"ana": 1, "bia": 0})
    assert game.results[0].delta == -10

    arm(game, "ana", "shield")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})  # duas sem errar: quebrou
    assert game.results[0].expired == ["shield"] and game.lasting["ana"] == {}


def test_second_chance_counts_on_both_questions():
    game, ana, bia = armed_game(5)
    arm(game, "ana", "second_chance")
    for _ in range(2):
        game.start_round(now=0)
        game.open_answers(now=0)
        game.answer("ana", 1, now=1)
        assert game.view(now=1, viewer="ana").first_wrong == 1  # vale nas duas
        game.answer("ana", 0, now=2)
        game.close_round([ana, bia], now=20)
    assert game.results[0].expired == [] and "second_chance" not in game.lasting["ana"]

    arm(game, "ana", "second_chance")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})  # duas sem errar: quebrou
    assert game.results[0].expired == ["second_chance"]


def test_reverse_is_secret_and_lasts_three_questions_or_two_for_the_leader():
    game, ana, bia = armed_game(8)
    reveal(game, [ana, bia], {"ana": 0, "bia": 1})  # ana em 1º
    arm(game, "ana", "reverse")
    arm(game, "bia", "reverse")
    game.start_round(now=0)
    assert [u.kind for u in game.view(now=0, viewer="ana").active] == ["reverse"]
    assert [u.by for u in game.view(now=0, viewer="bia").active] == ["bia"]  # só vê o próprio
    assert [(x.kind, x.rounds_left, x.total) for x in game.view(now=0, viewer="ana").lasting] == [("reverse", 2, 2)]
    assert [(x.kind, x.rounds_left, x.total) for x in game.view(now=0, viewer="bia").lasting] == [("reverse", 3, 3)]
    game.open_answers(now=0)
    game.close_round([ana, bia], now=20)
    assert [u.by for u in game.view(now=20, viewer="ana").active] == ["ana"]  # nem na revelação
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    by_id = {r.player_id: r for r in game.results}
    assert by_id["ana"].expired == ["reverse"] and by_id["bia"].expired == []
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    assert game.results[1].expired == ["reverse"]


def test_reverse_lasts_until_it_bounces():
    game, ana, bia = armed_game(5)
    arm(game, "bia", "reverse")
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})  # ninguém atacou: continua
    arm(game, "ana", "mirror", "bia")
    game.start_round(now=0)
    mirror = next(u for u in game.active if u.kind == "mirror")
    assert (mirror.target, mirror.reflected_by) == ("ana", "bia")
    assert "reverse" not in game.lasting["bia"]


def test_magnifier_is_a_sabotage_that_the_reverse_sends_back():
    game, ana, bia = armed_game(2)
    arm(game, "ana", "magnifier", "bia")
    assert game.armed["ana"].target == "bia"
    arm(game, "bia", "reverse")
    game.start_round(now=0)
    lens = next(u for u in game.active if u.kind == "magnifier")
    assert (lens.target, lens.reflected_by) == ("ana", "bia")


def test_toll_charges_the_price_of_the_chosen_option_to_the_attacker():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "toll", "bia")
    game.start_round(now=0)
    prices = game.view(now=0, viewer="bia").tolls
    assert len(prices) == 4 and all(3 <= p <= 8 for p in prices)
    assert game.view(now=0, viewer="ana").tolls is None
    game.open_answers(now=0)
    game.answer("bia", 1, now=1)
    game.close_round([ana, bia], now=20)
    by_id = {r.player_id: r for r in game.results}
    assert by_id["bia"].tolled == prices[1] and by_id["ana"].toll_received == prices[1]


def test_toll_without_an_answer_costs_the_cheapest_price():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "toll", "bia")
    game.start_round(now=0)
    prices = game.view(now=0, viewer="bia").tolls
    game.open_answers(now=0)
    game.close_round([ana, bia], now=20)
    assert {r.player_id: r.tolled for r in game.results}["bia"] == min(prices)


def test_legendary_toll_is_cheaper_and_everyone_pays():
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10)
    ana, bia, caio = P("ana", 50), P("bia", 50), P("caio", 50)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    game.legendaries = {"ana": ["toll"]}
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    game.arm("ana", "toll", None, ["ana", "bia", "caio"], legendary=True)
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    by_id = {r.player_id: r for r in game.results}
    assert 2 <= by_id["bia"].tolled <= 4 and 2 <= by_id["caio"].tolled <= 4
    assert by_id["ana"].toll_received == by_id["bia"].tolled + by_id["caio"].tolled


def test_backpack_adds_a_slot_and_a_powerup_right_away():
    game, ana, bia = armed_game(3)
    game.powerups["ana"] = ["backpack", "backpack", "backpack"]
    game.arm("ana", "backpack", None, ["ana", "bia"])
    assert game.capacity("ana") == game.powerup_max + 1 and len(game.powerups["ana"]) == 3
    assert game.armed == {}  # não ocupa a vez de armar
    game.arm("ana", "backpack", None, ["ana", "bia"])
    game.powerups["ana"].append("backpack")
    with pytest.raises(GameError, match="tamanho máximo"):
        game.arm("ana", "backpack", None, ["ana", "bia"])


def themed(qid: str, theme: str, difficulty: str = "medium") -> Question:
    return question(qid, difficulty).model_copy(update={"theme": theme})


def test_theme_swaps_the_next_question_and_only_the_first_choice_counts():
    bank = [themed(f"{t}{i}", t) for t in "ABCDE" for i in range(2)]
    questions = [themed("e0", "A", "easy"), themed("A0", "A"), themed("A1", "A")]
    game = Game(powers=True, questions=questions, answer_seconds=10, bank=bank, used={"e0", "A0", "A1"})
    ana, bia = P("ana", 50), P("bia", 50)
    game.powerups = {"ana": ["theme"], "bia": ["theme"]}
    reveal(game, [ana, bia], {"ana": 0, "bia": 0})
    choices = game.view(now=20, viewer="ana").theme_choices
    assert len(choices) == 4
    pick = next(t for t in choices if t != "A")
    game.arm("ana", "theme", None, ["ana", "bia"], theme=pick)
    assert game.questions[1].theme == pick
    with pytest.raises(GameError, match="já escolheu"):
        game.arm("bia", "theme", None, ["ana", "bia"], theme=pick)
    assert game.powerups["bia"] == ["theme"]
    game.start_round(now=0)
    assert [(u.kind, u.theme) for u in game.active] == [("theme", pick)]


def test_investment_pays_growing_bonuses_until_the_first_mistake():
    game, ana, bia = armed_game(6)
    arm(game, "ana", "investment")
    paid = []
    for pick in (0, 0, 0, 1, 0):
        reveal(game, [ana, bia], {"ana": pick, "bia": 0})
        paid.append([b.delta for b in game.results[0].bonuses if b.kind == "investment"])
    assert paid == [[2], [4], [6], [], []]
    assert "ana" not in game.investments


def test_investment_starts_only_after_the_easy_questions_and_is_never_dealt():
    game, _, _ = armed_game(3, "easy")
    with pytest.raises(GameError, match="médias"):
        arm(game, "ana", "investment")
    game = Game(powers=True, questions=[question("q")], answer_seconds=10, rng=random.Random(3))
    game.deal_powerups([f"p{i}" for i in range(300)])
    assert "investment" not in game.starting_powerups.values()


def test_decoys_are_nearby_numbers_or_options_from_similar_questions():
    rng = random.Random(1)
    years = powerups.decoys("1878", ["1878", "1888", "1868", "1898"], [], rng)
    assert len(years) == 2 and all(1858 <= int(y) <= 1898 and y not in ("1878", "1888", "1868", "1898") for y in years)
    names = powerups.decoys("Aconcágua", ["Aconcágua", "Huascarán", "Chimborazo", "Pico da Neblina"], ["Ojos del Salado", "Everest", "Huascarán"], rng)
    assert sorted(names) == ["Everest", "Ojos del Salado"]


def test_decoy_shows_six_options_only_to_the_target_and_pays_who_cast_it():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "decoy", "bia")
    game.start_round(now=0)
    seen = game.view(now=0, viewer="bia").question.options
    assert len(seen) == 6 and len(game.view(now=0, viewer="ana").question.options) == 4
    fake = next(i for i, text in enumerate(seen) if text not in game.question.options)
    game.open_answers(now=0)
    game.answer("ana", 0, now=1)
    game.answer("bia", fake, now=1)
    game.close_round([ana, bia], now=20)
    by_id = {r.player_id: r for r in game.results}
    assert by_id["bia"].decoy == seen[fake] and not by_id["bia"].correct
    assert by_id["ana"].tricked == powerups.DECOY_BONUS
    assert {r.player_id: r.option for r in game.view(now=20, viewer="bia").results}["bia"] == fake
    assert {r.player_id: r.option for r in game.view(now=20, viewer="ana").results}["bia"] is None


def test_fifty_fifty_never_removes_a_decoy():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "decoy", "bia")
    game.powerups["bia"].append("fifty_fifty")
    game.start_round(now=0)
    game.use_now("bia", "fifty_fifty")
    view = game.view(now=0, viewer="bia")
    assert all(view.question.options[i] in game.question.options for i in view.hidden_options)


def test_flashbang_hits_only_the_target_and_legendary_hits_everyone_else():
    game, ana, bia = armed_game(3)
    arm(game, "ana", "flashbang", "bia")
    game.start_round(now=0)
    assert game.view(now=0, viewer="bia").flashbang and not game.view(now=0, viewer="ana").flashbang
    game = Game(powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10)
    ana, bia, caio = P("ana", 50), P("bia", 50), P("caio", 50)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    game.legendaries = {"ana": ["flashbang"]}
    reveal(game, [ana, bia, caio], {"ana": 0, "bia": 0, "caio": 0})
    game.arm("ana", "flashbang", None, ["ana", "bia", "caio"], legendary=True)
    game.start_round(now=0)
    assert [game.view(now=0, viewer=p).flashbang for p in ("ana", "bia", "caio")] == [False, True, True]


def test_resurrection_jumps_the_last_right_behind_the_one_ahead():
    game, ana, bia = armed_game(4)
    caio = P("caio", 10)
    ana.score, bia.score = 100, 60
    game.mythics = {"caio": ["resurrection"]}
    game.resurrect(caio, [ana, bia, caio])
    assert caio.score == 59 and game.view(now=20, viewer="ana").revivals[0].after == 59
    game.mythics = {"bia": ["resurrection"]}
    with pytest.raises(GameError, match="último"):
        game.resurrect(bia, [ana, bia, caio])


def test_resurrection_with_two_players_lands_ten_behind_the_leader():
    game, ana, bia = armed_game(4)
    ana.score, bia.score = 100, 20
    game.mythics = {"bia": ["resurrection"]}
    game.resurrect(bia, [ana, bia])
    assert bia.score == 90


def test_resurrection_breaks_when_the_player_leaves_last_place():
    game, ana, bia = armed_game(4)
    ana.score, bia.score = 40, 30
    game.mythics = {"bia": ["resurrection"]}
    reveal(game, [ana, bia], {"ana": 1, "bia": 0})  # ana erra (-10), bia acerta: bia passa
    assert game.mythics["bia"] == [] and "resurrection" in game.results[1].expired


def duel_game() -> tuple[Game, dict[str, P]]:
    """Partida com banco para o X1 (difíceis, impossíveis e frases), e a 1ª pergunta revelada."""
    bank = [question(f"h{i}", "hard") for i in range(8)] + [
        Question(id=f"i{i}", theme="Teste", difficulty="impossible", text="?", options=list("ABCDEF"), answer=0, fact="!")
        for i in range(2)
    ]
    statements = [
        x1.DuelQuestion(id=f"vf{i}", theme="Teste", kind="true_false", text="Frase", options=["Verdadeiro", "Falso"], answer=0, fact="!")
        for i in range(6)
    ]
    game = Game(
        powers=True, questions=[question(f"m{i}", "medium") for i in range(3)], answer_seconds=10, bank=bank, statements=statements
    )
    players = {pid: P(pid, score) for pid, score in (("ana", 50), ("bia", 80), ("caio", 50), ("davi", 50), ("edu", 50), ("fabi", 3))}
    game.powerups = {pid: [] for pid in players}
    reveal(game, list(players.values()), {pid: 0 for pid in players})
    for p in players.values():
        p.score = {"ana": 50, "bia": 80, "caio": 50, "davi": 50, "edu": 50, "fabi": 3}[p.id]
    game.mythics = {"ana": ["duel"]}
    game.challenge("ana", "bia", list(players))
    return game, players


def test_duel_runs_four_true_false_five_hard_and_one_impossible():
    game, players = duel_game()
    assert game.view(now=20, viewer="caio").duels[0].rival == "bia"
    assert game.start_duel(list(players), {p.id: p.score for p in players.values()}, now=0)
    assert [q.kind for q in game.duel.questions] == ["true_false"] * 4 + ["hard"] * 5 + ["impossible"]
    assert game.duel.bettors == ["caio", "davi", "edu"]  # os duelistas e quem tem menos de 5 não apostam
    assert game.view(now=0, viewer="caio").duel.can_bet and not game.view(now=0, viewer="ana").duel.can_bet


def test_duel_payout_with_the_crowd_bets():
    game, players = duel_game()
    game.start_duel(list(players), {p.id: p.score for p in players.values()}, now=0)
    game.duel_bet("caio", "ana", now=1)
    game.duel_bet("davi", "ana", now=1)
    game.duel_bet("edu", "bia", now=1)
    assert game.everyone_bet_on_duel(list(players))
    assert game.open_duel_question(now=10) and game.phase == "duel_answering"
    game.duel_answer("ana", 0, now=11)
    game.duel_answer("bia", 0, now=12)
    game.close_duel_question(now=12)
    assert game.duel.winner is None  # os dois acertaram: segue
    assert game.open_duel_question(now=20)
    assert game.duel.seconds() == x1.FIRST_SECONDS - x1.STEP_SECONDS
    game.duel_answer("ana", 0, now=21)
    game.duel_answer("bia", 1, now=21)
    game.close_duel_question(now=21)
    assert game.duel.winner == "ana" and not game.open_duel_question(now=30)
    game.finish_duel(list(players.values()), now=30)
    scores = {pid: p.score for pid, p in players.items()}
    assert scores["ana"] == 50 + 32 + 5 + 5 and scores["bia"] == 80 - 32
    assert (scores["caio"], scores["davi"], scores["edu"]) == (55, 55, 45)
    end = game.view(now=30, viewer="caio").duel
    assert (end.winner, end.paid, end.from_bets, end.favorite_bonus) == ("ana", 32, 5, 5)


def test_duel_goes_on_when_both_miss_and_the_clock_breaks_a_tie_at_the_end():
    game, players = duel_game()
    game.start_duel(list(players), {p.id: p.score for p in players.values()}, now=0)
    t = 0
    while game.open_duel_question(now=t):
        game.duel_answer("ana", 1, now=t + 1)  # erra sempre, rápido
        game.duel_answer("bia", 1, now=t + 2)  # erra sempre, devagar
        game.close_duel_question(now=t + 2)
        t += 10
    assert game.duel.index == 9 and game.duel.winner == "ana"
    assert set(game.duel.bets) == {"caio", "davi", "edu"}  # quem não apostou teve a aposta sorteada



def test_a_right_bet_of_a_quarter_of_the_iq_earns_a_power():
    game = Game(powers=True, questions=[question("h", "hard", answer=0)], answer_seconds=10, rng=random.Random(3))
    ana, bia, caio = P("ana", 100), P("bia", 100), P("caio", 100)
    game.powerups = {"ana": [], "bia": [], "caio": []}
    game.bet_round = 0
    game.round = -1
    game.round += 1
    game.phase = "betting"
    game.phase_ends_at = 100
    game.bet(ana, 25, now=0)
    game.bet(bia, 24, now=0)
    game.bet(caio, 50, now=0)
    game.open_answers(now=0)
    game.answer("ana", 0, now=1)
    game.answer("bia", 0, now=1)
    game.answer("caio", 1, now=1)
    game.close_round([ana, bia, caio], now=20)
    by_id = {r.player_id: r for r in game.results}
    assert by_id["ana"].bet_gained and by_id["ana"].bet_gained.reason == "bet"
    assert by_id["bia"].bet_gained is None  # menos de 25%
    assert by_id["caio"].bet_gained is None  # errou


def themed(qid: str, theme: str, difficulty: str = "medium") -> Question:
    return question(qid, difficulty).model_copy(update={"theme": theme})


def specialist_game(rounds: int = 10) -> Game:
    themes = ["Artes", "Brasil", "Ciências", "Esportes", "Games"]
    bank = [themed(f"{t}-{i}", t) for t in themes for i in range(rounds)]
    return Game(
        questions=[themed(f"mix-{i}", themes[i % 5]) for i in range(rounds)],
        answer_seconds=10, bank=bank, specialist=True, rng=random.Random(1),
    )


def test_specialist_opens_each_block_with_a_theme_pick():
    game = specialist_game()
    game.start_round(now=0, scores={"ana": 50, "bia": 50})
    view = game.view(now=0, viewer="ana")
    assert view.phase == "theme_pick" and view.question is None
    assert game.theme_picker in ("ana", "bia")
    assert len(view.theme_options) == 4
    other = "bia" if game.theme_picker == "ana" else "ana"
    with pytest.raises(GameError, match="outra pessoa"):
        game.choose_theme(other, game.theme_options[0])
    with pytest.raises(GameError, match="um dos temas"):
        game.choose_theme(game.theme_picker, "Futebol")
    theme = game.theme_options[1]
    game.choose_theme(game.theme_picker, theme)
    game.close_theme_pick(now=3)
    assert game.phase == "starting"
    assert all(game.questions[i].theme == theme for i in range(5))
    assert len({q.id for q in game.questions[:5]}) == 5
    for _ in range(4):
        game.start_round(now=10, scores={"ana": 50, "bia": 50})
        assert game.phase == "reading" and game.block_theme == theme
    game.start_round(now=20, scores={"ana": 50, "bia": 40})
    assert game.phase == "theme_pick" and game.block_theme is None


def test_specialist_draws_a_random_theme_when_nobody_picks():
    game = specialist_game()
    game.start_round(now=0, scores={"ana": 50})
    game.close_theme_pick(now=12)
    assert game.block_theme in game.theme_options
    assert all(q.theme == game.block_theme for q in game.questions[:5])


def test_specialist_picker_is_more_likely_the_last_place():
    picks = {"ana": 0, "bia": 0, "caio": 0}
    for seed in range(600):
        game = specialist_game()
        game.rng = random.Random(seed)
        game.start_round(now=0, scores={"ana": 80, "bia": 60, "caio": 20})
        picks[game.theme_picker] += 1
    assert picks["caio"] > 250 and picks["ana"] > 60 and picks["bia"] > 60  # 3/5 para o último


def test_specialist_picker_gets_a_quarter_more_on_right_answers():
    game = specialist_game()
    game.start_round(now=0, scores={"ana": 0, "bia": 0})
    picker = game.theme_picker
    other = "bia" if picker == "ana" else "ana"
    game.close_theme_pick(now=0)
    game.begin_reading(now=0)
    game.open_answers(now=0)
    right = game.question.answer  # as alternativas do bloco vêm embaralhadas
    game.answer(picker, right, now=1)
    game.answer(other, right, now=1)
    players = [P("ana"), P("bia")]
    game.close_round(players, now=20)
    by_id = {r.player_id: r for r in game.results}
    assert by_id[picker].delta == 11 and by_id[picker].specialist_bonus == 3
    assert by_id[other].specialist_bonus == 0
    assert {p.id: p.score for p in players} == {picker: 14, other: 11}


def test_specialist_never_deals_the_theme_power():
    game = specialist_game()
    game.powers = True
    assert "theme" not in game.dealable and "coup" in game.dealable
    assert "coup" not in Game(questions=[question("q1")], answer_seconds=10).dealable
    for seed in range(50):
        game.rng = random.Random(seed)
        game.deal_powerups(["ana", "bia", "caio"])
        assert "theme" not in [k for held in game.powerups.values() for k in held]


def test_coup_takes_the_theme_bonus_for_the_rest_of_the_block():
    game = specialist_game(rounds=15)
    game.powers = True
    game.start_round(now=0, scores={"ana": 50, "bia": 50, "caio": 50})
    game.theme_picker = "ana"
    game.close_theme_pick(now=0)
    game.begin_reading(now=0)
    game.open_answers(now=0)
    game.close_round([P("ana"), P("bia"), P("caio")], now=20)
    game.powerups = {"ana": ["coup"], "bia": ["coup"], "caio": ["coup"]}
    with pytest.raises(GameError, match="já é seu"):
        game.arm("ana", "coup", None, ["ana", "bia", "caio"])
    game.arm("bia", "coup", None, ["ana", "bia", "caio"])
    assert game.armed["bia"].target == "ana" and game.armed["bia"].theme == game.block_theme
    with pytest.raises(GameError, match="Já deram"):
        game.arm("caio", "coup", None, ["ana", "bia", "caio"])
    game.start_round(now=30, scores={"ana": 50, "bia": 50, "caio": 50})
    assert game.theme_picker == "bia"
    game.open_answers(now=30)
    game.answer("ana", game.question.answer, now=31)
    game.answer("bia", game.question.answer, now=31)
    players = [P("ana"), P("bia"), P("caio")]
    game.close_round(players, now=50)
    bonus = {r.player_id: r.specialist_bonus for r in game.results}
    assert bonus["bia"] > 0 and bonus["ana"] == 0
    with pytest.raises(GameError, match="Já deram"):
        game.arm("caio", "coup", None, ["ana", "bia", "caio"])
    for _ in range(3):  # até a 5ª pergunta, a última do bloco
        game.start_round(now=60, scores={})
        game.open_answers(now=60)
        game.close_round(players, now=80)
    game.coup_block = None  # mesmo sem Golpe no bloco, não dá para usar na última pergunta dele
    with pytest.raises(GameError, match="acaba agora"):
        game.arm("caio", "coup", None, ["ana", "bia", "caio"])  # a próxima já é de outro bloco
