import random
from dataclasses import dataclass

import pytest

from app import powerups
from app.estimate import (
    ANSWER_SECONDS,
    LAST_WORD_SECONDS,
    LEGENDARY,
    MATH_SECONDS,
    MYTHICS,
    POWERS,
    Estimate,
    EstimateError,
    EstimateQuestion,
    answer_digits,
    apply_math,
    draw_math,
    draw_range,
    error_percent,
    guess_points,
    load_estimates,
    math_path,
)
from app.events import PowerUpUse


@dataclass
class P:
    id: str
    score: int = 50
    answer_ms: int = 0


def question(qid: str, answer: float, scale: float | None = None, difficulty: str = "easy") -> EstimateQuestion:
    return EstimateQuestion(
        id=qid, theme="Teste", difficulty=difficulty, text="Quanto?", answer=answer, scale=scale, fact="Curiosidade."
    )


def test_bank_has_30_numeric_questions_per_theme():
    bank = load_estimates()
    assert len({q.id for q in bank}) == len(bank)
    themes = {q.theme for q in bank}
    assert len(themes) == 12
    assert all(sum(1 for q in bank if q.theme == t) == 30 for t in themes)
    for t in themes:  # 10 de cada nível em cada tema
        assert all(sum(1 for q in bank if q.theme == t and q.difficulty == d) == 10 for d in ("easy", "medium", "hard"))


def test_medium_points_shrink_with_the_distance_and_turn_into_losses_past_30_percent():
    q = question("q", 200)
    points = lambda guess: guess_points(error_percent(q, guess), "medium")
    assert points(200) == 24  # cravou: 16 + 8 de bônus
    assert points(201) == 16  # 0,5%: sem o bônus
    assert points(210) == 13  # 5%
    assert points(212) == 13 and points(228) == 9  # 6% ganha mais que 14%
    assert points(260) == 0  # 30%: nem ganha nem perde
    assert points(290) == -4  # 45%
    assert points(320) == -8  # 60%
    assert points(380) == -15 and points(5000) == -15  # de 90% em diante
    assert guess_points(None, "medium") == -15


def test_easy_is_an_obligation_and_hard_is_worth_the_risk():
    assert [guess_points(e, "easy") for e in (0, 10, 20, 50, 60, None)] == [12, 4, 0, -15, -20, -20]
    assert [guess_points(e, "hard") for e in (0, 10, 35, 50, 105, None)] == [36, 17, 0, -2, -10, -10]


def test_shorter_matches_are_worth_more_per_question():
    assert guess_points(0, "hard", scale=2) == 72  # 10 perguntas: o dobro
    assert guess_points(None, "easy", scale=2) == -40


def test_years_use_the_question_scale():
    q = question("ano", 1822, scale=50)
    assert error_percent(q, 1820) == 4  # 2 anos de 50 = 4%, não 0,1%
    assert guess_points(error_percent(q, 1820), "medium") == 14
    assert guess_points(error_percent(q, 1700), "medium") == -15


def test_negative_answers_measure_distance_from_the_absolute_value():
    q = question("frio", -273.15)
    assert guess_points(error_percent(q, -270), "medium") == 15  # 1,15%


def test_match_flow_scores_and_sorts_by_distance():
    pool = [question(f"{d}{i}", 100, difficulty=d) for d in ("hard", "medium", "easy") for i in range(3)]
    used: set[str] = set()
    game = Estimate.create(pool, 3, used, random.Random(1), now=0)
    assert len(game.questions) == 3 and len(used) == 3
    assert [q.difficulty for q in game.questions] == ["easy", "medium", "hard"]  # como no clássico
    assert game.phase == "starting" and game.view(0).text is None
    ana, bia, caio = P("ana"), P("bia"), P("caio")
    players = [ana, bia, caio]

    with pytest.raises(EstimateError, match="Agora não dá"):
        game.guess("ana", 100, now=1)  # na abertura ainda não dá
    game.advance(7, players)
    assert game.phase == "answering" and game.view(7).text  # sem tempo de leitura
    game.guess("ana", 140, now=8)
    game.guess("bia", 100, now=9)
    with pytest.raises(EstimateError, match="já chutou"):
        game.guess("bia", 90, now=9)
    assert game.everyone_answered(["ana", "bia"]) and not game.everyone_answered(["ana", "bia", "caio"])
    assert game.view(9, "ana").answer is None  # a resposta só aparece na revelação

    game.advance(27, players)
    view = game.view(27, "ana")
    assert view.phase == "results" and view.answer == 100
    assert [g.player_id for g in view.guesses] == ["bia", "ana", "caio"]
    assert view.guesses[0].exact and view.guesses[2].value is None
    # Fácil numa partida de 3 (vale 20/3 por pergunta): 40% de erro, cravou, sem chute.
    assert (ana.score, bia.score, caio.score) == (50 - 67, 50 + 80, 50 - 133)
    assert caio.answer_ms == ANSWER_SECONDS * 1000

    game.mark_ready("ana")
    assert not game.everyone_ready(["ana", "bia"])
    for _ in range(2):
        game.advance(30, players)
        assert game.phase == "level" and game.view(30).text is None  # o nível sobe a cada pergunta aqui
        game.advance(34, players)
        game.advance(55, players)
    game.advance(60, players)
    assert game.phase == "finished"


def test_late_guesses_are_rejected():
    game = Estimate.create(
        [question("q", 10, difficulty="hard")], 1, set(), random.Random(1), now=0
    )  # 1 pergunta: a difícil
    game.advance(6, [])
    with pytest.raises(EstimateError, match="tempo acabou"):
        game.guess("ana", 10, now=6 + ANSWER_SECONDS + 2)


# --- poderes ------------------------------------------------------------------


