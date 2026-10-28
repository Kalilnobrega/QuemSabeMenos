import asyncio
import dataclasses
import json

import httpx
import pytest
import socketio

from app import game, main, rooms
from app.history import MatchHistory
from app.powerups import INSTANT, TARGETED
from app.rooms import RoomManager


@pytest.fixture(autouse=True)
def fresh_rooms(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "rooms", RoomManager())
    monkeypatch.setattr(main, "history", MatchHistory(tmp_path / "matches.db"))
    monkeypatch.setattr(main, "RECONNECT_GRACE_SECONDS", 0.2)
    # A leitura precisa de folga: o teste vê "reading" e tenta responder antes de liberar.
    monkeypatch.setattr(game, "MIN_READING_SECONDS", 0.25)
    monkeypatch.setattr(game, "TYPING_SECONDS_PER_CHAR", 0)
    monkeypatch.setattr(game, "START_SECONDS", 0.05)
    monkeypatch.setattr(game, "LEVEL_SECONDS", 0.05)
    monkeypatch.setattr(game, "INTRO_SECONDS", 0.05)
    monkeypatch.setattr(game, "BET_SECONDS", 1.0)
    monkeypatch.setattr(game, "LATE_SECONDS", 0.05)
    monkeypatch.setattr(game, "MIN_RESULTS_SECONDS", 0.05)
    monkeypatch.setattr(game, "MAX_RESULTS_SECONDS", 0.05)
    monkeypatch.setattr(rooms, "ANSWER_SECONDS", 1.0)


class Client:
    """Cliente Socket.IO que guarda o último room_state recebido."""

    def __init__(self) -> None:
        self.sio = socketio.AsyncClient()
        self.state: dict | None = None
        self.sio.on("room_state", self._on_state)

    async def _on_state(self, data: dict) -> None:
        self.state = data

    async def connect(self, url: str) -> "Client":
        await self.sio.connect(url, transports=["websocket"])
        return self

    async def call(self, event: str, data: dict | None = None) -> dict:
        return await self.sio.call(event, data) if data is not None else await self.sio.call(event)

    async def wait_for(self, predicate, timeout: float = 2) -> dict:
        async def poll():
            while not (self.state and predicate(self.state)):
                await asyncio.sleep(0.01)
            return self.state

        return await asyncio.wait_for(poll(), timeout)


@pytest.fixture
async def connect(server_url):
    clients: list[Client] = []

    async def factory() -> Client:
        client = await Client().connect(server_url)
        clients.append(client)
        return client

    yield factory
    for client in clients:
        if client.sio.connected:
            await client.sio.disconnect()


def nicknames(state: dict) -> list[str]:
    return [p["nickname"] for p in state["players"]]


async def test_create_and_join_broadcasts_lobby(connect):
    ana, bia = await connect(), await connect()

    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    assert created["ok"]
    code = created["room"]["code"]

    joined = await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})
    assert joined["ok"]

    state = await ana.wait_for(lambda s: len(s["players"]) == 2)
    assert nicknames(state) == ["Ana", "Bia"]
    assert state["host_id"] == created["player_id"]


async def test_invalid_payloads_return_errors(connect):
    ana = await connect()
    bad_avatar = await ana.call("create_room", {"nickname": "Ana", "avatar": "dragao"})
    assert bad_avatar == {"ok": False, "error": "Apelido ou avatar inválido."}
    unknown = await ana.call("join_room", {"code": "ZZZZZ", "nickname": "Ana", "avatar": "gato"})
    assert not unknown["ok"]


async def test_host_leaving_passes_host(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    joined = await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    assert (await ana.call("leave_room"))["ok"]
    state = await bia.wait_for(lambda s: nicknames(s) == ["Bia"])
    assert state["host_id"] == joined["player_id"]


async def test_disconnected_player_can_rejoin(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})

    await ana.sio.disconnect()
    await bia.wait_for(lambda s: not s["players"][0]["connected"])

    ana_again = await connect()
    rejoined = await ana_again.call("rejoin_room", {"code": code, "token": created["token"]})
    assert rejoined["ok"]
    assert rejoined["player_id"] == created["player_id"]
    await bia.wait_for(lambda s: s["players"][0]["connected"])


async def test_player_who_does_not_return_is_removed(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    joined = await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    await ana.sio.disconnect()
    state = await bia.wait_for(lambda s: nicknames(s) == ["Bia"])
    assert state["host_id"] == joined["player_id"]


async def test_host_starts_game(connect):
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})

    assert not (await bia.call("start_game"))["ok"]
    assert (await ana.call("start_game"))["ok"]
    await bia.wait_for(lambda s: s["status"] == "playing")


