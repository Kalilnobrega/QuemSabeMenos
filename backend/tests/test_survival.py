import random

import pytest

from app.duel import DuelQuestion
from app.game import Question
from app.survival import RULES, Survival, SurvivalError

TF = RULES["true_false"]
LIVES = TF.lives
ANSWER_SECONDS = TF.answer_seconds
MEDIUM_COUNT = dict(TF.levels)["medium"]
DUEL_FIRST_SECONDS, DUEL_STEP_SECONDS, DUEL_MIN_SECONDS = TF.duel_first_seconds, TF.duel_step_seconds, TF.duel_min_seconds


def statements(count: int = 30) -> list[DuelQuestion]:
    return [
        DuelQuestion(
            id=f"vf-{level}-{i}",
            theme="Games",
            kind="true_false",
            text=f"Frase {level} {i}",
            options=["Verdadeiro", "Falso"],
            answer=0,
            fact="Curiosidade.",
            difficulty=level,
        )
        for level in ("medium", "hard")
        for i in range(count)
    ]


def questions(count: int = 30) -> list[Question]:
    return [
        Question(
            id=f"q-{level}-{i}",
            theme="Games",
            difficulty=level,
            text=f"Pergunta {level} {i}",
            options=[f"Certa {i}", "B", "C", "D"] + (["E", "F"] if level == "impossible" else []),
            answer=0,
            fact="Curiosidade.",
        )
        for level in ("easy", "medium", "hard", "impossible")
        for i in range(count)
    ]


def new_game(players: int) -> Survival:
    game = Survival.create("true_false", [f"p{i}" for i in range(players)], statements(), set(), random.Random(1), now=0)
    game.advance(now=5)
    return game


def play(game: Survival, right: list[str], now: float = 0) -> None:
    """Quem está em `right` acerta; o resto dos que respondem erra."""
    while game.phase in ("level", "duel_intro", "reading", "duel_reading"):
        game.advance(now)
    for pid in game.answering_ids():
        game.answer(pid, game.question.answer if pid in right else 1 - game.question.answer, now)
    game.advance(now)  # fecha
    game.advance(now)  # próxima


def test_two_wrong_answers_eliminate():
    game = new_game(3)
    assert game.phase == "answering" and game.question.difficulty == "medium"
    play(game, right=["p0", "p1"])
    assert game.contender("p2").lives == LIVES - 1
    play(game, right=["p0", "p1"])
    assert game.contender("p2").out_round == 2
    assert game.answering_ids() == ["p0", "p1"]
    assert game.phase == "duel_intro"


def test_nobody_loses_a_life_when_everyone_is_wrong():
    game = new_game(3)
    for pid in game.answering_ids():
        game.answer(pid, 1 - game.question.answer, 0)
    game.advance(0)
    assert game.spared
    assert all(c.lives == LIVES for c in game.contenders)


def test_no_answer_costs_a_life():
    game = new_game(3)
    game.answer("p0", game.question.answer, 0)
    game.advance(ANSWER_SECONDS)
    assert [c.lives for c in game.contenders] == [LIVES, LIVES - 1, LIVES - 1]
    assert [p.lost_life for p in game.picks] == [False, True, True]


def test_hard_statements_after_the_mediums_with_a_level_screen():
    game = new_game(4)
    for _ in range(MEDIUM_COUNT):
        assert game.question.difficulty == "medium"
        play(game, right=game.alive_ids())
    assert game.phase == "level"
    assert game.question.difficulty == "hard"
    game.advance(0)
    assert game.phase == "answering"