def powered(rounds: int = 6, difficulty: str = "medium", themes: tuple[str, ...] = ("Teste",)) -> Estimate:
    """Partida com poderes em que toda resposta é 100: 115 ganha +8, 170 perde 10 e sem chute perde 15 (médias)."""
    questions = [question(f"q{i}", 100, difficulty=difficulty) for i in range(rounds)]
    bank = [q.model_copy(update={"id": f"{t}-{i}", "theme": t}) for t in themes for i, q in enumerate(questions)]
    game = Estimate(questions=questions, powers=True, rng=random.Random(1), bank=bank, used={q.id for q in questions})
    game._enter("starting", 0, 0)
    return game


def ask(game: Estimate, players: list[P], **guesses: float) -> None:
    """Abre a próxima pergunta, recebe os chutes e fecha."""
    game.advance(game.phase_ends_at, players)
    for pid, value in guesses.items():
        game.guess(pid, value, game.phase_started_at + 1)
    game.advance(game.phase_started_at + 2, players)


def give(game: Estimate, pid: str, kind: str, target: str | None = None, ids: tuple[str, ...] = ("a", "b")) -> None:
    game.held.setdefault(pid, []).append(kind)
    game.arm(pid, kind, target, list(ids), None)


def result(game: Estimate, pid: str):
    return next(g for g in game.results if g.player_id == pid)


def test_without_powers_nothing_changes():
    a = P("a")
    game = Estimate.create(
        [question(f"q{i}", 100) for i in range(10)], 10, set(), random.Random(1), 0, ["a"], powers=False
    )
    assert not game.held
    ask(game, [a], a=115)
    view = game.view(game.phase_started_at, "a")
    assert not view.powers and not view.can_arm and view.powerups == []
    assert a.score == 50 + result(game, "a").delta


def test_everyone_starts_with_one_power():
    for seed in range(40):
        game = Estimate.create(
            [question(f"q{i}", 100) for i in range(10)], 10, set(), random.Random(seed), 0, ["a", "b"], powers=True
        )
        assert all(len(game.held[pid]) == 1 for pid in ("a", "b"))
        assert game.view(0, "a").starting_powerup == game.held["a"][0]


def test_double_doubles_gains_and_losses():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "double")
    ask(game, [a, b], a=115, b=115)
    assert result(game, "a").delta == 16 and result(game, "a").doubled
    assert result(game, "b").delta == 8
    give(game, "a", "double")
    ask(game, [a, b], a=170, b=170)
    assert result(game, "a").delta == 2 * result(game, "b").delta < 0


def test_double_triples_the_loss_on_hard_questions():
    a = P("a")
    game = powered(difficulty="hard")
    ask(game, [a], a=100)
    give(game, "a", "double", ids=("a",))
    ask(game, [a])
    assert result(game, "a").delta == -30


def test_shield_holds_one_loss_and_then_ends():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "shield")
    before = a.score
    ask(game, [a, b], a=170, b=100)
    assert result(game, "a").delta == 0 and result(game, "a").shielded == 10
    assert a.score == before
    ask(game, [a, b], a=170, b=100)
    assert result(game, "a").delta == -10


def test_unused_shield_breaks_after_two_questions():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "shield")
    ask(game, [a, b], a=100, b=100)
    assert result(game, "a").expired == []
    ask(game, [a, b], a=100, b=100)
    assert result(game, "a").expired == ["shield"]


def test_steal_takes_ten_and_half_of_the_gain():
    a, b = P("a", score=0), P("b", score=0)
    game = powered()
    ask(game, [a, b], a=100, b=100)
    a.score = b.score = 0
    give(game, "a", "steal", "b")
    assert all(use.kind != "steal" for use in game.view(game.phase_ends_at, "b").active)
    ask(game, [a, b], a=170, b=115)
    assert result(game, "a").stolen == result(game, "b").robbed == 14
    assert a.score == -10 + 14 and b.score == 8 - 14


def test_shield_blocks_steal():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "b", "shield")
    give(game, "a", "steal", "b")
    ask(game, [a, b], a=100, b=170)
    assert result(game, "a").stolen == 0 and result(game, "b").robbed == 0


def test_second_chance_tells_the_side_and_the_new_guess_is_worth_half():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    give(game, "a", "second_chance", ids=("a",))
    game.advance(game.phase_ends_at, [a])
    at = game.phase_started_at
    game.guess("a", 170, at + 1)
    view = game.view(at + 1, "a")
    assert view.my_guess is None and view.first_guess == 170 and view.retry_hint == "lower"
    assert not game.everyone_answered(["a"])
    game.guess("a", 115, at + 2)
    assert game.view(at + 2, "a").retry_hint is None
    game.advance(at + 3, [a])
    assert result(game, "a").delta == 4
    assert result(game, "a").value == 115 and result(game, "a").first_value == 170


def test_second_chance_keeps_a_winning_guess_and_the_first_loss_if_nobody_retries():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    give(game, "a", "second_chance", ids=("a",))
    ask(game, [a], a=115)  # já ganhava QI: não gasta
    assert result(game, "a").delta == 8 and result(game, "a").first_value is None
    ask(game, [a], a=30)  # 70% de erro: perde, sem tentar de novo fica com ele
    assert result(game, "a").delta == -10 and result(game, "a").value == 30


def test_reverse_sends_the_sabotage_back_once():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "b", "reverse")
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "mirror", "b")
    game.advance(game.phase_ends_at, [a, b])
    use = next(u for u in game.active if u.kind == "mirror")
    assert use.target == "a" and use.reflected_by == "b"
    assert not game._affects("reverse", "b")


def test_reverse_only_shows_to_its_owner():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "b", "reverse")
    game.advance(game.phase_ends_at, [a, b])
    assert any(u.kind == "reverse" for u in game.view(game.phase_started_at, "b").active)
    assert not any(u.kind == "reverse" for u in game.view(game.phase_started_at, "a").active)