async def setup_room(connect) -> tuple[Client, Client, dict, dict]:
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    joined = await bia.call("join_room", {"code": created["room"]["code"], "nickname": "Bia", "avatar": "sapo"})
    return ana, bia, created, joined


async def test_only_host_changes_rounds(connect):
    ana, bia, *_ = await setup_room(connect)
    assert not (await bia.call("update_settings", {"rounds": 10}))["ok"]
    assert not (await ana.call("update_settings", {"rounds": 7}))["ok"]
    assert (await ana.call("update_settings", {"rounds": 10}))["ok"]
    await bia.wait_for(lambda s: s["settings"]["rounds"] == 10)


async def test_full_game(connect):
    ana, bia, created, joined = await setup_room(connect)
    await ana.call("update_settings", {"rounds": 10})
    assert (await ana.call("start_game"))["ok"]

    for round_number in range(1, 12):  # 10 rodadas + a final impossível
        state = await ana.wait_for(
            lambda s: s["game"]
            and s["game"]["round"] == round_number
            and s["game"]["phase"] not in ("starting", "level", "intro")
        )
        if state["game"]["phase"] == "betting":
            assert state["game"]["question"] is None and state["game"]["theme"]
            assert round_number == state["game"]["bet_round"] == 9  # 10 rodadas: 3/3/4, a 3ª difícil
            bia_score = next(p["score"] for p in state["players"] if p["id"] == joined["player_id"])
            assert not (await ana.call("submit_bet", {"amount": 10_000}))["ok"]
            assert (await ana.call("submit_bet", {"amount": 0}))["ok"]
            if bia_score > 0:  # sem QI a Bia não aposta, e a aposta da Ana já fecha a fase
                assert (await bia.call("submit_bet", {"amount": bia_score // 2}))["ok"]
            # Todos apostaram: a pergunta aparece antes do tempo (1 s).
            state = await ana.wait_for(
                lambda s: s["game"]["phase"] in ("reading", "answering"), timeout=0.8
            )
        assert state["game"]["question"]["text"]
        assert state["game"]["correct_option"] is None

        # Antes da pergunta terminar de aparecer, responder não vale.
        if state["game"]["phase"] == "reading":
            assert not (await ana.call("submit_answer", {"option": 0}))["ok"]

        await ana.wait_for(lambda s: s["game"]["round"] == round_number and s["game"]["phase"] == "answering")
        assert (await ana.call("submit_answer", {"option": 0}))["ok"]
        assert (await bia.call("submit_answer", {"option": 1}))["ok"]

        # Todos responderam: a rodada fecha antes do tempo (1 s).
        results = await ana.wait_for(
            lambda s: s["game"]["round"] == round_number and s["game"]["phase"] in ("results", "finished"), timeout=0.8
        )
        assert results["game"]["correct_option"] is not None
        assert results["game"]["fact"]
        assert {r["player_id"] for r in results["game"]["results"]} == {created["player_id"], joined["player_id"]}
        assert all((r["bet"] is not None) == (round_number == 9) for r in results["game"]["results"])

    final = await bia.wait_for(lambda s: s["game"]["phase"] == "finished")
    await asyncio.sleep(0.05)  # o histórico fecha a partida logo depois de transmitir o fim

    db = main.history.db
    (status, mode, players), = db.execute("SELECT status, mode, players FROM matches").fetchall()
    assert (status, mode) == ("finished", "classic")
    assert [p["nickname"] for p in json.loads(players)] == [p["nickname"] for p in sorted(final["players"], key=lambda p: (-p["score"], p["answer_ms"]))]
    assert db.execute("SELECT count(*), sum(bet_round), sum(skipped) FROM rounds").fetchone() == (11, 1, 0)
    rows = db.execute("SELECT nickname, option, correct, elapsed_ms FROM answers WHERE round = 1 ORDER BY nickname").fetchall()
    assert [(n, o) for n, o, _, _ in rows] == [("Ana", 0), ("Bia", 1)] and all(ms is not None for *_, ms in rows)
    assert all(p["answer_ms"] > 0 for p in final["players"])

    assert not (await bia.call("play_again"))["ok"]
    assert (await ana.call("play_again"))["ok"]
    lobby = await bia.wait_for(lambda s: s["status"] == "lobby")
    assert lobby["game"] is None
    assert all(p["score"] == 50 and p["answer_ms"] == 0 and p["streak"] == 0 for p in lobby["players"])


async def test_round_ends_when_time_runs_out(connect):
    ana, bia, created, _ = await setup_room(connect)
    await ana.call("update_settings", {"rounds": 10})
    await ana.call("start_game")
    await ana.wait_for(lambda s: s["game"] and s["game"]["phase"] == "answering")
    await ana.call("submit_answer", {"option": 0})

    results = await bia.wait_for(lambda s: s["game"]["phase"] == "results", timeout=2)
    bia_result = next(r for r in results["game"]["results"] if r["player_id"] != created["player_id"])
    assert bia_result == {"player_id": bia_result["player_id"], "option": None, "correct": False, "elapsed_ms": None, "delta": -20, "bonuses": [], "bet": None, "bet_delta": 0, "shielded": 0, "stolen": 0, "robbed": 0, "tolled": 0, "toll_received": 0, "decoy": None, "tricked": 0, "doubled": False, "first_option": None, "expired": [], "gained": None}  # partida de 10: vale o dobro


async def test_powerups_are_private_and_everyone_skipping_ends_the_reveal(connect, monkeypatch):
    monkeypatch.setattr(game, "MIN_RESULTS_SECONDS", 5.0)
    monkeypatch.setattr(game, "MAX_RESULTS_SECONDS", 5.0)
    ana, bia, created, joined = await setup_room(connect)
    assert not (await ana.call("update_settings", {"mode": "turbo"}))["ok"]
    await ana.call("update_settings", {"rounds": 10, "mode": "powers"})
    await ana.call("start_game")
    start = await bia.wait_for(lambda s: s["game"] is not None)
    assert len(start["game"]["powerups"]) == 1  # só a dela

    await ana.wait_for(lambda s: s["game"]["phase"] == "answering")
    await ana.call("submit_answer", {"option": 0})
    await bia.call("submit_answer", {"option": 0})
    await ana.wait_for(lambda s: s["game"]["phase"] == "results")
    kind = ana.state["game"]["powerups"][0]
    if kind in INSTANT or kind in ("backpack", "theme", "investment"):  # troca por uma de armar simples
        kind = "mirror"
        main.rooms.rooms[start["code"]].game.powerups[created["player_id"]] = [kind]
    target = joined["player_id"] if kind in TARGETED else None
    assert (await ana.call("arm_powerup", {"kind": kind, "target": target}))["ok"]
    assert ana.state["game"]["armed"]["kind"] == kind
    assert bia.state["game"]["armed"] is None

    assert (await ana.call("skip_results"))["ok"]
    assert (await bia.call("skip_results"))["ok"]
    # Todos pularam: a próxima pergunta abre bem antes dos 5 s, já com a habilidade valendo.
    state = await ana.wait_for(lambda s: s["game"]["round"] == 2, timeout=1)
    assert state["game"]["active"] == [{"kind": kind, "by": created["player_id"], "target": target, "reflected_by": None, "legendary": False, "theme": None}]
    # O roubo é surpresa (o alvo só fica sabendo na revelação) e o Reverso armado é segredo.
    hidden = await bia.wait_for(lambda s: s["game"]["round"] == 2, timeout=1)
    assert hidden["game"]["active"] == ([] if kind in ("steal", "reverse") else state["game"]["active"])


async def test_abandoned_match_is_kept_in_history(connect):
    ana, bia, created, _ = await setup_room(connect)
    await ana.call("start_game")
    await ana.wait_for(lambda s: s["game"] and s["game"]["phase"] == "answering")
    await ana.call("leave_room")
    await bia.call("leave_room")  # sala vazia: some, e a partida fecha quando a fase acabar

    async def closed():
        while main.history.db.execute("SELECT status FROM matches").fetchall() != [("abandoned",)]:
            await asyncio.sleep(0.05)

    await asyncio.wait_for(closed(), timeout=2)


async def test_history_download_needs_the_token(server_url, monkeypatch):
    async with httpx.AsyncClient(base_url=server_url) as client:
        assert (await client.get("/history.db")).status_code == 404  # sem token configurado: desligada
        monkeypatch.setattr(main, "HISTORY_TOKEN", "segredo")
        assert (await client.get("/history.db", headers={"Authorization": "Bearer errado"})).status_code == 404
        response = await client.get("/history.db", headers={"Authorization": "Bearer segredo"})
    assert response.status_code == 200 and response.content.startswith(b"SQLite format 3")


async def test_duel_stops_the_match_and_then_it_goes_on(connect, monkeypatch):
    from app import duel as x1

    monkeypatch.setattr(game, "MIN_RESULTS_SECONDS", 5.0)
    monkeypatch.setattr(game, "MAX_RESULTS_SECONDS", 5.0)
    monkeypatch.setattr(x1, "INTRO_SECONDS", 0.05)
    monkeypatch.setattr(x1, "FIRST_SECONDS", 0.6)
    monkeypatch.setattr(x1, "STEP_SECONDS", 0.0)
    monkeypatch.setattr(x1, "RESULTS_SECONDS", 0.02)
    monkeypatch.setattr(x1, "END_SECONDS", 0.05)
    ana, bia, created, joined = await setup_room(connect)
    await ana.call("update_settings", {"rounds": 10, "mode": "powers"})
    await ana.call("start_game")
    await ana.wait_for(lambda s: s["game"] is not None and s["game"]["phase"] == "answering")
    await ana.call("submit_answer", {"option": 0})
    await bia.call("submit_answer", {"option": 0})
    await ana.wait_for(lambda s: s["game"]["phase"] == "results")
    main.rooms.rooms[created["room"]["code"]].game.mythics[created["player_id"]] = ["duel"]
    assert (await ana.call("arm_powerup", {"kind": "duel", "target": joined["player_id"]}))["ok"]
    assert (await bia.wait_for(lambda s: s["game"]["duels"] != []))["game"]["duels"][0]["rival"] == joined["player_id"]
    await ana.call("skip_results")
    await bia.call("skip_results")
    state = await ana.wait_for(lambda s: s["game"]["phase"] == "duel_answering")
    assert state["game"]["duel"]["question_number"] == 1 and state["game"]["duel"]["kind"] == "true_false"
    # Ninguém responde: os dois "erram" todas, e no fim o tempo empata e decide.
    end = await ana.wait_for(lambda s: s["game"]["phase"] == "duel_end", timeout=10)
    assert end["game"]["duel"]["winner"] in (created["player_id"], joined["player_id"])
    await ana.wait_for(lambda s: s["game"]["round"] == 2 and s["game"]["phase"] in ("reading", "answering"), timeout=3)


async def test_last_standing_plays_to_a_winner(connect, monkeypatch):
    from app import survival

    for name in ("START_SECONDS", "LEVEL_SECONDS", "RESULTS_SECONDS", "DUEL_INTRO_SECONDS", "DUEL_RESULTS_SECONDS", "LATE_SECONDS"):
        monkeypatch.setattr(survival, name, 0.05)
    monkeypatch.setitem(survival.RULES, "true_false", dataclasses.replace(survival.RULES["true_false"], answer_seconds=0.5))
    ana, bia, caio = await connect(), await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})
    await caio.call("join_room", {"code": code, "nickname": "Caio", "avatar": "urso"})
    await ana.call("update_settings", {"mode": "last_standing"})
    assert (await ana.call("start_game"))["ok"]
    game = main.rooms.rooms[code].survival

    def sv(state: dict) -> dict:
        return state["survival"] or {}

    # Ana acerta e Bia erra; Caio não responde, mas a frase só fecha no tempo.
    for round_ in (1, 2):
        await ana.wait_for(lambda s: sv(s).get("round") == round_ and sv(s)["phase"] == "answering")
        assert (await ana.call("submit_answer", {"option": game.question.answer}))["ok"]
        assert (await bia.call("submit_answer", {"option": 1 - game.question.answer}))["ok"]
        state = await ana.wait_for(lambda s: sv(s).get("phase") not in (None, "answering"), timeout=12)
        assert sv(state)["correct_option"] == game.question.answer or sv(state)["phase"] == "finished"
    state = await caio.wait_for(lambda s: sv(s).get("phase") == "finished")
    assert sv(state)["winner"] == created["player_id"]
    assert [s["place"] for s in sv(state)["survivors"]][0] == 1


async def test_hot_potato_passes_and_explodes(connect, monkeypatch):
    from app import hot_potato

    monkeypatch.setattr(hot_potato, "START_SECONDS", 0.05)
    monkeypatch.setattr(hot_potato, "PASS_SECONDS", 0.05)
    monkeypatch.setattr(hot_potato, "FUSE_SECONDS", (0.6, 0.6))
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    joined = await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})
    await ana.call("update_settings", {"mode": "hot_potato"})
    assert (await ana.call("start_game"))["ok"]
    game = main.rooms.rooms[code].hot_potato

    def hp(state: dict) -> dict:
        return state["hot_potato"] or {}

    state = await ana.wait_for(lambda s: hp(s).get("phase") == "asking")
    first = hp(state)["holder"]
    client = ana if first == created["player_id"] else bia
    assert (await client.call("submit_answer", {"option": game.question.answer}))["ok"]
    state = await ana.wait_for(lambda s: hp(s).get("phase") == "asking" and hp(s)["holder"] != first)
    second = hp(state)["holder"]
    assert second in (created["player_id"], joined["player_id"])
    state = await ana.wait_for(lambda s: hp(s).get("phase") == "exploded")
    assert hp(state)["exploded"] == second


