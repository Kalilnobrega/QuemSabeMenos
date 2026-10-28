import random

import pytest

from app.game import Question
from app.hot_potato import (
    DOUBLE_BOMB_RIGHTS,
    FUSE_SECONDS,
    GOLDEN_FUSE_SECONDS,
    MAX_WRONG_STREAK,
    PASS_SECONDS,
    SHORT_FUSE_SECONDS,
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


def new_game(players: int = 3, powers: bool = False) -> HotPotato:
    game = HotPotato.create([f"p{i}" for i in range(players)], questions(), set(), random.Random(1), now=0, powers=powers)
    game.advance(START_SECONDS)
    return game


def powered(players: int = 3) -> HotPotato:
    return new_game(players, powers=True)


def right(potato) -> int:
    return potato.question.answer


def wrong(potato) -> int:
    return (potato.question.answer + 1) % 4


def give(game: HotPotato, player_id: str, *kinds) -> None:
    game.held[player_id] = list(kinds)


def watcher(game: HotPotato) -> str:
    holders = {p.holder for p in game.potatoes}
    return next(pid for pid in game.alive_ids() if pid not in holders)


def test_starts_with_a_hidden_fuse_and_only_easy_or_medium_questions():
    game = new_game()
    potato = game.main
    assert game.phase == "playing" and potato.state == "asking"
    assert FUSE_SECONDS[0] <= potato.fuse_total <= FUSE_SECONDS[1]
    assert potato.question.difficulty in ("easy", "medium")
    assert potato.question.options[potato.question.answer].startswith("Certa")


def test_right_answer_passes_to_the_next_in_the_circle():
    game = new_game()
    potato = game.main
    first = potato.holder
    game.answer(first, right(potato), 7)
    assert potato.state == "passing"
    game.advance(7 + PASS_SECONDS)
    ids = [p.id for p in game.players]
    assert potato.holder == ids[(ids.index(first) + 1) % 3]


def test_the_fuse_only_burns_while_answering():
    game = new_game()
    potato = game.main
    total, t0 = potato.fuse_total, potato.state_started_at
    game.answer(potato.holder, right(potato), t0 + 5)
    assert potato.fuse_left == pytest.approx(total - 5)
    assert game.fuse_at(potato, t0 + 100) == pytest.approx(total - 5)  # o passe não queima


def test_wrong_answer_costs_ten_seconds_and_keeps_the_potato():
    game = new_game()
    potato = game.main
    holder, total, t0 = potato.holder, potato.fuse_total, potato.state_started_at
    game.answer(holder, wrong(potato), t0 + 2)
    assert potato.state == "wrong"
    assert potato.fuse_left == pytest.approx(total - 2 - WRONG_PENALTY_SECONDS)
    game.advance(t0 + 2 + WRONG_SECONDS)
    assert potato.holder == holder and potato.state == "asking"


def test_three_wrong_in_a_row_explodes():
    game = new_game()
    potato = game.main
    holder = potato.holder
    for _ in range(MAX_WRONG_STREAK - 1):
        game.answer(holder, wrong(potato), 0)
        game.advance(0)
    game.answer(holder, wrong(potato), 0)
    assert game.phase == "exploded" and game.exploded == holder
    assert not game.player(holder).alive


def test_the_fuse_running_out_eliminates_the_holder_and_the_next_round_starts_after_them():
    game = new_game(players=3)
    holder = game.main.holder
    game.advance(game.deadline())
    assert game.exploded == holder and game.phase == "exploded"
    game.advance(game.phase_ends_at)
    ids = [p.id for p in game.players]
    potato = game.main
    assert game.round == 2 and game.phase == "playing"
    assert potato.holder == ids[(ids.index(holder) + 1) % 3]
    assert potato.fuse_left == potato.fuse_total


def test_last_one_standing_wins():
    game = new_game(players=2)
    loser = game.main.holder
    game.advance(game.deadline())
    game.advance(game.phase_ends_at)
    assert game.phase == "finished"
    assert game.winner != loser
    assert game.places()[game.winner] == 1 and game.places()[loser] == 2


def test_only_the_holder_answers():
    game = new_game()
    with pytest.raises(HotPotatoError):
        game.answer(watcher(game), 0, 0)


def test_holder_leaving_hands_the_potato_on():
    game = new_game(players=3)
    holder = game.main.holder
    game.drop(holder, 1)
    assert game.main.holder != holder and game.main.state == "asking"
    other = next(pid for pid in game.alive_ids() if pid != game.main.holder)
    game.drop(other, 2)
    assert game.phase == "finished" and game.winner == game.alive_ids()[0]


def test_view_hides_the_fuse_but_shows_the_heat():
    game = new_game()
    potato = game.main
    view = game.view(potato.state_started_at + potato.fuse_total / 2, [p.id for p in game.players])
    assert view.potatoes[0].heat == pytest.approx(0.5, abs=0.01)
    assert view.potatoes[0].burning and view.potatoes[0].options and view.potatoes[0].fuse_ms is None


# --- com poderes ----------------------------------------------------------

def test_everyone_starts_with_one_power():
    game = powered()
    assert all(len(game.held[p.id]) == 1 for p in game.players)
    assert game.view(0, [p.id for p in game.players], "p0").starting_powerup == game.held["p0"][0]


def test_without_powers_nothing_is_dealt_and_using_fails():
    game = new_game()
    assert not game.held
    with pytest.raises(HotPotatoError):
        game.use(game.main.holder, "shield", 0)


def test_helps_only_with_the_potato_and_sabotages_only_on_whoever_has_it():
    game = powered()
    potato, other = game.main, watcher(game)
    give(game, other, "shield")
    with pytest.raises(HotPotatoError):
        game.use(other, "shield", 0)
    give(game, potato.holder, "accelerator")
    with pytest.raises(HotPotatoError):
        game.use(potato.holder, "accelerator", 0)
    give(game, other, "accelerator")
    game.use(other, "accelerator", potato.state_started_at)
    assert potato.uses[0].target == potato.holder


def test_shield_holds_the_next_wrong():
    game = powered()
    potato = game.main
    holder, t0 = potato.holder, potato.state_started_at
    give(game, holder, "shield")
    game.use(holder, "shield", t0)
    fuse = potato.fuse_left
    game.answer(holder, wrong(potato), t0)
    assert potato.state == "wrong" and potato.turn.shielded
    assert potato.wrong_streak == 0 and potato.fuse_left == pytest.approx(fuse)


def test_second_chance_lets_you_try_again_without_penalty():
    game = powered()
    potato = game.main
    holder, t0 = potato.holder, potato.state_started_at
    give(game, holder, "second_chance")
    game.use(holder, "second_chance", t0)
    first = wrong(potato)
    game.answer(holder, first, t0 + 1)
    assert potato.state == "asking" and potato.first_wrong == first and potato.wrong_streak == 0
    with pytest.raises(HotPotatoError):
        game.answer(holder, first, t0 + 2)


def test_cold_water_adds_ten_seconds_and_accelerator_burns_twice_as_fast():
    game = powered()
    potato = game.main
    t0, total = potato.state_started_at, potato.fuse_total
    give(game, potato.holder, "cold_water")
    game.use(potato.holder, "cold_water", t0 + 5)
    assert game.fuse_at(potato, t0 + 5) == pytest.approx(total + 5)
    other = watcher(game)
    give(game, other, "accelerator")
    game.use(other, "accelerator", t0 + 5)
    assert game.fuse_at(potato, t0 + 7) == pytest.approx(total + 5 - 4)


def test_reverse_flips_the_circle_and_free_pass_skips_the_question():
    game = powered(players=4)
    potato = game.main
    holder, t0 = potato.holder, potato.state_started_at
    ids = [p.id for p in game.players]
    give(game, holder, "reverse", "free_pass")
    game.use(holder, "reverse", t0)
    game.use(holder, "free_pass", t0 + 1)
    assert potato.state == "passing" and potato.turn.free_pass
    game.advance(t0 + 1 + PASS_SECONDS)
    assert potato.holder == ids[(ids.index(holder) - 1) % 4]


def test_flashbang_blinds_only_the_holder():
    game = powered()
    potato, other = game.main, watcher(game)
    give(game, other, "flashbang")
    game.use(other, "flashbang", potato.state_started_at)
    ids = [p.id for p in game.players]
    assert game.view(0, ids, potato.holder).potatoes[0].flashbang
    assert not game.view(0, ids, other).potatoes[0].flashbang


def test_one_sabotage_per_watcher_per_question():
    game = powered()
    potato, other = game.main, watcher(game)
    give(game, other, "mirror", "scramble")
    game.use(other, "mirror", potato.state_started_at)
    with pytest.raises(HotPotatoError):
        game.use(other, "scramble", potato.state_started_at)


def test_three_right_in_a_row_earns_a_power():
    game = powered(players=2)
    potato = game.main
    holder = potato.holder
    game.held[holder] = []
    for _ in range(3):
        while potato.holder != holder:
            game.answer(potato.holder, right(potato), potato.state_started_at)
            game.advance(potato.state_ends_at)
        game.answer(holder, right(potato), potato.state_started_at)
        game.advance(potato.state_ends_at)
    assert len(game.held[holder]) + len(game.mythics.get(holder, [])) == 1


def test_ghosts_get_a_sabotage_when_someone_explodes_and_can_resurrect():
    game = powered(players=4)
    first = game.main.holder
    game.advance(game.deadline())  # o primeiro explode: ainda não tem fantasma antes dele
    game.held[first] = []
    game.advance(game.phase_ends_at)
    game.advance(game.deadline())  # o segundo explode: o primeiro ganha uma sabotagem
    assert len(game.held[first]) == 1 or game.mythics.get(first)
    game.mythics[first] = ["resurrection"]
    game.use(first, "resurrection", game.phase_started_at)
    assert game.player(first).alive and first in game.revived


def test_each_explosion_but_the_last_gives_the_living_a_power():
    game = powered(players=3)
    for p in game.players:
        game.held[p.id] = []
    game.advance(game.deadline())  # explode com 2 vivos sobrando
    alive = game.alive_ids()
    assert all(len(game.held[pid]) == 1 for pid in alive)
    game.advance(game.phase_ends_at)
    game.advance(game.deadline())  # a última explosão acaba a partida: sem poder
    assert not any(g.gain.reason == "elimination" for g in game.gifts)


# --- poderes só da Batata quente -----------------------------------------

def test_short_fuse_burns_ten_seconds_on_the_spot():
    game = powered()
    potato, other = game.main, watcher(game)
    t0 = potato.state_started_at
    give(game, other, "short_fuse")
    game.use(other, "short_fuse", t0 + 1)
    assert potato.fuse_left == pytest.approx(potato.fuse_total - 1 - SHORT_FUSE_SECONDS)


def test_short_fuse_can_blow_it_up():
    game = powered()
    potato, other = game.main, watcher(game)
    holder = potato.holder
    give(game, other, "short_fuse")
    game.use(other, "short_fuse", potato.state_started_at + potato.fuse_total - 5)
    assert game.phase == "exploded" and game.exploded == holder


def test_double_bomb_needs_two_rights_in_a_row_to_pass():
    game = powered()
    potato, other = game.main, watcher(game)
    holder = potato.holder
    give(game, other, "double_bomb")
    game.use(other, "double_bomb", potato.state_started_at)
    game.answer(holder, right(potato), potato.state_started_at)
    assert potato.state == "again" and potato.need_right == 1
    game.advance(potato.state_ends_at)
    game.answer(holder, wrong(potato), potato.state_started_at)
    assert potato.need_right == DOUBLE_BOMB_RIGHTS  # errou: volta a pedir 2
    game.advance(potato.state_ends_at)
    for _ in range(DOUBLE_BOMB_RIGHTS):
        game.answer(holder, right(potato), potato.state_started_at)
        game.advance(potato.state_ends_at)
    assert potato.holder != holder and potato.need_right == 1 and not potato.bomb


def test_thermometer_shows_the_fuse_only_to_the_holder_until_it_passes():
    game = powered()
    potato = game.main
    holder, t0 = potato.holder, potato.state_started_at
    give(game, holder, "thermometer")
    game.use(holder, "thermometer", t0)
    ids = [p.id for p in game.players]
    assert game.view(t0 + 2, ids, holder).potatoes[0].fuse_ms == round((potato.fuse_total - 2) * 1000)
    assert game.view(t0 + 2, ids, watcher(game)).potatoes[0].fuse_ms is None
    game.answer(holder, right(potato), t0 + 3)
    game.advance(potato.state_ends_at)
    assert not potato.thermometer


def test_scare_is_only_for_ghosts_and_does_nothing_to_the_fuse():
    game = powered(players=4)
    ghost = game.main.holder
    game.advance(game.deadline())
    game.advance(game.phase_ends_at)
    potato = game.main
    fuse = potato.fuse_left
    give(game, ghost, "scare")
    game.use(ghost, "scare", potato.state_started_at)
    assert potato.uses[-1].kind == "scare" and potato.fuse_left == fuse and game.phase == "playing"


def test_double_potato_adds_a_golden_potato_far_away_that_skips_whoever_threw_it():
    game = powered(players=5)
    potato = game.main
    ids = game.alive_ids()
    thrower = next(pid for pid in ids if pid != potato.holder)
    game.mythics[thrower] = ["double_potato"]
    game.use(thrower, "double_potato", potato.state_started_at)
    golden = game.golden
    assert golden and golden.holder != thrower and golden.excluded == thrower
    assert GOLDEN_FUSE_SECONDS[0] <= golden.fuse_total <= GOLDEN_FUSE_SECONDS[1]
    here, there = ids.index(potato.holder), ids.index(golden.holder)
    assert min(abs(here - there), 5 - abs(here - there)) == 2  # o mais longe na roda de 5
    for _ in range(6):  # roda a dourada: nunca chega em quem jogou
        game.answer(golden.holder, right(golden), golden.state_started_at, golden.id)
        game.advance(golden.state_ends_at)
        assert golden.holder != thrower
    game.mythics[thrower] = ["double_potato"]
    with pytest.raises(HotPotatoError, match="Já tem"):
        game.use(thrower, "double_potato", 0)


def test_holding_both_potatoes_answers_one_question_for_each():
    game = powered(players=3)
    potato = game.main
    thrower = next(pid for pid in game.alive_ids() if pid != potato.holder)
    game.mythics[thrower] = ["double_potato"]
    game.use(thrower, "double_potato", 0)
    golden = game.golden
    golden.holder = potato.holder  # as duas com a mesma pessoa
    holder = potato.holder
    with pytest.raises(HotPotatoError, match="as duas"):
        game.answer(holder, right(potato), 0)
    game.answer(holder, right(potato), 0, potato.id)
    assert potato.state == "passing" and golden.state == "asking"
    game.answer(holder, right(golden), 0, golden.id)
    assert golden.state == "passing"


def test_golden_potato_explodes_on_its_own_and_disappears():
    game = powered(players=4)
    potato = game.main
    thrower = next(pid for pid in game.alive_ids() if pid != potato.holder)
    game.mythics[thrower] = ["double_potato"]
    t0 = potato.state_started_at
    game.use(thrower, "double_potato", t0)
    golden = game.golden
    golden.fuse_left = 1  # a dourada vai explodir antes
    victim = golden.holder
    game.advance(game.deadline())
    assert game.phase == "exploded" and game.exploded == victim
    assert game.view(t0 + 1, game.alive_ids()).exploded_golden
    main_fuse = potato.fuse_left
    game.advance(game.phase_ends_at)
    assert game.golden is None and game.main is potato and potato.fuse_left == pytest.approx(main_fuse)


def test_double_potato_needs_three_alive():
    game = powered(players=2)
    holder = game.main.holder
    other = next(pid for pid in game.alive_ids() if pid != holder)
    game.mythics[other] = ["double_potato"]
    with pytest.raises(HotPotatoError, match="pelo menos 3"):
        game.use(other, "double_potato", 0)