def test_theme_swaps_the_next_question_and_cannot_be_undone():
    a = P("a")
    game = powered(themes=("Teste", "Outro"))
    ask(game, [a], a=100)
    assert "Outro" in game.theme_choices
    game.held["a"] = ["theme"]
    game.arm("a", "theme", None, ["a"], "Outro")
    assert game.questions[game.round + 1].theme == "Outro"
    with pytest.raises(EstimateError):
        game.disarm("a")


def test_disarm_returns_the_power_to_the_hand():
    a = P("a")
    game = powered()
    ask(game, [a], a=110)
    give(game, "a", "shield", ids=("a",))
    game.ready.add("a")
    game.disarm("a")
    assert game.held["a"] == ["shield"] and "a" not in game.armed and "a" not in game.ready


def test_backpack_gives_a_slot_and_a_power_right_away():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    game.held["a"] = ["backpack"]
    game.arm("a", "backpack", None, ["a"], None)
    assert game.capacity("a") == game.powerup_max + 1
    assert len(game.held["a"]) == 1 and game.held["a"][0] != "backpack"
    assert "a" not in game.armed


def test_silence_hides_time_guesses_and_reveal_for_two_questions():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "silence", "b")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    game.guess("a", 100, at + 1)
    assert game.view(at + 1, "b").answered == [] and game.view(at + 1, "a").answered == ["a"]
    game.advance(at + 2, [a, b])
    hidden = game.view(game.phase_started_at, "b")
    assert hidden.answer is None and hidden.guesses == [] and hidden.fact is None and hidden.silenced_rounds == 2
    assert not hidden.can_arm
    assert game.everyone_ready(["b"])
    game.held["b"] = ["shield"]
    with pytest.raises(EstimateError):
        game.arm("b", "shield", None, ["a", "b"], None)
    ask(game, [a, b], a=100, b=100)
    assert game.view(game.phase_started_at, "b").silenced_rounds == 1
    ask(game, [a, b], a=100, b=100)
    assert game.view(game.phase_started_at, "b").answer == 100


def test_three_earning_guesses_in_a_row_give_a_power():
    a = P("a")
    game = powered()
    game.powerup_max = 3
    ask(game, [a], a=115)
    ask(game, [a], a=115)
    assert result(game, "a").gained is None
    ask(game, [a], a=115)
    assert result(game, "a").gained.reason == "streak"
    assert len(game.held["a"]) == 1 and game.right_runs["a"] == 0


def test_a_losing_guess_resets_the_run_even_with_a_shield():
    a = P("a")
    game = powered()
    ask(game, [a], a=115)
    ask(game, [a], a=115)
    give(game, "a", "shield", ids=("a",))
    ask(game, [a], a=170)
    assert result(game, "a").gained is None and game.right_runs["a"] == 0


def test_far_behind_for_three_questions_gives_a_power():
    a, b = P("a", score=0), P("b", score=500)
    game = powered()
    for _ in range(3):
        ask(game, [a, b], a=170, b=100)
    assert result(game, "a").gained.reason == "comeback"


def test_full_hands_get_nothing_and_the_last_question_gives_nothing():
    a = P("a")
    game = powered(rounds=4)
    game.held["a"] = ["shield"]
    game.powerup_max = 1
    for _ in range(3):
        ask(game, [a], a=115)
    assert result(game, "a").gained is None and game.held["a"] == ["shield"]
    game.powerup_max = 3
    ask(game, [a], a=115)
    assert result(game, "a").gained is None
    assert not game.can_arm and game.theme_choices == []


# --- poderes só do Chutômetro -----------------------------------------------------


def test_range_contains_the_answer_off_center_and_only_its_owner_sees_it():
    for answer, scale, difficulty in (
        (100, None, "medium"),
        (1500, 50, "hard"),
        (-273.15, None, "easy"),
        (3.14, None, "easy"),
    ):
        for seed in range(50):
            q = question("q", answer, scale, difficulty)
            drawn = draw_range(q, random.Random(seed))
            assert drawn.low < answer < drawn.high
            assert answer != (drawn.low + drawn.high) / 2
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    game.advance(game.phase_ends_at, [a, b])
    game.held["a"] = ["range"]
    game.use_now("a", "range")
    at = game.phase_started_at + 1
    assert game.view(at, "a").range_hint is not None and game.view(at, "b").range_hint is None
    with pytest.raises(EstimateError):  # uma por pergunta, e a mão ficou vazia
        game.use_now("a", "range")
    game.advance(game.phase_started_at + 2, [a, b])
    assert game.view(game.phase_started_at + 2, "a").range_hint is None  # na revelação, some
    game.advance(game.phase_ends_at, [a, b])
    assert not game.ranges


def test_range_is_not_armed_in_the_reveal():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    game.held["a"] = ["range"]
    with pytest.raises(EstimateError):
        game.arm("a", "range", None, ["a"], None)


def test_wide_margin_doubles_the_zones_for_who_used_it():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "wide_margin")
    ask(game, [a, b], a=145, b=145)  # 45% de erro: passa dos 30% das médias, mas não dos 60% da Margem
    assert result(game, "a").delta > 0 and result(game, "b").delta < 0
    assert result(game, "a").error_percent == result(game, "b").error_percent == 45
    at = game.phase_started_at
    assert game.view(at, "a").scoring.break_even_percent == 60
    assert game.view(at, "b").scoring.break_even_percent == 30
    game.advance(game.phase_ends_at, [a, b])
    assert game.view(game.phase_started_at, "a").scoring.break_even_percent == 30  # só vale uma pergunta


def test_wide_margin_avoids_spending_the_second_chance():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    give(game, "a", "wide_margin", ids=("a",))
    game.lasting["a"] = {"second_chance": 2}
    game.advance(game.phase_ends_at, [a])
    game.guess("a", 145, game.phase_started_at + 1)
    assert "a" in game.guesses and "a" not in game.first_guesses


