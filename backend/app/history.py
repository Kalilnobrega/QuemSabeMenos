"""Histórico das partidas em SQLite, para analisar depois.

Uma linha por partida (configuração, duração e placar final), uma por pergunta (com as
alternativas na ordem mostrada, os tempos de cada fase e os poderes) e uma por resposta de cada
jogador, que é o que permite medir a taxa de acerto de cada pergunta e recalibrar a dificuldade.

Os modos com motor próprio (Último de pé, Batata quente, Times e Chutômetro) gravam a linha da
partida e, no lugar de `rounds`/`answers`, uma linha por acontecimento em `events`: a configuração,
cada pergunta fechada (com o que cada um respondeu), cada explosão, cada poder da Batata quente e o
X1 dos Times. No fim, `matches.players` traz a classificação do próprio modo.

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
CREATE TABLE IF NOT EXISTS events (
    match_id TEXT NOT NULL REFERENCES matches(id),
    seq INTEGER NOT NULL,  -- começa em 1, na ordem em que aconteceu
    at REAL NOT NULL,
    kind TEXT NOT NULL,  -- settings, question, answer, explosion, power, duel
    data TEXT NOT NULL,
    PRIMARY KEY (match_id, seq)
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
                    room.powerup_max if room.powers else None,
                    json.dumps(room.themes, ensure_ascii=False),
                    _standings(room),
                ),
            )
        if room.mode != "classic" and room.mode != "specialist":
            self.event(match_id, "settings", _settings(room), now)
        return match_id

    def event(self, match_id: str, kind: str, data: dict, now: float) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO events VALUES (?, (SELECT COALESCE(MAX(seq), 0) + 1 FROM events WHERE match_id = ?), ?, ?, ?)",
                (match_id, match_id, now, kind, json.dumps(data, ensure_ascii=False)),
            )

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

    def finish(self, match_id: str, room: "Room", status: str, now: float, standings: list[dict] | None = None) -> None:
        """`standings`: a classificação do modo, quando não é por QI (Último de pé, Batata quente, Times)."""
        players = _standings(room) if standings is None else json.dumps(standings, ensure_ascii=False)
        with self.db:
            self.db.execute(
                "UPDATE matches SET status = ?, ended_at = ?, players = ? WHERE id = ?",
                (status, now, players, match_id),
            )


def _standings(room: "Room") -> str:
    return json.dumps(score_standings(room.players), ensure_ascii=False)


def score_standings(players) -> list[dict]:
    """Mais QI primeiro; no empate, quem respondeu mais rápido na soma da partida."""
    ranked = sorted(players, key=lambda p: (-p.score, p.answer_ms))
    return [
        {"id": p.id, "nickname": p.nickname, "avatar": p.avatar, "score": p.score, "answer_ms": p.answer_ms}
        for p in ranked
    ]


def _settings(room: "Room") -> dict:
    settings: dict = {"powers": room.powers}
    if room.mode == "last_standing":
        settings["survival_kind"] = room.survival_kind
    if room.mode == "teams" and room.team_match:
        settings["team_count"] = room.team_count
        settings["team_pick"] = room.team_pick
        settings["teams"] = team_lineup(room.team_match)
    return settings


def _dump(value):
    return value.model_dump() if hasattr(value, "model_dump") else value


def _question(q) -> dict:
    return {"question_id": q.id, "theme": q.theme, "difficulty": q.difficulty}


def roster(room: "Room") -> dict:
    """Quem começou a partida, para a classificação final incluir também quem saiu no meio."""
    return {p.id: p for p in room.players}


def _who(players: dict, player_id: str) -> dict:
    p = players.get(player_id)
    return {"id": player_id, "nickname": p.nickname if p else None, "avatar": p.avatar if p else None}


# --- Último de pé ------------------------------------------------------------


def survival_question(s, room: "Room") -> dict:
    """A pergunta que acabou de fechar: o que cada vivo respondeu e quantas vidas sobraram."""
    return {
        **_question(s.question),
        "round": s.round,
        "duel_round": s.duel_round or None,
        "kind": s.kind,
        "options": s.question.options,
        "answer": s.question.answer,
        "spared": s.spared,
        "picks": [pick.model_dump() for pick in s.picks],
        "lives": {c.id: c.lives for c in s.contenders},
        "powers": [use.model_dump() for use in s.active],
        "stabs": [_dump(stab) for stab in s.stabs],
        "revived": list(s.revived),
    }


def survival_standings(s, players: dict) -> list[dict]:
    """Quem venceu primeiro; depois quem caiu mais tarde (a mesma rodada desempata pelo tempo)."""
    ranked = sorted(
        s.contenders,
        key=lambda c: (c.id != s.winner, -(c.out_round if c.out_round is not None else 10**6), c.answer_ms),
    )
    return [
        {
            **_who(players, c.id),
            "lives": c.lives,
            "out_round": c.out_round,
            "correct": c.correct,
            "answer_ms": c.answer_ms,
        }
        for c in ranked
    ]


# --- Batata quente -----------------------------------------------------------


def hot_potato_events(potato) -> list[tuple[str, dict]]:
    """Tira da fila da Batata quente o que aconteceu desde a última vez (respostas, explosões, poderes)."""
    events, potato.log = potato.log, []
    return [(kind, {key: _dump(value) for key, value in data.items()}) for kind, data in events]


def hot_potato_standings(h, players: dict) -> list[dict]:
    """Quem venceu primeiro; depois quem explodiu mais tarde."""
    ranked = sorted(h.players, key=lambda p: (p.id != h.winner, -(p.out_round if p.out_round is not None else 10**6)))
    return [
        {
            **_who(players, p.id),
            "out_round": p.out_round,
            "correct": p.correct,
            "wrong": p.wrong,
        }
        for p in ranked
    ]


# --- Times -------------------------------------------------------------------


def team_question(m) -> dict:
    """A pergunta que acabou de fechar: o voto de cada um, o que o time travou e o que ganhou."""
    q = m.question
    return {
        **_question(q),
        "round": m.round + 1,
        "solo": m.solo,
        "bet_round": m.round == m.bet_index,
        "options": q.options,
        "answer": q.answer,
        "teams": [
            {
                "team": t.id,
                "members": t.members,
                "captain": t.captain,
                "representative": t.representative,
                "votes": {pid: vote[0] for pid, vote in t.votes.items()},
                "option": t.option,
                "correct": t.correct,
                "delta": t.delta,
                "captain_delta": t.captain_delta,
                "harmony_delta": t.harmony_delta,
                "bet": t.bet,
                "bet_delta": t.bet_delta,
                "shielded": t.shielded,
                "doubled": t.doubled,
                "stolen": t.stolen,
                "robbed": t.robbed,
                "tolled": t.tolled,
                "toll_received": t.toll_received,
                "tricked": t.tricked,
                "tax": t.tax,
                "effects": list(t.effects),
                "gained": _dump(t.gained) if t.gained else None,
                "score": t.score,
            }
            for t in m.teams
        ],
        "powers": [use.model_dump() for use in m.active],
    }


def team_duel(m) -> dict:
    """Um X1 dos Times que acabou: quem duelou, quem venceu e o placar dos times depois."""
    duel = m.duel
    return {
        "round": m.round + 1,
        "teams": list(m.duel_teams) if m.duel_teams else None,
        "fighters": list(duel.fighters) if duel else None,
        "winner": duel.winner if duel else None,
        "paid": duel.paid if duel else None,
        "bets": dict(duel.bets) if duel else None,
        "scores": {t.id: t.score for t in m.teams},
    }


def team_lineup(m) -> list[list[str]]:
    return [list(t.members) for t in m.teams]


def team_standings(m, players: dict, lineup: list[list[str]]) -> list[dict]:
    """Times do maior QI para o menor, com o desempenho de cada jogador. `lineup`: os times do começo,
    porque quem sai no meio deixa o time."""
    return [
        {
            "team": t.id,
            "score": t.score,
            "players": [
                {**_who(players, pid), **(vars(m.stats[pid]) if pid in m.stats else {})}
                for pid in dict.fromkeys(lineup[t.id] + t.members)
            ],
        }
        for t in sorted(m.teams, key=lambda t: -t.score)
    ]


# --- Chutômetro --------------------------------------------------------------


def estimate_question(e) -> dict:
    """A pergunta que acabou de fechar: o chute de cada um, o erro e os pontos."""
    q = e.question
    return {
        **_question(q),
        "round": e.round + 1,
        "answer": q.answer,
        "unit": q.unit,
        "scale": q.scale,
        "guesses": [g.model_dump() for g in e.results],
        "uses": [use.model_dump() for use in e.active],
    }
