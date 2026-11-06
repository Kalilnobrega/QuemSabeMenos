import random
from dataclasses import dataclass

import pytest

from app.estimate import (
    ANSWER_SECONDS,
    Estimate,
    EstimateError,
    EstimateQuestion,
    error_percent,
    guess_points,
    load_estimates,
)


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


def test_everyone_starts_with_one_power_but_never_investment():
    for seed in range(40):
        game = Estimate.create(
            [question(f"q{i}", 100) for i in range(10)], 10, set(), random.Random(seed), 0, ["a", "b"], powers=True
        )
        assert all(len(game.held[pid]) == 1 and game.held[pid][0] != "investment" for pid in ("a", "b"))
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


def test_investment_pays_while_guesses_earn_and_ends_on_a_loss():
    a = P("a")
    game = powered()
    ask(game, [a], a=100)
    give(game, "a", "investment", ids=("a",))
    ask(game, [a], a=115)
    assert result(game, "a").investment == 2
    ask(game, [a], a=115)
    assert result(game, "a").investment == 4
    ask(game, [a], a=170)
    assert result(game, "a").investment == 0 and "a" not in game.investments


def test_investment_needs_medium_or_harder_next():
    game = powered(difficulty="easy")
    ask(game, [P("a")], a=100)
    game.held["a"] = ["investment"]
    with pytest.raises(EstimateError):
        game.arm("a", "investment", None, ["a"], None)


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


def test_accelerator_cuts_only_the_target_window():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "accelerator", "b")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert game.view(at, "b").phase_ends_in_ms == round(ANSWER_SECONDS / 3 * 1000)
    assert game.view(at, "a").phase_ends_in_ms == round(ANSWER_SECONDS * 1000)
    with pytest.raises(EstimateError):
        game.guess("b", 100, at + 8)
    game.guess("a", 100, at + 8)


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
    ask(game, [a], a=100)
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


def test_peek_shows_other_guesses_live_and_is_spent_during_the_question():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    game.guess("b", 150, at + 1)
    assert game.view(at + 1, "a").peek is None
    game.held["a"] = ["peek"]
    game.use_now("a", "peek")
    assert game.held["a"] == []
    peek = game.view(at + 1, "a").peek
    assert [(p.player_id, p.value) for p in peek] == [("b", 150)]
    assert game.view(at + 1, "b").peek is None


def test_peek_is_not_armed_in_the_reveal():
    game = powered()
    ask(game, [P("a")], a=100)
    game.held["a"] = ["peek"]
    with pytest.raises(EstimateError):
        game.arm("a", "peek", None, ["a"], None)


def test_flashbang_only_reaches_the_target_while_guessing():
    a, b = P("a"), P("b")
    game = powered()
    ask(game, [a, b], a=100, b=100)
    give(game, "a", "flashbang", "b")
    game.advance(game.phase_ends_at, [a, b])
    at = game.phase_started_at
    assert game.view(at, "b").flashbang and not game.view(at, "a").flashbang
    game.advance(at + 1, [a, b])
    assert not game.view(game.phase_started_at, "b").flashbang


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