def test_hot_keys_shows_the_answer_digits_only_to_who_used_it():
    assert answer_digits(1500) == ["0", "1", "5"]
    assert answer_digits(-273.15) == ["1", "2", "3", "5", "7"]
    assert answer_digits(0.5) == ["0", "5"]
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "hot_keys")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert game.view(at, "a").hot_digits == ["0", "1"] and game.view(at, "b").hot_digits is None
    game.advance(at + 1, [a, b])
    assert game.view(at + 1, "a").hot_digits is None


def test_nudge_moves_the_guess_by_10_to_30_percent_and_stays_hidden_until_the_reveal():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "nudge", "b")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert not any(u.kind == "nudge" for u in game.view(at, "b").active)
    assert any(u.kind == "nudge" for u in game.view(at, "a").active)
    game.guess("b", 100, at + 1)
    assert game.view(at + 1, "b").my_guess == 100  # o alvo só descobre na régua
    game.advance(at + 2, [a, b])
    moved = result(game, "b")
    assert moved.nudged_from == 100 and 10 <= moved.error_percent <= 30 and not moved.exact
    assert any(u.kind == "nudge" for u in game.view(at + 2, "b").active)


def test_no_guess_means_nothing_to_nudge():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "nudge", "b")
    ask(game, [a, b], a=100)
    assert result(game, "b").value is None and result(game, "b").nudged_from is None


@pytest.mark.parametrize(
    "kind",
    ["broken_keys", "shuffled_keys", "perfectionist", "nudge", "swap", "runaway_keys", "short_circuit", "double_click"],
)
def test_keypad_sabotages_need_a_target_and_the_reverse_sends_them_back(kind):
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    game.held["a"] = [kind]
    with pytest.raises(EstimateError):
        game.arm("a", kind, None, ["a", "b"], None)
    give(game, "b", "reverse")
    game.arm("a", kind, "b", ["a", "b"], None)
    game.advance(game.phase_ends_at, [a, b])
    use = next(u for u in game.active if u.kind == kind)
    assert use.target == "a" and use.reflected_by == "b"


def test_new_powers_stay_out_of_the_other_modes():
    new = {
        "range",
        "wide_margin",
        "hot_keys",
        "broken_keys",
        "shuffled_keys",
        "perfectionist",
        "nudge",
        "sniper",
        "swap",
        "runaway_keys",
        "short_circuit",
        "double_click",
    }
    assert new <= set(POWERS)
    assert not new & (set(powerups.POWERUPS) | powerups.TARGETED | powerups.INSTANT)


def test_powers_taken_out_of_this_mode_stay_out():
    assert not {"investment", "scramble", "magnifier", "accelerator", "flashbang", "peek"} & set(POWERS)


def test_nudge_stays_between_10_and_30_percent_on_both_sides():
    shifts = []
    for seed in range(200):
        a, b = P("a"), P("b")
        game = powered()
        game.rng = random.Random(seed)
        ask(game, [a, b], a=100, b=100)
        give(game, "a", "nudge", "b")
        ask(game, [a, b], a=100, b=100)
        shifts.append(result(game, "b").value - 100)
    assert all(10 <= abs(shift) <= 30 for shift in shifts)
    assert min(shifts) < 0 < max(shifts)
    assert len({abs(shift) for shift in shifts}) > 5


def snipe(game: Estimate, players: list[P], pid: str) -> float:
    """Abre a próxima pergunta e usa o Sniper na hora."""
    game.advance(game.phase_ends_at, players)
    game.held[pid] = ["sniper"]
    game.use_now(pid, "sniper")
    return game.phase_started_at + 1


def test_sniper_halves_the_zone_and_doubles_the_gain_during_the_question():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    at = snipe(game, [a, b], "a")
    assert game.view(at, "a").scoring.break_even_percent == 15
    assert game.view(at, "a").scoring.max_points == 32
    assert game.view(at, "b").scoring.break_even_percent == 30
    game.guess("a", 105, at)  # 5% de erro: na zona de 15% vale 11 de 16, em dobro
    game.guess("b", 105, at)
    game.advance(at + 1, [a, b])
    assert result(game, "a").delta == 22 and result(game, "b").delta == 13


def test_sniper_turns_a_near_miss_into_a_loss():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    at = snipe(game, [a, b], "a")
    game.guess("a", 120, at)  # 20%: ganha sem o Sniper, perde com ele
    game.guess("b", 120, at)
    game.advance(at + 1, [a, b])
    assert result(game, "a").delta < 0 < result(game, "b").delta


def test_sniper_is_not_armed_in_the_reveal():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    game.held["a"] = ["sniper"]
    with pytest.raises(EstimateError):
        game.arm("a", "sniper", None, ["a"], None)


def test_swap_trades_the_guesses_in_the_reveal_and_stays_hidden_until_then():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "swap", "b")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert not any(u.kind == "swap" for u in game.view(at, "b").active)
    game.guess("a", 170, at + 1)
    game.guess("b", 100, at + 3)
    assert game.view(at + 3, "b").my_guess == 100
    game.advance(at + 4, [a, b])
    assert result(game, "a").value == 100 and result(game, "a").swapped_from == 170 and result(game, "a").exact
    assert result(game, "b").value == 170 and result(game, "b").swapped_from == 100 and result(game, "b").delta < 0
    assert result(game, "a").elapsed_ms == 1000 and result(game, "b").elapsed_ms == 3000  # o tempo é de cada um


def test_swap_needs_both_guesses():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "swap", "b")
    ask(game, [a, b], b=100)
    assert result(game, "a").value is None and result(game, "b").value == 100
    assert result(game, "b").swapped_from is None


def test_reverse_cancels_the_swap():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "b", "reverse")
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "swap", "b")
    ask(game, [a, b], a=170, b=100)
    assert result(game, "a").value == 170 and result(game, "b").value == 100
    assert result(game, "a").swapped_from is None


# --- lendários -------------------------------------------------------------------


