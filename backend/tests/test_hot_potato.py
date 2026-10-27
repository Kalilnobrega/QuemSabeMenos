import random

import pytest

from app.game import Question
from app.hot_potato import (
    EXPLODED_SECONDS,
    FUSE_SECONDS,
    MAX_WRONG_STREAK,
    PASS_SECONDS,
    START_SECONDS,
    WRONG_PENALTY_SECONDS,
    WRONG_SECONDS,
    HotPotato,
    HotPotatoError,
)


def questions(count: int = 40) -> list[Question]:
    return [
        Question(
            id=f"q-{level}-{i}",
            theme="Games",
            difficulty=level,
            text=f"Pergunta {level} {i}",
            options=[f"Certa {i}", "B", "C", "D"],
            answer=0,
            fact="Curiosidade.",
        )
        for level in ("easy", "medium", "hard")
        for i in range(count)
    ]


def new_game(players: int = 3) -> HotPotato:
    game = HotPotato.create([f"p{i}" for i in range(players)], questions(), set(), random.Random(1), now=0)
    game.advance(START_SECONDS)
    return game


def right(game: HotPotato) -> int:
    return game.question.answer


def wrong(game: HotPotato) -> int:
    return (game.question.answer + 1) % 4


def test_starts_with_a_hidden_fuse_and_only_easy_or_medium_questions():
    game = new_game()
    assert game.phase == "asking"
    assert FUSE_SECONDS[0] <= game.fuse_total <= FUSE_SECONDS[1]
    assert game.question.difficulty in ("easy", "medium")
    assert game.question.options[game.question.answer].startswith("Certa")


def test_right_answer_passes_to_the_next_in_the_circle():
    game = new_game()
    first = game.holder
    game.answer(first, right(game), 7)
    assert game.phase == "passing"
    game.advance(7 + PASS_SECONDS)
    ids = [p.id for p in game.players]
    assert game.holder == ids[(ids.index(first) + 1) % 3]


def test_the_fuse_only_burns_while_answering():
    game = new_game()
    total, t0 = game.fuse_total, game.phase_started_at
    game.answer(game.holder, right(game), t0 + 5)
    assert game.fuse_left == pytest.approx(total - 5)
    game.advance(t0 + 100)  # o passe não queima
    assert game.fuse_at(t0 + 100) == pytest.approx(total - 5)


def test_wrong_answer_costs_ten_seconds_and_keeps_the_potato():
    game = new_game()
    holder, total, t0 = game.holder, game.fuse_total, game.phase_started_at
    game.answer(holder, wrong(game), t0 + 2)
    assert game.phase == "wrong"
    assert game.fuse_left == pytest.approx(total - 2 - WRONG_PENALTY_SECONDS)
    game.advance(t0 + 2 + WRONG_SECONDS)
    assert game.holder == holder and game.phase == "asking"


def test_three_wrong_in_a_row_explodes():
    game = new_game()
    holder = game.holder
    for _ in range(MAX_WRONG_STREAK - 1):
        game.answer(holder, wrong(game), 0)
        game.advance(0)
    game.answer(holder, wrong(game), 0)
    assert game.phase == "exploded" and game.exploded == holder
    assert not game.player(holder).alive


def test_a_right_answer_resets_the_wrong_streak():
    game = new_game(players=2)
    holder = game.holder
    game.answer(holder, wrong(game), 0)
    game.advance(0)
    game.answer(holder, right(game), 0)
    assert game.wrong_streak == 0


def test_the_fuse_running_out_eliminates_the_holder_and_the_next_round_starts_after_them():
    game = new_game(players=3)
    holder = game.holder
    game.advance(game.deadline())
    assert game.exploded == holder and game.phase == "exploded"
    game.advance(game.deadline() + EXPLODED_SECONDS)
    ids = [p.id for p in game.players]
    assert game.round == 2
    assert game.holder == ids[(ids.index(holder) + 1) % 3]
    assert game.fuse_left == game.fuse_total


def test_last_one_standing_wins():
    game = new_game(players=2)
    loser = game.holder
    game.advance(game.deadline())
    game.advance(game.deadline())
    assert game.phase == "finished"
    assert game.winner != loser
    assert game.places()[game.winner] == 1 and game.places()[loser] == 2


def test_only_the_holder_answers():
    game = new_game()
    other = next(p.id for p in game.players if p.id != game.holder)
    with pytest.raises(HotPotatoError):
        game.answer(other, 0, 0)


def test_holder_leaving_hands_the_potato_on():
    game = new_game(players=3)
    holder = game.holder
    game.drop(holder, 1)
    assert game.holder != holder and game.phase == "asking"
    other = next(pid for pid in game.alive_ids() if pid != game.holder)
    game.drop(other, 2)
    assert game.phase == "finished" and game.winner == game.alive_ids()[0]


def test_view_hides_the_fuse_but_shows_the_heat():
    game = new_game()
    view = game.view(game.phase_started_at + game.fuse_total / 2, [p.id for p in game.players])
    assert view.heat == pytest.approx(0.5, abs=0.01)
    assert view.burning and view.options and view.holder == game.holder
