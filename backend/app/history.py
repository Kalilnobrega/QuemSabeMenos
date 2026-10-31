"""Histórico das partidas em SQLite, para analisar depois.

Uma linha por partida (configuração, duração e placar final), uma por pergunta (com as
alternativas na ordem mostrada, os tempos de cada fase e os poderes) e uma por resposta de cada
jogador, que é o que permite medir a taxa de acerto de cada pergunta e recalibrar a dificuldade.

Horários em segundos desde 1970 (time.time()); listas e objetos como JSON.
"""

import json
import sqlite3
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.rooms import Room

SCHEMA = """
CREATE TABLE IF NOT EXISTS matches (
    id TEXT PRIMARY KEY,
    room_code TEXT NOT NULL,
    status TEXT NOT NULL,  -- playing, finished ou abandoned
    started_at REAL NOT NULL,
    ended_at REAL,
    mode TEXT NOT NULL,
    rounds INTEGER NOT NULL,
    answer_seconds REAL NOT NULL,
    speed_grace_seconds REAL NOT NULL,
    powerup_max INTEGER,  -- só no modo com poderes
    themes TEXT NOT NULL,
    players TEXT NOT NULL  -- do 1º ao último: id, apelido, avatar, QI, tempo total de resposta
);
CREATE TABLE IF NOT EXISTS rounds (
    match_id TEXT NOT NULL REFERENCES matches(id),
    round INTEGER NOT NULL,  -- começa em 1
    question_id TEXT NOT NULL,
    theme TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    options TEXT NOT NULL,  -- na ordem mostrada nesta partida
    answer INTEGER NOT NULL,
    bet_round INTEGER NOT NULL,
    reading_at REAL NOT NULL,
    answers_at REAL NOT NULL,
    closed_at REAL NOT NULL,
    ended_at REAL,  -- fim da revelação
    skipped INTEGER,  -- a revelação acabou antes porque todos pularam
    powerups TEXT NOT NULL,  -- poderes valendo: tipo, quem usou, alvo, quem devolveu
    PRIMARY KEY (match_id, round)
);
CREATE TABLE IF NOT EXISTS answers (
    match_id TEXT NOT NULL REFERENCES matches(id),
    round INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    connected INTEGER NOT NULL,
    option INTEGER,  -- NULL = não respondeu
    correct INTEGER NOT NULL,
    elapsed_ms INTEGER,
    delta INTEGER NOT NULL,
    bonus INTEGER NOT NULL,
    bet INTEGER,
    bet_delta INTEGER NOT NULL,
    shielded INTEGER NOT NULL,
    stolen INTEGER NOT NULL,
    robbed INTEGER NOT NULL,
    doubled INTEGER NOT NULL,
    first_option INTEGER,
    expired TEXT NOT NULL,
    gained TEXT,
    score_after INTEGER NOT NULL,
    PRIMARY KEY (match_id, round, player_id)
);
CREATE INDEX IF NOT EXISTS answers_by_question ON answers (match_id, round);
CREATE INDEX IF NOT EXISTS rounds_by_question ON rounds (question_id);
"""


class MatchHistory:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, check_same_thread=False)
        self.db.executescript(SCHEMA)

    def start(self, room: "Room", now: float) -> str:
        match_id = uuid.uuid4().hex
        with self.db:
            self.db.execute(
                "INSERT INTO matches VALUES (?, ?, 'playing', ?, NULL, ?, ?, ?, ?, ?, ?, ?)",
                (
                    match_id,
                    room.code,
                    now,
                    # O clássico com poderes era um modo à parte: segue gravado como "powers".
                    "powers" if room.mode == "classic" and room.powers else room.mode,
                    room.rounds,
                    room.answer_seconds,
                    room.speed_grace_seconds,
                    room.powerup_max if room.game and room.game.powers else None,
                    json.dumps(room.themes, ensure_ascii=False),
                    _standings(room),
                ),
            )
        return match_id

    def round_closed(self, match_id: str, room: "Room", reading_at: float, answers_at: float, now: float) -> None:
        game = room.game
        q = game.question
        scores = {p.id: p for p in room.players}
        with self.db:
            self.db.execute(
                "INSERT OR REPLACE INTO rounds VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)",
                (
                    match_id,
                    game.round + 1,
                    q.id,
                    q.theme,
                    q.difficulty,
                    json.dumps(q.options, ensure_ascii=False),
                    q.answer,
                    int(game.is_bet_round),
                    reading_at,
                    answers_at,
                    now,
                    json.dumps([use.model_dump() for use in game.active]),
                ),
            )
            self.db.executemany(
                "INSERT OR REPLACE INTO answers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        match_id,
                        game.round + 1,
                        r.player_id,
                        scores[r.player_id].nickname,
                        int(scores[r.player_id].connected),
                        r.option,
                        int(r.correct),
                        r.elapsed_ms,
                        r.delta,
                        sum(b.delta for b in r.bonuses),
                        r.bet,
                        r.bet_delta,
                        r.shielded,
                        r.stolen,
                        r.robbed,
                        int(r.doubled),
                        r.first_option,
                        json.dumps(r.expired),
                        r.gained.model_dump_json() if r.gained else None,
                        scores[r.player_id].score,
                    )
                    for r in game.results
                    if r.player_id in scores
                ],
            )

    def round_ended(self, match_id: str, round_number: int, now: float, skipped: bool) -> None:
        with self.db:
            self.db.execute(
                "UPDATE rounds SET ended_at = ?, skipped = ? WHERE match_id = ? AND round = ?",
                (now, int(skipped), match_id, round_number),
            )

    def snapshot(self) -> bytes:
        """Cópia consistente do banco inteiro, para baixar e analisar."""
        return self.db.serialize()

    def finish(self, match_id: str, room: "Room", status: str, now: float) -> None:
        with self.db:
            self.db.execute(
                "UPDATE matches SET status = ?, ended_at = ?, players = ? WHERE id = ?",
                (status, now, _standings(room), match_id),
            )


def _standings(room: "Room") -> str:
    """Mais QI primeiro; no empate, quem respondeu mais rápido na soma da partida."""
    ranked = sorted(room.players, key=lambda p: (-p.score, p.answer_ms))
    return json.dumps(
        [
            {"id": p.id, "nickname": p.nickname, "avatar": p.avatar, "score": p.score, "answer_ms": p.answer_ms}
            for p in ranked
        ],
        ensure_ascii=False,
    )