def give_legendary(game: Estimate, pid: str, kind: str, ids: tuple[str, ...] = ("a", "b", "c")) -> None:
    game.legendaries.setdefault(pid, []).append(kind)
    game.arm(pid, kind, None, list(ids), None, legendary=True)


class Lucky(random.Random):
    """Sorteio que sempre cai na menor chance: todo poder ganho vem lendário."""

    def random(self) -> float:
        return 0.05  # acima do mítico (2%), abaixo do lendário


def test_legendary_sabotage_reaches_everyone_but_who_used_it():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=100, b=100, c=100)
    give_legendary(game, "a", "shuffled_keys")
    assert game.view(game.phase_started_at, "a").armed.legendary
    game.advance(game.phase_ends_at, [a, b, c])
    use = next(u for u in game.active if u.kind == "shuffled_keys")
    assert use.legendary and use.target is None
    assert game._affects("shuffled_keys", "b") and game._affects("shuffled_keys", "c")
    assert not game._affects("shuffled_keys", "a")


def test_reverse_does_not_stop_a_legendary():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "b", "reverse")
    ask(game, [a, b], a=100, b=100)
    give_legendary(game, "a", "mirror", ("a", "b"))
    game.advance(game.phase_ends_at, [a, b])
    assert game._affects("mirror", "b") and not game._affects("mirror", "a")
    assert next(u for u in game.active if u.kind == "mirror").reflected_by is None


def test_legendary_silence_mutes_everyone_else():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=100, b=100, c=100)
    give_legendary(game, "a", "silence")
    game.advance(game.phase_ends_at, [a, b, c])
    assert game.is_silenced("b") and game.is_silenced("c") and not game.is_silenced("a")


def test_legendary_nudge_moves_all_the_other_guesses():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=100, b=100, c=100)
    give_legendary(game, "a", "nudge")
    ask(game, [a, b, c], a=100, b=100, c=100)
    assert result(game, "a").nudged_from is None and result(game, "a").value == 100
    assert result(game, "b").nudged_from == 100 and result(game, "c").nudged_from == 100


def test_legendary_steal_shares_one_and_a_half_steals_and_the_leader_pays_more():
    a, b, c = P("a"), P("b", score=80), P("c")
    game = powered()
    ask(game, [a, b, c], a=170, b=170, c=170)
    give_legendary(game, "a", "steal")
    ask(game, [a, b, c], a=170, b=170, c=170)
    assert result(game, "b").robbed == 10 and result(game, "c").robbed == 5
    assert result(game, "a").stolen == 15


def test_shield_holds_its_part_of_a_legendary_steal():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=100, b=100, c=100)
    give_legendary(game, "a", "steal")
    game.lasting["b"] = {"shield": 2}
    ask(game, [a, b, c], a=170, b=170, c=170)
    assert result(game, "b").shielded and result(game, "b").robbed == 0
    assert result(game, "c").robbed > 0 and result(game, "a").stolen == result(game, "c").robbed


def test_legendary_goes_back_to_its_place_when_disarmed_and_needs_to_be_held():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    with pytest.raises(EstimateError):
        game.arm("a", "mirror", None, ["a", "b"], None, legendary=True)
    give_legendary(game, "a", "mirror", ("a", "b"))
    assert game.legendaries["a"] == []
    game.disarm("a")
    assert game.legendaries["a"] == ["mirror"] and "mirror" not in game.held.get("a", [])
    assert game.view(game.phase_started_at, "a").legendary_powerups == ["mirror"]


def test_gained_powers_can_come_legendary_but_never_the_swap():
    assert "swap" not in LEGENDARY and LEGENDARY
    assert all(kind in POWERS for kind in LEGENDARY)
    a = P("a")
    game = powered()
    game.rng = Lucky(1)
    for _ in range(3):
        ask(game, [a], a=115)
    gained = result(game, "a").gained
    assert gained.legendary and gained.kind in LEGENDARY and game.legendaries["a"] == [gained.kind]


def test_legendaries_take_up_space_in_the_hand():
    a = P("a")
    game = powered()
    game.powerup_max = 1
    game.legendaries["a"] = ["mirror"]
    for _ in range(3):
        ask(game, [a], a=115)
    assert result(game, "a").gained is None


# --- como se ganha poder -----------------------------------------------------------


def test_any_guess_that_earns_iq_counts_for_the_streak():
    a = P("a")
    game = powered(rounds=10)
    for _ in range(2):
        ask(game, [a], a=125)  # 25%: ganha QI nas médias
    assert game.right_runs["a"] == 2 and result(game, "a").gained is None
    ask(game, [a], a=125)
    assert result(game, "a").gained is not None and result(game, "a").gained.reason == "streak"
    assert game.right_runs["a"] == 0


@pytest.mark.parametrize("difficulty", ["medium", "hard"])
def test_an_exact_guess_gives_a_power_on_medium_and_hard(difficulty):
    a = P("a")
    game = powered(difficulty=difficulty)
    ask(game, [a], a=100)
    gained = result(game, "a").gained
    assert gained is not None and gained.reason == "exact"
    assert game.right_runs["a"] == 1  # a cravada também soma na sequência


def test_an_exact_guess_gives_nothing_on_easy():
    a = P("a")
    game = powered(difficulty="easy")
    ask(game, [a], a=100)
    assert result(game, "a").gained is None


def test_exact_and_streak_together_give_one_power_and_the_streak_waits():
    a = P("a")
    game = powered()
    ask(game, [a], a=110)
    ask(game, [a], a=110)
    ask(game, [a], a=100)
    assert result(game, "a").gained.reason == "exact" and game.right_runs["a"] == 3
    ask(game, [a], a=110)
    assert result(game, "a").gained.reason == "streak" and game.right_runs["a"] == 0


