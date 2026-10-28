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


# --- com poderes ----------------------------------------------------------

from app import duel as x1  # noqa: E402
from app.teams import DECOY_PER_PLAYER, IRON_RIGHT, IRON_WRONG, MUTINY_ROUNDS, TAX_SHARE  # noqa: E402


def bank() -> list[Question]:
    return [
        Question(id=f"{d}{i}", theme=t, difficulty=d, text=f"{t} {d} {i}?", options=[f"Certa {i}", f"Errada {i}", f"Outra {i}", f"Mais {i}"], answer=0, fact="Fato.")
        for t in ("Teste", "Games")
        for d in ("medium", "hard")
        for i in range(20)
    ]


def powered(questions: list[Question] | None = None) -> TeamMatch:
    questions = questions or [question(f"q{i}") for i in range(8)]
    match = TeamMatch.create(
        {"a1": 0, "a2": 0, "a3": 0, "b1": 1, "b2": 1}, questions, answer_seconds=10, now=0, rng=random.Random(2),
        powers=True, bank=bank(), statements=[
            x1.DuelQuestion(id=f"vf{i}", theme="Teste", kind="true_false", text="V?", options=["Verdadeiro", "Falso"], answer=0, fact="F.")
            for i in range(6)
        ],
    )
    match.advance(0, ALL)
    return match


def to_results(match: TeamMatch, votes: dict[str, int] | None = None) -> None:
    t0 = open_question(match)
    for pid, option in (votes or {}).items():
        match.vote(pid, option, t0 + 1, ALL)
    while match.phase == "answering":
        match.advance(match.deadline(), ALL)


def arm(match: TeamMatch, team_id: int, kind: str, **kwargs) -> None:
    t = team(match, team_id)
    t.held = [kind]
    match.arm(t.next_captain or t.members[0], kind, **kwargs)


def next_question(match: TeamMatch) -> float:
    match.advance(match.phase_ends_at, ALL)
    return open_question(match)


def test_each_team_starts_with_one_power_and_only_the_next_captain_arms():
    match = powered()
    assert all(len(t.held) == 1 for t in match.teams) and match.powerup_max == 3
    to_results(match)
    a = team(match, 0)
    assert a.next_captain == "a2"
    a.held = ["shield"]
    with pytest.raises(TeamMatchError, match="capitão"):
        match.arm("a1", "shield")
    match.arm("a2", "shield")
    assert a.armed.kind == "shield"


def test_mutiny_leaves_the_other_team_without_captain_for_three_questions():
    match = powered()
    to_results(match)
    arm(match, 0, "mutiny", target_team=1)
    for _ in range(MUTINY_ROUNDS):
        next_question(match)
        assert team(match, 1).captain is None
        match.advance(match.phase_ends_at, ALL)
    next_question(match)
    assert team(match, 1).captain is not None


def test_infiltrator_votes_twice_in_the_other_team():
    match = powered()
    to_results(match)
    arm(match, 0, "infiltrator", target_team=1, target_player="a3")
    t0 = next_question(match)
    match.vote("a3", 2, t0, ALL, team_id=1)
    with pytest.raises(TeamMatchError):
        match.vote("a1", 2, t0, ALL, team_id=1)
    b = team(match, 1)
    captain = b.captain
    other = next(p for p in b.members if p != captain)
    match.vote(other, 0, t0, ALL)
    match.vote(captain, 1, t0, ALL)  # capitão 2 x Infiltrado 2 x 1: empate fica com o capitão
    assert b.option == 1
    assert match.view(t0, other).teams[1].votes[-1].infiltrator


def test_gag_takes_the_vote_away():
    match = powered()
    to_results(match)
    arm(match, 0, "gag", target_team=1, target_player="b2")
    t0 = next_question(match)
    with pytest.raises(TeamMatchError, match="Mordaça"):
        match.vote("b2", 0, t0, ALL)
    match.vote("b1", 0, t0, ALL)
    assert team(match, 1).locked_at is not None  # quem tem mordaça não segura o time


def test_iron_captain_votes_alone_for_eight_or_minus_ten():
    match = powered()
    to_results(match)
    arm(match, 0, "iron_captain")
    t0 = next_question(match)
    a = team(match, 0)
    with pytest.raises(TeamMatchError, match="ferro"):
        match.vote(next(p for p in a.members if p != a.captain), 0, t0, ALL)
    match.vote(a.captain, 0, t0, ALL)
    assert a.locked_at is not None
    match.vote("b1", 0, t0, ALL)
    match.vote("b2", 0, t0, ALL)
    match.advance(match.deadline(), ALL)
    assert a.captain_delta == IRON_RIGHT
    assert IRON_WRONG == -10


