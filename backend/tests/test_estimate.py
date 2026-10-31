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
    points = lambda guess: guess_points(error_percent(q, guess), "medium")  # noqa: E731
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
    game = Estimate.create([question("q", 10, difficulty="hard")], 1, set(), random.Random(1), now=0)  # 1 pergunta: a difícil
    game.advance(6, [])
    with pytest.raises(EstimateError, match="tempo acabou"):
        game.guess("ana", 10, now=6 + ANSWER_SECONDS + 2)