def test_wide_margin_helps_the_streak():
    a = P("a")
    game = powered()
    ask(game, [a], a=110)
    give(game, "a", "wide_margin", ids=("a",))
    ask(game, [a], a=145)  # 45%: perderia sem a Margem larga
    assert result(game, "a").delta > 0 and game.right_runs["a"] == 2


def test_full_hands_lose_the_exact_power():
    a = P("a")
    game = powered()
    game.powerup_max = 1
    game.held["a"] = ["shield"]
    ask(game, [a], a=100)
    assert result(game, "a").gained is None and game.held["a"] == ["shield"]


# --- mítico: Matemática --------------------------------------------------------------


def give_math(game: Estimate, target: str = "b", ids: tuple[str, ...] = ("a", "b")) -> None:
    game.mythics.setdefault("a", []).append("math")
    game.arm("a", "math", target, list(ids), None)


def test_math_always_has_a_path_into_the_gain_zone_for_every_question():
    for q in load_estimates():
        for seed in range(5):
            puzzle = draw_math(q.answer, random.Random(seed))
            assert len(puzzle.keys) == 9
            assert all(1 <= key.uses <= 3 for key in puzzle.keys)
            keys = {(key.op, key.value): key.uses for key in puzzle.keys}
            value = puzzle.start
            for step in math_path(puzzle.start, q.answer):
                assert keys[(step.op, step.value)] > 0, q.id
                keys[(step.op, step.value)] -= 1
                value = apply_math(value, step)
            assert guess_points(error_percent(q, value), q.difficulty) > 0, (q.id, value)


def test_math_keys_are_not_repeated_and_never_divide_by_zero():
    for seed in range(100):
        puzzle = draw_math(-273.15, random.Random(seed))
        pairs = [(key.op, key.value) for key in puzzle.keys]
        assert len(set(pairs)) == 9
        assert all(key.value != 0 for key in puzzle.keys)


def test_math_reaches_only_the_target_only_while_guessing_and_lasts_one_question():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give_math(game)
    assert game.mythics["a"] == []
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert game.view(at, "b").math is not None and game.view(at, "a").math is None
    game.guess("a", 100, at + 1)
    game.guess("b", 100, at + 1)
    game.advance(at + 2, [a, b])
    assert game.view(at + 2, "b").math is None
    game.advance(game.phase_ends_at, [a, b])
    assert game.view(game.phase_started_at, "b").math is None


def test_reverse_does_not_stop_math():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "b", "reverse")
    ask(game, [a, b], a=110, b=110)
    give_math(game)
    game.advance(game.phase_ends_at, [a, b])
    use = next(u for u in game.active if u.kind == "math")
    assert use.target == "b" and use.reflected_by is None
    assert game.view(game.phase_started_at, "b").math is not None


def test_math_needs_a_target_and_goes_back_to_the_mythics_when_disarmed():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    game.held["a"] = ["math"]  # na mão comum não vale
    with pytest.raises(EstimateError):
        game.arm("a", "math", "b", ["a", "b"], None)
    game.held["a"] = []
    game.mythics["a"] = ["math"]
    with pytest.raises(EstimateError):
        game.arm("a", "math", None, ["a", "b"], None)
    game.arm("a", "math", "b", ["a", "b"], None)
    game.disarm("a")
    assert game.mythics["a"] == ["math"] and game.held["a"] == []
    assert game.view(game.phase_started_at, "a").mythic_powerups == ["math"]


def test_gained_power_can_come_mythic_and_math_is_never_common_or_legendary():
    assert not set(MYTHICS) & set(POWERS) and not set(MYTHICS) & set(LEGENDARY)

    class Lucky(random.Random):
        def random(self) -> float:
            return 0.0

    a = P("a")
    game = powered()
    game.rng = Lucky(1)
    for _ in range(3):
        ask(game, [a], a=115)
    gained = result(game, "a").gained
    assert gained.mythic and not gained.legendary and gained.kind in MYTHICS and game.mythics["a"] == [gained.kind]


def test_mythics_take_up_space_in_the_hand():
    a = P("a")
    game = powered()
    game.powerup_max = 1
    game.mythics["a"] = ["math"]
    for _ in range(3):
        ask(game, [a], a=115)
    assert result(game, "a").gained is None


def math_round(game: Estimate, players: list[P]) -> float:
    """Abre uma pergunta com Matemática em b e devolve quando ela começou."""
    ask(game, players, **{p.id: 110 for p in players})
    give_math(game, ids=tuple(p.id for p in players))
    game.advance(game.phase_ends_at, players)
    return game.phase_started_at


def test_math_target_has_more_time_and_the_others_keep_theirs():
    a, b = P("a"), P("b")
    game = powered()
    at = math_round(game, [a, b])
    assert game.phase_ends_at == at + MATH_SECONDS
    assert game.view(at, "b").phase_ends_in_ms == round(MATH_SECONDS * 1000)
    assert game.view(at, "a").phase_ends_in_ms == round(ANSWER_SECONDS * 1000)
    with pytest.raises(EstimateError):
        game.guess("a", 100, at + ANSWER_SECONDS + 5)
    game.guess("b", 100, at + ANSWER_SECONDS + 5)


def test_who_guessed_or_ran_out_of_time_watches_the_target():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    at = math_round(game, [a, b, c])
    assert game.view(at, "a").math_watch == [] and game.view(at, "c").math_watch == []
    game.guess("a", 100, at + 1)
    watching = game.view(at + 1, "a").math_watch
    assert [w.player_id for w in watching] == ["b"]
    assert game.view(at + 1, "c").math_watch == [] and game.view(at + 1, "b").math_watch == []
    late = at + ANSWER_SECONDS + 2
    assert game.view(late, "c").time_up and [w.player_id for w in game.view(late, "c").math_watch] == ["b"]
    assert game.view(late, "c").phase_ends_in_ms == round((MATH_SECONDS - ANSWER_SECONDS - 2) * 1000)
    assert not game.view(late, "b").time_up
    game.guess("b", 100, late)
    assert game.view(late, "a").math_watch == []  # o alvo já chutou: não tem mais o que assistir