def test_decoy_pays_five_per_player_who_falls_for_it():
    match = powered()
    to_results(match)
    arm(match, 0, "decoy", target_team=1)
    t0 = next_question(match)
    b = team(match, 1)
    fake = next(i for i in range(6) if b.decoy.order[i] >= 4)
    right = b.decoy.order.index(0)
    match.vote(b.captain, right, t0, ALL)
    match.vote(next(p for p in b.members if p != b.captain), fake, t0, ALL)
    match.advance(match.deadline(), ALL)
    assert b.correct and team(match, 0).tricked == DECOY_PER_PLAYER


def test_tax_makes_the_leader_pay_the_last():
    match = powered()
    to_results(match)
    a, b = team(match, 0), team(match, 1)
    a.score, b.score = 100, 20
    b.mythics = ["tax"]
    with pytest.raises(TeamMatchError):
        a.mythics = ["tax"]
        match.arm(a.next_captain, "tax")
    match.arm(b.next_captain, "tax")
    paid = round(100 * TAX_SHARE)
    assert (a.score, b.score) == (100 - paid, 20 + paid)


def test_steal_and_shield_and_double():
    match = powered()
    to_results(match)
    arm(match, 0, "steal", target_team=1)
    arm(match, 1, "double")
    to_results_after = next_question(match)
    for pid in ("b1", "b2"):
        match.vote(pid, 0, to_results_after, ALL)
    for pid in ("a1", "a2", "a3"):
        match.vote(pid, 1, to_results_after, ALL)
    match.advance(match.deadline(), ALL)
    a, b = team(match, 0), team(match, 1)
    assert b.doubled and b.delta > 0 and b.robbed == a.stolen > 10


def test_second_chance_lets_the_team_vote_again():
    match = powered()
    to_results(match)
    arm(match, 1, "second_chance")
    t0 = next_question(match)
    match.vote("b1", 2, t0, ALL)
    match.vote("b2", 2, t0, ALL)
    b = team(match, 1)
    assert b.locked_at is None and b.first_option == 2 and not b.votes
    match.vote("b1", 0, t0 + 1, ALL)
    match.vote("b2", 0, t0 + 1, ALL)
    assert b.option == 0


def test_fifty_fifty_and_peek_during_the_question():
    match = powered()
    t0 = open_question(match)
    a = team(match, 0)
    a.held = ["fifty_fifty", "peek"]
    with pytest.raises(TeamMatchError):
        match.use_now("a2", "fifty_fifty")  # só o capitão
    match.use_now("a1", "fifty_fifty")
    assert len(a.hidden) == 2 and 0 not in a.hidden
    match.use_now("a1", "peek", target_team=1)
    match.vote("b1", 3, t0, ALL)
    assert match.view(t0, "a2").teams[1].votes[0].option == 3


def test_silence_hides_teammates_votes():
    match = powered()
    to_results(match)
    arm(match, 0, "silence", target_team=1)
    t0 = next_question(match)
    match.vote("b1", 3, t0, ALL)
    assert match.view(t0, "b2").teams[1].votes == []
    assert match.view(t0, "b1").teams[1].votes[0].option == 3


def test_team_x1_with_representatives_and_bets():
    match = TeamMatch.create(
        {"a1": 0, "a2": 0, "b1": 1, "b2": 1, "c1": 2, "c2": 2}, [question(f"q{i}") for i in range(5)],
        answer_seconds=10, now=0, rng=random.Random(3), powers=True, bank=bank(),
        statements=[x1.DuelQuestion(id=f"vf{i}", theme="T", kind="true_false", text="V?", options=["V", "F"], answer=0, fact="F.") for i in range(6)],
    )
    everyone = ["a1", "a2", "b1", "b2", "c1", "c2"]
    match.advance(0, everyone)
    while match.phase != "answering":
        match.advance(match.phase_ends_at, everyone)
    match.advance(match.deadline(), everyone)
    a = team(match, 0)
    a.mythics = ["duel"]
    match.arm(a.next_captain, "duel", target_team=1)
    match.advance(match.phase_ends_at, everyone)
    assert match.phase == "duel_choosing"
    with pytest.raises(TeamMatchError):
        match.choose("c1", "c2")  # o time C não está no X1
    match.choose("a1", "a2")
    match.choose("a2", "a2")
    match.advance(match.phase_ends_at, everyone)
    assert match.phase == "duel_betting" and match.duel.challenger == "a2"
    assert set(match.duel.bettors) == {"c1", "c2"}
    match.duel_bet("c1", "a2", match.phase_started_at)
    match.advance(match.phase_ends_at, everyone)
    while match.phase in ("duel_answering", "duel_results"):
        if match.phase == "duel_answering":
            match.vote("a2", match.duel.question.answer, match.phase_started_at, everyone)
            match.vote(match.duel.rival, 1 - match.duel.question.answer if len(match.duel.question.options) == 2 else (match.duel.question.answer + 1) % 4, match.phase_started_at, everyone)
        match.advance(match.phase_ends_at, everyone)
    assert match.phase == "duel_end" and match.duel.winner == "a2"
    assert team(match, 0).duel_delta > 0 and team(match, 1).duel_delta < 0
    match.advance(match.phase_ends_at, everyone)
    assert match.phase in ("reading", "level")
