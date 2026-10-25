import random
from dataclasses import dataclass

import pytest

from app.game import (
    MAX_READING_SECONDS,
    MAX_RESULTS_SECONDS,
    MIN_RESULTS_SECONDS,
    MIN_READING_SECONDS,
    BET_SECONDS,
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
    assert split_by_difficulty(10) == {"easy": 4, "medium": 3, "hard": 3}
    assert split_by_difficulty(5) == {"easy": 2, "medium": 2, "hard": 1}


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
        game.answer("ana", 0, now=11.5)


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
        game.bet(dani, 0, now=BET_SECONDS + 1)  # fora da fase

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
