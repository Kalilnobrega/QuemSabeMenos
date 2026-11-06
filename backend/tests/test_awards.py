import random
from collections import Counter

from app.awards import Contest, Tally, award, draw_awards, sabotages, team_key
from app.events import PowerUpUse


def rng() -> random.Random:
    return random.Random(1)


def test_never_more_than_three_and_each_one_takes_one():
    contests = [Contest(kind, {pid: 5}) for kind, pid in [("exact", "a"), ("thief", "b"), ("hot", "c"), ("cold", "d")]]
    contests.append(Contest("fall", {"a": 9}))
    awards = draw_awards(contests, "abcd", rng())
    assert len(awards) == 3
    winners = [a.player_id for a in awards]
    assert len(winners) == len(set(winners))


def test_an_award_stays_out_when_who_earned_it_already_has_another():
    """O segundo colocado não leva: a frase seria falsa."""
    contests = [Contest("exact", {"a": 5}), Contest("thief", {"a": 5, "b": 2})]
    awards = draw_awards(contests, ["a", "b"], rng())
    assert [a.player_id for a in awards] == ["a"]


def test_a_tie_goes_to_who_has_no_award_yet():
    contests = [Contest("exact", {"a": 5}), Contest("thief", {"a": 5, "b": 5})]
    seen = set()
    for seed in range(20):
        winners = [a.player_id for a in draw_awards(contests, ["a", "b"], random.Random(seed))]
        assert len(winners) == len(set(winners))
        seen.add(frozenset(winners))
    assert frozenset({"a", "b"}) in seen


def test_who_left_the_room_takes_nothing():
    assert draw_awards([Contest("fall", {"gone": 90})], ["a"], rng()) == []


def test_lowest_contests_pick_the_smallest():
    tally = Tally()
    for pid, value in (("a", 2.0), ("b", 4.0), ("c", 1.0)):
        tally.sample("seconds", pid, value)
        tally.sample("seconds", pid, value)
    tally.sample("seconds", "d", 0.1)  # uma resposta só não faz média
    awards = draw_awards([tally.mean("quick_answer", "seconds", 5, 2)], "abcd", rng())
    assert [(a.player_id, a.amount) for a in awards] == [("c", 1.0)]


def test_runs_keep_the_longest():
    tally = Tally()
    for going in (True, True, True, False, True):
        tally.run("hot", "a", going)
    assert tally.peaks["hot"]["a"] == 3


def test_minimums_keep_dull_awards_out():
    tally = Tally()
    tally.add("thrown", "a")
    tally.add("received", "b", 2)
    assert [c.scores for c in tally.sabotage_contests()] == [{}, {"b": 2}]


def test_comeback_compares_the_middle_of_the_match_with_the_end():
    tally = Tally(half_places={"a": 3, "b": 1, "c": 2})
    awards = draw_awards([tally.comeback(["a", "b", "c"])], "abc", rng())
    assert [(x.kind, x.player_id, x.amount, x.from_place) for x in awards] == [("comeback", "a", 1, 3)]
    assert Tally(half_places={"a": 2, "b": 1}).comeback(["a", "b"]).scores == {}


def test_team_awards_have_the_team_and_no_player():
    made = award("team_thief", team_key(2), 35)
    assert made.team == 2 and made.player_id is None


def test_reflected_steal_counts_for_who_threw():
    steal = PowerUpUse(kind="steal", by="b", target="a", reflected_by="b")
    mirror = PowerUpUse(kind="mirror", by="a", target="a", reflected_by="b")
    thrown, received = sabotages([steal, mirror], frozenset({"steal", "mirror"}), ["a", "b"])
    assert Counter(thrown) == Counter({"a": 2}) and Counter(received) == Counter({"a": 2})
