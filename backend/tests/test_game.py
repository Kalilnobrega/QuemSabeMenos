import random
from dataclasses import dataclass

import pytest

from app.game import (
    MAX_READING_SECONDS,
    MAX_RESULTS_SECONDS,
    MIN_RESULTS_SECONDS,
    MIN_READING_SECONDS,
    Game,
    GameError,
    Question,
    load_bank,
    pick_questions,
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
    assert points("medium", True, 1) == 12
    assert points("medium", True, 0) == 6
    assert points("hard", True, 1) == 25
    assert points("hard", True, 0.5) == 20
    assert points("hard", True, 0) == 15
    assert points("impossible", True, 1) == 35
    assert points("impossible", True, 0) == 35  # sem bônus de tempo
    assert points("easy", False) == -15
    assert points("medium", False) == -7
    assert points("hard", False) == -2
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
    assert [q.difficulty for q in first] == ["easy"] * 5 + ["medium"] * 5 + ["hard"] * 4 + ["impossible"]
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
    assert (ana.score, bia.score, caio.score) == (12, -7, -10)
    assert (ana.answer_ms, bia.answer_ms, caio.answer_ms) == (2000, 3000, 10000)
    view = game.view(now=12)
    assert view.correct_option == 2
    assert view.fact == "Dois é o único primo par."
    assert not game.has_next_round


def test_speed_bonus_starts_decaying_after_the_grace_period():
    game = Game(questions=[question("q1", "hard")], answer_seconds=10)
    assert game.speed_fraction(0) == game.speed_fraction(3) == 1
    assert game.speed_fraction(6.5) == 0.5
    assert game.speed_fraction(10) == 0
    assert points("hard", True, game.speed_fraction(6.5)) == 20


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
    view = game.view(now=0.5)
    assert view.correct_option is None
    assert view.fact is None
    assert view.round == 1 and view.total_rounds == 1
    assert view.phase_ends_in_ms == round((reading_seconds("Quanto é 1+1?") - 0.5) * 1000)