def test_duel_time_drops_every_statement_and_a_lonely_mistake_loses():
    game = new_game(2)
    assert game.phase == "duel_intro"
    game.advance(0)
    assert game.phase == "duel_answering"
    assert game.answer_seconds() == DUEL_FIRST_SECONDS
    play(game, right=["p0", "p1"])
    assert game.answer_seconds() == DUEL_FIRST_SECONDS - DUEL_STEP_SECONDS
    play(game, right=[])  # os dois erram: segue
    assert game.phase == "duel_answering"
    for _ in range(20):
        play(game, right=["p0", "p1"])
    assert game.answer_seconds() == DUEL_MIN_SECONDS
    play(game, right=["p1"])
    assert game.phase == "finished"
    assert game.winner == "p1"
    assert game.places() == {"p1": 1, "p0": 2}


def test_places_follow_elimination_order():
    game = new_game(4)
    play(game, right=["p0", "p1", "p2"])
    play(game, right=["p0", "p1", "p2"])  # p3 cai na 2
    play(game, right=["p0", "p1"])
    play(game, right=["p0", "p1"])  # p2 cai na 4 → X1
    assert game.phase == "duel_intro"
    play(game, right=["p0"])
    assert game.winner == "p0"
    assert game.places() == {"p0": 1, "p1": 2, "p2": 3, "p3": 4}


def test_leaving_the_duel_hands_the_win():
    game = new_game(2)
    game.advance(0)
    game.drop("p0")
    game.answer("p1", 1 - game.question.answer, 0)
    game.advance(0)
    game.advance(0)
    assert game.winner == "p1"


def test_eliminated_players_cannot_answer():
    game = new_game(3)
    play(game, right=["p0", "p1"])
    play(game, right=["p0", "p1"])
    game.advance(0)
    with pytest.raises(SurvivalError):
        game.answer("p2", 0, 0)


def test_statements_do_not_repeat_until_the_level_runs_out():
    used: set[str] = set()
    game = Survival.create("true_false", ["a", "b", "c"], statements(count=3), used, random.Random(2), now=0)
    game.advance(0)
    seen = [game.question.id]
    for _ in range(2):
        play(game, right=["a", "b", "c"])
        seen.append(game.question.id)
    assert len(set(seen)) == 3
    play(game, right=["a", "b", "c"])
    assert game.question.difficulty == "medium"  # acabaram as médias: libera de novo


def new_choices_game(players: int) -> Survival:
    game = Survival.create("choices", [f"p{i}" for i in range(players)], questions(), set(), random.Random(3), now=0)
    game.advance(now=5)
    return game


def test_choices_start_with_three_lives_and_easy_questions_after_reading():
    game = new_choices_game(3)
    assert game.phase == "reading"
    assert all(c.lives == 3 for c in game.contenders)
    assert game.question.difficulty == "easy"
    with pytest.raises(SurvivalError):
        game.answer("p0", 0, 5)
    game.advance(6)
    assert game.phase == "answering"
    assert game.answer_seconds() == RULES["choices"].answer_seconds


def test_choices_shuffle_options_and_keep_the_answer():
    game = new_choices_game(3)
    q = game.question
    assert q.options[q.answer].startswith("Certa")
    assert sorted(q.options) == sorted(next(o for o in questions() if o.id == q.id).options)


def test_choices_go_easy_then_medium_then_hard():
    game = new_choices_game(4)
    levels = []
    for _ in range(17):
        while game.phase in ("level", "reading"):
            game.advance(0)
        levels.append(game.question.difficulty)
        play(game, right=game.alive_ids())
    assert levels == ["easy"] * 5 + ["medium"] * 10 + ["hard"] * 2


def test_choices_duel_turns_impossible_and_speed_decides_it():
    game = new_choices_game(2)
    rules = RULES["choices"]
    for _ in range(rules.duel_impossible_after):
        play(game, right=["p0", "p1"])
    while game.phase in ("duel_reading",):
        game.advance(0)
    assert game.question.difficulty == "impossible"
    assert len(game.question.options) == 6
    assert game.answer_seconds() == rules.duel_min_seconds
    game.answer("p1", game.question.answer, 1)
    game.answer("p0", game.question.answer, 2)
    game.advance(3)
    game.advance(3)
    assert game.winner == "p1"