def test_math_steps_are_replayed_undone_and_seen_live():
    a, b = P("a"), P("b")
    game = powered()
    at = math_round(game, [a, b])
    keys = game.math_puzzles["b"].keys
    start = game.math_puzzles["b"].start
    plus = next(i for i, key in enumerate(keys) if key.op in ("add", "mul"))
    game.math_steps("b", [plus])
    moved = game.view(at + 1, "b").math
    assert moved.steps == [plus] and moved.value == apply_math(start, keys[plus])
    game.guess("a", 100, at + 1)
    assert game.view(at + 1, "a").math_watch[0].math.value == moved.value
    game.math_steps("b", [])  # Voltar
    assert game.view(at + 1, "b").math.value == start


def test_math_steps_reject_what_the_keypad_does_not_allow():
    a, b = P("a"), P("b")
    game = powered()
    math_round(game, [a, b])
    keys = game.math_puzzles["b"].keys
    with pytest.raises(EstimateError):
        game.math_steps("b", [99])
    with pytest.raises(EstimateError):
        game.math_steps("b", [0] * (keys[0].uses + 1))
    with pytest.raises(EstimateError):
        game.math_steps("a", [0])  # não é o alvo


def test_when_time_runs_out_the_visor_counts_as_the_guess():
    a, b = P("a"), P("b")
    game = powered()
    at = math_round(game, [a, b])
    game.math_puzzles["b"] = game.math_puzzles["b"].model_copy(update={"value": 100})
    game.guess("a", 170, at + 1)
    game.advance(at + MATH_SECONDS + 2, [a, b])
    assert result(game, "b").value == 100 and result(game, "b").exact
    assert result(game, "b").elapsed_ms == round(MATH_SECONDS * 1000)


def test_who_ran_out_of_time_does_not_hold_the_question():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    at = math_round(game, [a, b, c])
    game.guess("a", 100, at + 1)
    assert not game.everyone_answered(["a", "b", "c"], at + 2)
    game.guess("b", 100, at + ANSWER_SECONDS + 5)
    assert not game.everyone_answered(["a", "b", "c"], at + 2)  # c ainda tinha tempo
    assert game.everyone_answered(["a", "b", "c"], at + ANSWER_SECONDS + 5)  # c ficou sem tempo


def test_without_math_nobody_gets_extra_time():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    game.advance(game.phase_ends_at, [a, b])
    assert game.others_time_up_at() is None and game.phase_ends_at == game.phase_started_at + ANSWER_SECONDS


# --- mítico: Palavra final -----------------------------------------------------------


def last_word_round(game: Estimate, players: list[P]) -> float:
    """Abre uma pergunta e a usa para a; devolve quando ela começou."""
    ask(game, players, **{p.id: 110 for p in players})
    game.advance(game.phase_ends_at, players)
    game.mythics["a"] = ["last_word"]
    game.use_now("a", "last_word")
    return game.phase_started_at


def test_last_word_waits_for_the_others_and_then_shows_the_guesses_and_sides():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    at = last_word_round(game, [a, b, c])
    assert game.mythics["a"] == [] and game.view(at, "b").last_word.player_id == "a"
    with pytest.raises(EstimateError):
        game.guess("a", 100, at + 1)
    game.guess("b", 70, at + 1)
    assert game.view(at + 1, "a").last_word.guesses == []  # só depois de todos
    assert not game.everyone_answered(["a", "b", "c"], at + 1)
    assert not game.open_last_word(at + 1, ["b", "c"])  # sem ele na sala, não abre
    game.guess("c", 130, at + 2)
    assert game.everyone_answered(["a", "b", "c"], at + 2)
    assert game.open_last_word(at + 2, ["a", "b", "c"])
    assert not game.everyone_answered(["a", "b", "c"], at + 3)
    view = game.view(at + 2, "a")
    assert view.last_word.open and view.phase_ends_in_ms == round(LAST_WORD_SECONDS * 1000)
    assert view.phase_duration_ms == round(LAST_WORD_SECONDS * 1000)
    assert [(g.player_id, g.value, g.side) for g in view.last_word.guesses] == [
        ("b", 70, "higher"),
        ("c", 130, "lower"),
    ]
    game.guess("a", 100, at + 3)
    assert game.everyone_answered(["a", "b", "c"], at + 3)


def test_last_word_opens_when_the_others_run_out_of_time():
    a, b = P("a"), P("b")
    game = powered()
    at = last_word_round(game, [a, b])
    assert game.others_time_up_at() == pytest.approx(at + ANSWER_SECONDS + 1)
    assert game.everyone_answered(["a", "b"], at + ANSWER_SECONDS + 2)
    assert game.open_last_word(at + ANSWER_SECONDS + 2, ["a", "b"])
    assert game.others_time_up_at() is None
    with pytest.raises(EstimateError):
        game.guess("b", 100, at + ANSWER_SECONDS + 3)


def finish_last_word(game: Estimate, players: list[P], at: float, speaker: float | None, **others: float) -> None:
    for pid, value in others.items():
        game.guess(pid, value, at + 1)
    assert game.open_last_word(at + 2, [p.id for p in players])
    if speaker is not None:
        game.guess("a", speaker, at + 3)
    game.advance(at + 3, players)


def test_last_word_closest_takes_iq_from_each_of_the_others():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    at = last_word_round(game, [a, b, c])
    finish_last_word(game, [a, b, c], at, 100, b=90, c=120)
    assert result(game, "a").last_word == 20
    assert result(game, "b").last_word == -10 and result(game, "c").last_word == -10
    assert result(game, "a").total == result(game, "a").delta + 20


def test_last_word_not_closest_pays_each_of_the_others():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    at = last_word_round(game, [a, b, c])
    before = a.score
    finish_last_word(game, [a, b, c], at, 150, b=100, c=170)
    assert result(game, "a").last_word == -20 and result(game, "b").last_word == 10
    assert a.score == before + result(game, "a").delta - 20


