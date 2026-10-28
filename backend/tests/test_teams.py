import random

import pytest

from app.game import Question
from app.teams import (
    CAPTAIN_BONUS,
    CHOOSING_SECONDS,
    HARMONY_BONUS,
    TeamMatch,
    TeamMatchError,
)


def question(qid: str, difficulty: str = "medium") -> Question:
    options = ["Certa", "B", "C", "D", "E", "F"] if difficulty == "impossible" else ["Certa", "B", "C", "D"]
    return Question(id=qid, theme="Teste", difficulty=difficulty, text="?", options=options, answer=0, fact="Fato.")


PLAYERS = ["a1", "a2", "a3", "b1", "b2"]
ALL = list(PLAYERS)


def new_match(questions: list[Question] | None = None) -> TeamMatch:
    questions = questions or [question(f"q{i}") for i in range(6)]
    match = TeamMatch.create(
        {"a1": 0, "a2": 0, "a3": 0, "b1": 1, "b2": 1}, questions, answer_seconds=10, now=0, rng=random.Random(1),
    )
    match.advance(0, ALL)  # starting → reading
    return match


def open_question(match: TeamMatch) -> float:
    while match.phase != "answering":
        match.advance(match.phase_ends_at, ALL)
    return match.phase_started_at


def team(match: TeamMatch, i: int):
    return match.teams[i]


def test_the_team_answers_when_everyone_votes_and_the_captain_counts_twice():
    match = new_match()
    t0 = open_question(match)
    a = team(match, 0)
    assert a.captain == "a1"
    match.vote("a1", 2, t0 + 1, ALL)  # capitão: 2 votos
    match.vote("a2", 0, t0 + 1, ALL)
    assert a.locked_at is None
    match.vote("a3", 1, t0 + 1, ALL)
    assert a.locked_at is not None and a.option == 2
    with pytest.raises(TeamMatchError, match="já respondeu"):
        match.vote("a2", 0, t0 + 2, ALL)


def test_votes_can_change_until_everyone_has_voted():
    match = new_match()
    t0 = open_question(match)
    match.vote("b1", 3, t0 + 1, ALL)
    match.vote("b1", 0, t0 + 2, ALL)
    match.vote("b2", 0, t0 + 2, ALL)
    assert team(match, 1).option == 0


def test_a_tie_goes_to_the_captains_side():
    match = new_match()
    t0 = open_question(match)
    match.vote("a1", 1, t0, ALL)  # capitão
    match.vote("a2", 0, t0, ALL)
    match.vote("a3", 0, t0, ALL)  # 2 x 2
    assert team(match, 0).option == 1


def test_scoring_with_captain_bonus_and_penalty():
    match = new_match()
    t0 = open_question(match)
    for pid in ("a1", "a2", "a3"):
        match.vote(pid, 0, t0 + 1, ALL)
    match.vote("b1", 2, t0 + 1, ALL)  # capitão do B erra
    match.vote("b2", 0, t0 + 1, ALL)
    match.advance(match.phase_ends_at, ALL)
    a, b = team(match, 0), team(match, 1)
    assert a.correct and a.captain_delta == CAPTAIN_BONUS and a.delta > 0
    assert b.option == 2 and not b.correct and b.captain_delta == -CAPTAIN_BONUS
    assert a.score == 50 + a.delta + CAPTAIN_BONUS
    assert b.score == 50 + b.delta - CAPTAIN_BONUS


def test_captain_rotates_each_question():
    match = new_match()
    captains = []
    for _ in range(3):
        open_question(match)
        captains.append(team(match, 0).captain)
        match.advance(match.phase_ends_at, ALL)
    assert captains == ["a1", "a2", "a3"]


def test_three_unanimous_right_answers_in_a_row_earn_harmony():
    match = new_match()
    for i in range(3):
        t0 = open_question(match)
        for pid in ("a1", "a2", "a3"):
            match.vote(pid, 0, t0, ALL)
        match.advance(match.phase_ends_at, ALL)
        assert team(match, 0).harmony_delta == (HARMONY_BONUS if i == 2 else 0)
        match.advance(match.phase_ends_at, ALL)


def test_one_wrong_vote_breaks_the_harmony_even_if_the_team_gets_it():
    match = new_match()
    t0 = open_question(match)
    match.vote("a1", 0, t0, ALL)
    match.vote("a2", 0, t0, ALL)
    match.vote("a3", 1, t0, ALL)
    match.advance(match.phase_ends_at, ALL)
    assert team(match, 0).correct and team(match, 0).harmony == 0


def test_nobody_voting_counts_as_no_answer():
    match = new_match()
    open_question(match)
    match.advance(match.phase_ends_at, ALL)
    assert team(match, 1).option is None and team(match, 1).delta < 0


def test_bet_and_final_are_answered_by_the_chosen_representative():
    questions = [question("e", "easy"), question("h1", "hard"), question("h2", "hard"), question("f", "impossible")]
    match = new_match(questions)
    while not match.solo:
        open_question(match)
        match.advance(match.phase_ends_at, ALL)
        match.advance(match.phase_ends_at, ALL)
    assert match.phase == "choosing" and match.round == match.bet_index
    for pid in ("a1", "a2", "a3"):
        match.choose(pid, "a2")
    with pytest.raises(TeamMatchError):
        match.choose("b1", "a1")  # só do próprio time
    match.advance(match.phase_started_at + CHOOSING_SECONDS, ALL)
    assert match.phase == "betting" and team(match, 0).representative == "a2"
    assert team(match, 1).representative in ("b1", "b2")
    with pytest.raises(TeamMatchError):
        match.place_bet("a1", 10, match.phase_started_at)
    score = team(match, 0).score
    match.place_bet("a2", 20, match.phase_started_at)
    t0 = open_question(match)
    with pytest.raises(TeamMatchError, match="representante"):
        match.vote("a1", 0, t0, ALL)
    match.vote("a2", 0, t0 + 1, ALL)
    assert team(match, 0).locked_at is not None
    match.advance(match.phase_ends_at, ALL)
    a = team(match, 0)
    assert a.bet_delta == 10 and a.captain_delta == 0 and a.score == score + a.delta + 10
    match.advance(match.phase_ends_at, ALL)
    assert match.phase == "choosing"  # a final
    match.advance(match.phase_ends_at, ALL)
    assert match.phase == "intro"


def test_others_see_only_who_voted_until_the_reveal():
    match = new_match()
    t0 = open_question(match)
    match.vote("a1", 2, t0, ALL)
    rival = match.view(t0, "b1").teams[0]
    assert rival.voted == ["a1"] and rival.votes == [] and rival.option is None
    assert match.view(t0, "a2").teams[0].votes[0].option == 2
