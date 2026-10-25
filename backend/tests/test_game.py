import random
from dataclasses import dataclass

import pytest

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
    game = Game(powers=True, questions=[question(f"e{i}") for i in range(7)], answer_seconds=10)
    ana = P("ana")
    game.powerups = {"ana": []}
    gains = []
    for _ in range(7):
        play(game, [ana], {"ana": 0})
        gains.append(game.results[0].gained)
    assert [g is not None for g in gains] == [False, False, True, False, False, True, False]
    assert gains[2].reason == "streak" and len(game.powerups["ana"]) == 2  # cheio: o 3º não vem


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
    assert trailing([P("a", 100), P("b", 60), P("c", 40)]) == set()  # perto do 2º
    assert trailing([P("a", 100), P("b", 40)]) == {"b"}  # com 2, compara com o 1º


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
    game = Game(powers=True, powerup_max=3, questions=[question(f"e{i}") for i in range(9)], answer_seconds=10)
    ana = P("ana")
    game.powerups = {"ana": []}
    for _ in range(9):
        play(game, [ana], {"ana": 0})
    assert len(game.powerups["ana"]) == 3
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