async def test_hot_potato_with_powers_uses_them_on_the_spot(connect, monkeypatch):
    from app import hot_potato

    monkeypatch.setattr(hot_potato, "START_SECONDS", 0.05)
    monkeypatch.setattr(hot_potato, "PASS_SECONDS", 0.05)
    ana, bia = await connect(), await connect()
    created = await ana.call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    await bia.call("join_room", {"code": code, "nickname": "Bia", "avatar": "sapo"})
    await ana.call("update_settings", {"mode": "hot_potato", "survival_powers": True})
    assert (await ana.call("start_game"))["ok"]
    game = main.rooms.rooms[code].hot_potato

    def hp(state: dict) -> dict:
        return state["hot_potato"] or {}

    state = await ana.wait_for(lambda s: hp(s).get("phase") == "asking")
    assert hp(state)["powers"] and len(hp(state)["powerups"]) == 1
    first = hp(state)["holder"]
    client = ana if first == created["player_id"] else bia
    game.held[first] = ["free_pass"]
    assert (await client.call("use_powerup", {"kind": "free_pass"}))["ok"]
    state = await ana.wait_for(lambda s: hp(s).get("phase") == "asking" and hp(s)["holder"] != first)
    assert hp(state)["holder"] != first


async def test_teams_vote_together_and_choose_who_goes_alone(connect, monkeypatch):
    from app import teams

    monkeypatch.setattr(teams, "START_SECONDS", 0.05)
    monkeypatch.setattr(teams, "reading_seconds", lambda text: 0.05)
    monkeypatch.setattr(teams, "results_seconds", lambda fact: 0.05)
    monkeypatch.setattr(teams, "LEVEL_SECONDS", 0.05)
    clients = [await connect() for _ in range(4)]
    created = await clients[0].call("create_room", {"nickname": "Ana", "avatar": "gato"})
    code = created["room"]["code"]
    ids = [created["player_id"]]
    for i, client in enumerate(clients[1:]):
        ids.append((await client.call("join_room", {"code": code, "nickname": f"P{i}", "avatar": "sapo"}))["player_id"])
    host = clients[0]
    assert (await host.call("update_settings", {"mode": "teams", "team_pick": "host"}))["ok"]
    assert not (await clients[1].call("set_team", {"player_id": ids[0], "team": 1}))["ok"]
    for pid, team in zip(ids, (0, 1, 0, 1)):
        assert (await host.call("set_team", {"player_id": pid, "team": team}))["ok"]
    assert (await host.call("start_game"))["ok"]
    match = main.rooms.rooms[code].team_match
    by_id = dict(zip(ids, clients))

    def tm(state: dict) -> dict:
        return state["team_match"] or {}

    state = await host.wait_for(lambda s: tm(s).get("phase") == "answering")
    assert [t["members"] for t in tm(state)["teams"]] == [[ids[0], ids[2]], [ids[1], ids[3]]]
    answer = match.question.answer
    assert (await by_id[ids[2]].call("submit_answer", {"option": answer}))["ok"]
    # O colega vê o voto na hora; o outro time só vê que alguém votou.
    state = await host.wait_for(lambda s: tm(s)["teams"][0]["votes"])
    assert tm(state)["teams"][0]["votes"] == [{"player_id": ids[2], "option": answer}]
    rival = await clients[1].wait_for(lambda s: tm(s)["teams"][0]["voted"])
    assert tm(rival)["teams"][0]["votes"] == []
    for pid in (ids[0], ids[1], ids[3]):
        assert (await by_id[pid].call("submit_answer", {"option": answer}))["ok"]
    state = await host.wait_for(lambda s: tm(s).get("phase") == "results")
    assert all(t["correct"] and t["captain_delta"] == 3 for t in tm(state)["teams"])