def test_last_word_a_tie_goes_to_the_speaker_and_silence_loses():
    a, b = P("a"), P("b")
    game = powered()
    at = last_word_round(game, [a, b])
    finish_last_word(game, [a, b], at, 110, b=110)
    assert result(game, "a").last_word == 10
    at = last_word_round(game, [a, b])
    finish_last_word(game, [a, b], at, None, b=170)
    assert result(game, "a").value is None and result(game, "a").last_word == -10


def test_last_word_stake_shrinks_in_big_rooms():
    players = [P(pid) for pid in "abcdefghi"]
    game = powered()
    at = last_word_round(game, players)
    finish_last_word(game, players, at, 100, **{p.id: 150 for p in players[1:]})
    assert result(game, "a").last_word == 40 and result(game, "b").last_word == -5


def test_last_word_is_one_per_question_and_not_for_math_targets():
    a, b = P("a"), P("b")
    game = powered()
    last_word_round(game, [a, b])
    game.mythics["b"] = ["last_word"]
    with pytest.raises(EstimateError):
        game.use_now("b", "last_word")
    game = powered()
    at = math_round(game, [a, b])
    game.mythics["b"] = ["last_word"]
    with pytest.raises(EstimateError):
        game.use_now("b", "last_word")
    assert at is not None


def test_last_word_is_not_armed_and_typing_is_only_for_the_speaker_after_it_opens():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    game.mythics["a"] = ["last_word"]
    with pytest.raises(EstimateError):
        game.arm("a", "last_word", None, ["a", "b"], None)
    game.advance(game.phase_ends_at, [a, b])
    game.use_now("a", "last_word")
    at = game.phase_started_at
    with pytest.raises(EstimateError):
        game.last_word_typing("a", "1")
    game.guess("b", 100, at + 1)
    game.open_last_word(at + 1, ["a", "b"])
    with pytest.raises(EstimateError):
        game.last_word_typing("b", "1")
    game.last_word_typing("a", "12")
    assert game.view(at + 1, "b").last_word.draft == "12"
    game.guess("a", 12, at + 2)
    game.advance(at + 2, [a, b])
    game.advance(game.phase_ends_at, [a, b])
    assert game.last_word_by is None and game.last_word_draft == ""


# --- Cópia ---------------------------------------------------------------------------


def test_copy_takes_the_best_guess_when_it_beats_your_own():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=110, b=110, c=110)
    give(game, "a", "copy", ids=("a", "b", "c"))
    ask(game, [a, b, c], a=170, b=105, c=130)
    copied = result(game, "a")
    assert copied.value == 105 and copied.copied_from == "b" and copied.copied_own == 170
    assert copied.delta == result(game, "b").delta > 0


def test_copy_keeps_your_guess_when_nobody_is_better():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "a", "copy")
    ask(game, [a, b], a=105, b=170)
    assert result(game, "a").value == 105 and result(game, "a").copied_from is None
    give(game, "a", "copy")
    ask(game, [a, b], a=105, b=105)  # empate: fica com o seu
    assert result(game, "a").copied_from is None


def test_copy_needs_your_own_guess():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "a", "copy")
    ask(game, [a, b], b=100)
    assert result(game, "a").value is None and result(game, "a").copied_from is None


def test_copied_guess_counts_for_iq_but_not_for_the_streak_or_the_exact_power():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "a", "copy")
    ask(game, [a, b], a=170, b=100)
    copied = result(game, "a")
    assert copied.exact and copied.delta > 0 and copied.gained is None
    assert game.right_runs["a"] == 0
    assert result(game, "b").gained is not None and result(game, "b").gained.reason == "exact"


def test_two_copiers_copy_who_guessed_on_their_own():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=110, b=110, c=110)
    give(game, "a", "copy", ids=("a", "b", "c"))
    give(game, "b", "copy", ids=("a", "b", "c"))
    ask(game, [a, b, c], a=150, b=101, c=120)
    assert result(game, "a").value == 120 and result(game, "a").copied_from == "c"
    assert result(game, "b").value == 101 and result(game, "b").copied_from is None


def test_nudge_moves_the_copied_guess_and_the_nudged_rival_is_the_one_copied():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "a", "copy")
    game.armed["b"] = PowerUpUse(kind="nudge", by="b", target="a", reflected_by=None)
    ask(game, [a, b], a=170, b=100)
    moved = result(game, "a")
    assert moved.copied_from == "b" and moved.nudged_from == 100 and moved.value != 100


def test_who_copied_is_out_of_the_last_word_comparison():
    a, b, c = P("a"), P("b"), P("c")
    game = powered()
    ask(game, [a, b, c], a=110, b=110, c=110)
    give(game, "b", "copy", ids=("a", "b", "c"))
    game.advance(game.phase_ends_at, [a, b, c])
    at = game.phase_started_at
    game.mythics["a"] = ["last_word"]
    game.use_now("a", "last_word")
    game.guess("b", 170, at + 1)
    game.guess("c", 110, at + 1)
    assert game.open_last_word(at + 2, ["a", "b", "c"])
    game.guess("a", 110, at + 3)  # empata com c, e b copiou um chute igual
    game.advance(at + 3, [a, b, c])
    assert result(game, "b").copied_from in ("a", "c")
    assert result(game, "a").last_word == 20


def test_speaker_who_copied_loses_the_last_word():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=110, b=110)
    give(game, "a", "copy")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    game.mythics["a"] = ["last_word"]
    game.use_now("a", "last_word")
    game.guess("b", 100, at + 1)
    assert game.open_last_word(at + 2, ["a", "b"])
    game.guess("a", 170, at + 3)
    game.advance(at + 3, [a, b])
    assert result(game, "a").value == 100 and result(game, "a").last_word < 0
