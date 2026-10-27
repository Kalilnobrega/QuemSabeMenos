import random

import pytest

from app.duel import DuelQuestion
from app.survival import (
    ANSWER_SECONDS,
    DUEL_FIRST_SECONDS,
    DUEL_MIN_SECONDS,
    DUEL_STEP_SECONDS,
    LIVES,
    MEDIUM_COUNT,
    Survival,
    SurvivalError,
)


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


def new_game(players: int) -> Survival:
    game = Survival.create([f"p{i}" for i in range(players)], statements(), set(), random.Random(1), now=0)
    game.advance(now=5)
    return game


def play(game: Survival, right: list[str], now: float = 0) -> None:
    """Quem está em `right` acerta; o resto dos que respondem erra."""
    if game.phase in ("level", "duel_intro"):
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
    game = Survival.create(["a", "b", "c"], statements(count=3), used, random.Random(2), now=0)
    game.advance(0)
    seen = [game.question.id]
    for _ in range(2):
        play(game, right=["a", "b", "c"])
        seen.append(game.question.id)
    assert len(set(seen)) == 3
    play(game, right=["a", "b", "c"])
    assert game.question.difficulty == "medium"  # acabaram as médias: libera de novo
