from pathlib import Path
from typing import get_args

import pytest

from app.events import Avatar, Profile
from app.rooms import CODE_ALPHABET, CODE_LENGTH, MAX_PLAYERS, RoomError, RoomManager


def profile(nickname: str, avatar: str = "gato") -> Profile:
    return Profile(nickname=nickname, avatar=avatar)


@pytest.fixture
def manager() -> RoomManager:
    return RoomManager()


def test_create_room_makes_creator_host(manager):
    room, player = manager.create("sid-ana", profile("Ana"))
    assert len(room.code) == CODE_LENGTH
    assert set(room.code) <= set(CODE_ALPHABET)
    assert room.host_id == player.id
    assert room.view().players[0].nickname == "Ana"


def test_join_is_case_insensitive_and_keeps_order(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    manager.join("sid-bia", room.code.lower(), profile("Bia"))
    assert [p.nickname for p in room.players] == ["Ana", "Bia"]


def test_join_unknown_room(manager):
    with pytest.raises(RoomError, match="não encontrada"):
        manager.join("sid-bia", "ZZZZZ", profile("Bia"))


def test_join_rejects_duplicate_nickname(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    with pytest.raises(RoomError, match="apelido"):
        manager.join("sid-ana2", room.code, profile("  ana "))


def test_nickname_whitespace_is_collapsed_and_blank_rejected(manager):
    room, player = manager.create("sid-ana", profile("  Ana   Maria "))
    assert player.nickname == "Ana Maria"
    with pytest.raises(RoomError, match="apelido"):
        manager.join("sid-x", room.code, profile("   "))


def test_room_is_capped(manager):
    room, _ = manager.create("sid-0", profile("P0"))
    for i in range(1, MAX_PLAYERS):
        manager.join(f"sid-{i}", room.code, profile(f"P{i}"))
    with pytest.raises(RoomError, match="cheia"):
        manager.join("sid-extra", room.code, profile("Extra"))


def test_host_leaving_passes_host_to_oldest(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    _, bia = manager.join("sid-bia", room.code, profile("Bia"))
    manager.join("sid-caio", room.code, profile("Caio"))
    manager.leave("sid-ana")
    assert room.host_id == bia.id


def test_host_transfer_prefers_connected_player(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    manager.join("sid-bia", room.code, profile("Bia"))
    _, caio = manager.join("sid-caio", room.code, profile("Caio"))
    manager.disconnect("sid-bia")
    manager.leave("sid-ana")
    assert room.host_id == caio.id


def test_last_player_leaving_deletes_room(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    assert manager.leave("sid-ana") is None
    assert room.code not in manager.rooms


def test_disconnected_player_can_rejoin_with_token(manager):
    room, ana = manager.create("sid-ana", profile("Ana"))
    manager.join("sid-bia", room.code, profile("Bia"))
    _, _, seq = manager.disconnect("sid-ana")
    assert not ana.connected

    manager.rejoin("sid-ana-new", room.code, ana.token)
    assert ana.connected
    assert manager.expire(room.code, ana.id, seq) is None  # voltou a tempo: continua
    assert ana in room.players
    assert room.host_id == ana.id


def test_expire_removes_player_who_did_not_return(manager):
    room, ana = manager.create("sid-ana", profile("Ana"))
    _, bia = manager.join("sid-bia", room.code, profile("Bia"))
    _, _, seq = manager.disconnect("sid-ana")
    assert manager.expire(room.code, ana.id, seq) is room
    assert [p.nickname for p in room.players] == ["Bia"]
    assert room.host_id == bia.id


def test_stale_expire_timer_is_ignored(manager):
    room, ana = manager.create("sid-ana", profile("Ana"))
    _, _, first_seq = manager.disconnect("sid-ana")
    manager.rejoin("sid-2", room.code, ana.token)
    manager.disconnect("sid-2")
    assert manager.expire(room.code, ana.id, first_seq) is None
    assert ana in room.players


def test_rejoin_with_wrong_token(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    with pytest.raises(RoomError):
        manager.rejoin("sid-x", room.code, "token-falso")


def test_rejoin_from_new_tab_returns_old_sid(manager):
    room, ana = manager.create("sid-ana", profile("Ana"))
    _, _, old_sid = manager.rejoin("sid-ana-tab2", room.code, ana.token)
    assert old_sid == "sid-ana"
    assert manager.session("sid-ana") is None


def test_only_host_starts_with_enough_players(manager):
    room, _ = manager.create("sid-ana", profile("Ana"))
    with pytest.raises(RoomError, match="pelo menos"):
        manager.start("sid-ana")
    manager.join("sid-bia", room.code, profile("Bia"))
    with pytest.raises(RoomError, match="anfitrião"):
        manager.start("sid-bia")
    assert manager.start("sid-ana").status == "playing"
    with pytest.raises(RoomError, match="já começou"):
        manager.join("sid-caio", room.code, profile("Caio"))


def test_avatar_ids_match_frontend_assets():
    assets = Path(__file__).resolve().parents[2] / "frontend" / "src" / "assets" / "avatars"
    assert {f.stem for f in assets.glob("*.svg")} == set(get_args(Avatar))
