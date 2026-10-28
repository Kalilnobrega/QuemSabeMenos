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


def test_losing_every_life_eliminates():
    game = new_game(3)
    assert game.phase == "answering" and game.question.difficulty == "medium"
    play(game, right=["p0", "p1"])
    assert game.contender("p2").lives == LIVES - 1
    for _ in range(LIVES - 1):
        play(game, right=["p0", "p1"])
    assert game.contender("p2").out_round == LIVES
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
    for _ in range(LIVES):
        play(game, right=["p0", "p1", "p2"])  # p3 cai primeiro
    for _ in range(LIVES):
        play(game, right=["p0", "p1"])  # depois p2 → X1
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


def powers_game(players: int = 4, kind: str = "choices") -> Survival:
    pool = questions() if kind == "choices" else statements()
    game = Survival.create(kind, [f"p{i}" for i in range(players)], pool, set(), random.Random(5), now=0, powers=True, powerup_max=3)
    for pid in game.held:
        game.held[pid] = []
    return game


def to_results(game: Survival, right: list[str]) -> None:
    """Joga até a revelação da próxima pergunta."""
    if game.phase in ("starting", "results"):
        game.advance(0)
    while game.phase in ("level", "reading"):
        game.advance(0)
    for pid in game.answering_ids():
        game.answer(pid, game.question.answer if pid in right else (game.question.answer + 1) % len(game.question.options), 0)
    game.advance(0)


def test_powers_deal_one_power_without_the_true_false_spoilers():
    game = Survival.create("true_false", [f"p{i}" for i in range(30)], statements(), set(), random.Random(1), 0, powers=True)
    dealt = {kinds[0] for kinds in game.held.values()}
    assert len(game.held["p0"]) == 1
    assert not dealt & {"fifty_fifty", "decoy"}


def test_shield_holds_a_life_once():
    game = powers_game()
    to_results(game, right=["p0", "p1", "p2"])
    game.held["p3"] = ["shield"]
    game.arm("p3", "shield", None)
    to_results(game, right=["p0", "p1", "p2"])
    pick = next(p for p in game.picks if p.player_id == "p3")
    assert pick.shielded and not pick.lost_life
    assert game.contender("p3").lives == 2  # perdeu só a primeira


def test_steal_takes_the_life_the_target_loses():
    game = powers_game()
    to_results(game, right=["p1", "p2", "p3"])  # p0 fica com 2
    game.held["p0"] = ["steal"]
    game.arm("p0", "steal", "p1")
    to_results(game, right=["p0", "p2", "p3"])
    assert game.contender("p1").lives == 2
    assert game.contender("p0").lives == 3
    assert next(p for p in game.picks if p.player_id == "p1").stolen_by == "p0"


def test_reverse_sends_the_sabotage_back():
    game = powers_game()
    to_results(game, right=["p0", "p1", "p2", "p3"])
    game.held["p1"] = ["reverse"]
    game.arm("p1", "reverse", None)
    to_results(game, right=["p0", "p1", "p2", "p3"])
    game.held["p0"] = ["accelerator"]
    game.arm("p0", "accelerator", "p1")
    game.advance(0)
    use = next(u for u in game.active if u.kind == "accelerator")
    assert use.target == "p0" and use.reflected_by == "p1"


def test_three_right_in_a_row_gives_a_power():
    game = powers_game()
    for _ in range(3):
        to_results(game, right=["p0", "p1", "p2"])
    assert len(game.held["p0"]) == 1
    assert any(g.player_id == "p0" and g.gain.reason == "streak" for g in game.gifts)


def test_ghosts_get_sabotages_and_only_hit_the_living():
    game = powers_game(players=5)
    for _ in range(3):
        to_results(game, right=["p0", "p1", "p2", "p3"])  # p4 cai na 3
    assert not game.contender("p4").alive
    for _ in range(3):
        to_results(game, right=["p0", "p1", "p2", "p3"])
    assert game.held["p4"] and game.held["p4"][0] in ("scramble", "accelerator", "mirror", "magnifier", "flashbang")
    kind = game.held["p4"][0]
    with pytest.raises(SurvivalError):
        game.arm("p4", kind, "p4")
    game.arm("p4", kind, "p0")
    game.advance(0)
    assert any(u.kind == kind and u.target == "p0" for u in game.active)


def test_resurrection_brings_a_ghost_back_with_one_life():
    game = powers_game(players=4)
    for _ in range(3):
        to_results(game, right=["p0", "p1", "p2"])
    game.mythics["p3"] = ["resurrection"]
    game.arm("p3", "resurrection", None)
    assert game.contender("p3").alive and game.contender("p3").lives == 1
    assert game.revived == ["p3"]


def test_no_powers_once_the_duel_starts():
    game = powers_game(players=3)
    for _ in range(3):
        to_results(game, right=["p0", "p1"])  # p2 cai na 3: vem o X1
    game.held["p0"] = ["shield"]
    assert not game.can_arm()
    with pytest.raises(SurvivalError):
        game.arm("p0", "shield", None)


def test_decoy_adds_options_only_for_the_target_and_shields_the_thrower():
    game = powers_game()
    to_results(game, right=["p0", "p1", "p2", "p3"])
    game.held["p0"] = ["decoy"]
    game.arm("p0", "decoy", "p1")
    game.advance(0)
    view = game.view(0, "p1", [c.id for c in game.contenders])
    assert len(view.options) == 6
    assert len(game.view(0, "p2", [c.id for c in game.contenders]).options) == 4
    fake = next(i for i, text in enumerate(view.options) if text not in game.question.options)
    game.advance(0)  # libera as respostas
    game.answer("p1", fake, 0)
    for pid in ("p0", "p2", "p3"):
        game.answer(pid, game.question.answer, 0)
    game.advance(0)
    assert next(p for p in game.picks if p.player_id == "p1").decoy
    assert game.lasting["p0"]["shield"] == 1


def test_silenced_player_does_not_see_lives_or_the_reveal():
    game = powers_game()
    to_results(game, right=["p0", "p1", "p2", "p3"])
    game.held["p0"] = ["silence"]
    game.arm("p0", "silence", "p1")
    to_results(game, right=["p0", "p1", "p2", "p3"])
    view = game.view(0, "p1", [c.id for c in game.contenders])
    assert view.correct_option is None and view.picks == []
    assert {s.lives for s in view.survivors if s.player_id != "p1"} == {-1}
    with pytest.raises(SurvivalError):
        game.held["p1"] = ["shield"]
        game.arm("p1", "shield", None)


def test_second_chance_lasts_one_question_in_true_false_and_two_in_choices():
    for kind, rounds in (("true_false", 1), ("choices", 2)):
        game = powers_game(kind=kind)
        to_results(game, right=["p0", "p1", "p2", "p3"])
        game.held["p0"] = ["second_chance"]
        game.arm("p0", "second_chance", None)
        game.advance(0)
        assert game.lasting["p0"]["second_chance"] == rounds
