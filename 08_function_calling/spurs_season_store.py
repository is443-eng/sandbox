# spurs_season_store.py
# SQLite store + NBA API loader + SQL search for San Antonio Spurs player game lines.
# Canonical copy in 08_function_calling (07_rag re-exports for older scripts).

from __future__ import annotations

import re
import sys
import sqlite3
import time
from calendar import monthrange
from datetime import date
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import boxscoretraditionalv3
from nba_api.stats.endpoints import boxscoresummaryv2
from nba_api.stats.endpoints import boxscoresummaryv3
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.static import teams

SAS_ABBREV = "SAS"

# Lowercase token → NBA tricode (`matchup` uses tricodes, e.g. SAS @ OKC, not team nicknames).
_OPPONENT_NICKNAME_TO_TRICODE: dict[str, str] = {
    "thunder": "OKC",
    "lakers": "LAL",
    "warriors": "GSW",
    "celtics": "BOS",
    "nuggets": "DEN",
    "rockets": "HOU",
    "mavericks": "DAL",
    "mavs": "DAL",
    "grizzlies": "MEM",
    "grizz": "MEM",
    "timberwolves": "MIN",
    "wolves": "MIN",
    "pelicans": "NOP",
    "pels": "NOP",
    "jazz": "UTA",
    "suns": "PHX",
    "blazers": "POR",
    "kings": "SAC",
    "clippers": "LAC",
    "sixers": "PHI",
    "nets": "BKN",
    "knicks": "NYK",
    "bucks": "MIL",
    "bulls": "CHI",
    "cavs": "CLE",
    "cavaliers": "CLE",
    "hawks": "ATL",
    "hornets": "CHA",
    "heat": "MIA",
    "magic": "ORL",
    "pistons": "DET",
    "pacers": "IND",
    "raptors": "TOR",
    "wizards": "WAS",
    "oklahoma": "OKC",
}


def resolve_opponent_tricode(raw: str) -> str | None:
    """
    Map a user/model string to a 3-letter opponent tricode for ``matchup`` filtering.

    Accepts nicknames (e.g. thunder), full cleaned phrases, or a 3-letter code (okc, OKC).
    """
    s = (raw or "").strip()
    if not s:
        return None
    low_full = re.sub(r"[^a-z0-9]+", "", s.lower())
    if low_full in _OPPONENT_NICKNAME_TO_TRICODE:
        return _OPPONENT_NICKNAME_TO_TRICODE[low_full]
    for t in re.findall(r"[A-Za-z0-9]+", s):
        tl = t.lower()
        if tl in _OPPONENT_NICKNAME_TO_TRICODE:
            return _OPPONENT_NICKNAME_TO_TRICODE[tl]
    alnum = re.sub(r"[^A-Za-z]", "", s).upper()
    if len(alnum) == 3 and alnum.isalpha():
        return alnum
    return None


def _expand_tokens_with_opponent_nicknames(tokens: list[str]) -> list[str]:
    """Append tricode tokens when a token is a known nickname (``matchup`` stores OKC, not Thunder)."""
    if not tokens:
        return tokens
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
        tl = t.lower()
        tri = _OPPONENT_NICKNAME_TO_TRICODE.get(tl)
        if tri and tri not in seen:
            seen.add(tri)
            out.append(tri)
    return out


def current_nba_season_id(today: date | None = None) -> str:
    """
    NBA season string as used by nba_api (e.g. ``2025-26``).

    The league year is roughly October–June: months Oct–Dec belong to the season
    starting that calendar year; Jan–Sep belong to the season that started the
    previous calendar year.
    """
    d = today or date.today()
    y, m = d.year, d.month
    start_year = y if m >= 10 else y - 1
    end_yy = (start_year + 1) % 100
    return f"{start_year}-{end_yy:02d}"


SCHEMA = """
CREATE TABLE IF NOT EXISTS player_game (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    game_date TEXT,
    matchup TEXT,
    wl TEXT,
    team TEXT NOT NULL,
    player_name TEXT NOT NULL,
    min TEXT,
    pts INTEGER,
    reb INTEGER,
    ast INTEGER,
    stl INTEGER,
    blk INTEGER,
    turnovers INTEGER,
    plus_minus INTEGER,
    nba_season TEXT
);
CREATE INDEX IF NOT EXISTS idx_player_game_name ON player_game(player_name);
CREATE INDEX IF NOT EXISTS idx_player_game_date ON player_game(game_date);
CREATE TABLE IF NOT EXISTS db_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS game_line_score (
    game_id TEXT PRIMARY KEY,
    spurs_q1 INTEGER NOT NULL,
    spurs_q2 INTEGER NOT NULL,
    spurs_q3 INTEGER NOT NULL,
    spurs_q4 INTEGER NOT NULL,
    opp_q1 INTEGER NOT NULL,
    opp_q2 INTEGER NOT NULL,
    opp_q3 INTEGER NOT NULL,
    opp_q4 INTEGER NOT NULL,
    spurs_final INTEGER,
    opp_final INTEGER,
    opp_abbrev TEXT,
    nba_season TEXT
);
"""


def _spurs_team_id() -> int:
    nba_teams = teams.get_teams()
    spurs = [t for t in nba_teams if t["abbreviation"] == SAS_ABBREV]
    if not spurs:
        raise ValueError("San Antonio Spurs (SAS) not found in nba_api teams.")
    return spurs[0]["id"]


def _boxscore_traditional_frames(
    game_id: str,
    *,
    retries: int = 3,
    retry_delay_sec: float = 0.75,
) -> tuple[list | None, str | None]:
    """
    Fetch BoxScoreTraditionalV3 frames with retries.

    Timeouts and empty responses from stats.nba.com are common; a later attempt often succeeds.
    Returns (frames, None) on success, or (None, reason) after all attempts fail.
    """
    gid = str(game_id).strip().zfill(10)
    last_reason = "empty or missing box score"
    for attempt in range(retries):
        try:
            box = boxscoretraditionalv3.BoxScoreTraditionalV3(
                game_id=gid,
                start_period=0,
                end_period=14,
                start_range=0,
                end_range=0,
                range_type=0,
            )
            frames = box.get_data_frames()
            if not frames or frames[0].empty:
                if attempt < retries - 1 and retry_delay_sec > 0:
                    time.sleep(retry_delay_sec)
                continue
            return frames, None
        except Exception as e:
            last_reason = f"{type(e).__name__}: {e}"
            if attempt < retries - 1 and retry_delay_sec > 0:
                time.sleep(retry_delay_sec)
    return None, last_reason



def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return {str(row[1]) for row in cur.fetchall()}


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
    # Migrate older DBs created before nba_season / db_meta
    cols = _table_columns(conn, "player_game")
    if "nba_season" not in cols:
        conn.execute("ALTER TABLE player_game ADD COLUMN nba_season TEXT")
        conn.commit()
    meta_cols = _table_columns(conn, "db_meta")
    if not meta_cols:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS db_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.commit()
    # game_line_score: add final scores for OT games (Q1–Q4 sum to regulation only)
    gls_cols = _table_columns(conn, "game_line_score")
    if gls_cols and "spurs_final" not in gls_cols:
        conn.execute("ALTER TABLE game_line_score ADD COLUMN spurs_final INTEGER")
        conn.execute("ALTER TABLE game_line_score ADD COLUMN opp_final INTEGER")
        conn.commit()


def line_scores_from_api(game_id: str) -> list[dict] | None:
    """
    Quarter-by-quarter team points for one game (V3 then V2).
    Each dict: team_abbrev, q1..q4, total. Spurs row sorted first when present.
    """
    game_id_10 = str(int(str(game_id).strip())).zfill(10)

    try:
        summary_v3 = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id_10)
        frames = summary_v3.get_data_frames()
        if len(frames) > 4 and not frames[4].empty:
            df = frames[4]
            rows: list[dict] = []
            for _, r in df.iterrows():
                rows.append(
                    {
                        "team_abbrev": str(r.get("teamTricode", r.get("team_id", ""))),
                        "q1": int(r.get("period1Score", 0) or 0),
                        "q2": int(r.get("period2Score", 0) or 0),
                        "q3": int(r.get("period3Score", 0) or 0),
                        "q4": int(r.get("period4Score", 0) or 0),
                        "total": int(r.get("score", 0) or 0),
                    }
                )
            rows.sort(
                key=lambda x: (0 if str(x.get("team_abbrev")) == SAS_ABBREV else 1)
            )
            return rows
    except Exception:
        pass

    try:
        summary_v2 = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id_10)
        frames = summary_v2.get_data_frames()
        if len(frames) > 5 and not frames[5].empty:
            df = frames[5]
            rows = []
            for _, r in df.iterrows():
                rows.append(
                    {
                        "team_abbrev": str(r.get("TEAM_ABBREVIATION", "")),
                        "q1": int(r.get("PTS_QTR1", 0) or 0),
                        "q2": int(r.get("PTS_QTR2", 0) or 0),
                        "q3": int(r.get("PTS_QTR3", 0) or 0),
                        "q4": int(r.get("PTS_QTR4", 0) or 0),
                        "total": int(r.get("PTS", 0) or 0),
                    }
                )
            rows.sort(
                key=lambda x: (0 if str(x.get("team_abbrev")) == SAS_ABBREV else 1)
            )
            return rows
    except Exception:
        pass

    return None


def get_game_line_score(conn: sqlite3.Connection, game_id: str) -> dict | None:
    """Return quarter lines from SQLite, or None if missing / not refreshed."""
    gid = str(game_id).strip()
    if gid.isdigit():
        gid = gid.zfill(10)
    cur = conn.execute(
        """
        SELECT spurs_q1, spurs_q2, spurs_q3, spurs_q4,
               opp_q1, opp_q2, opp_q3, opp_q4,
               spurs_final, opp_final, opp_abbrev
        FROM game_line_score WHERE game_id = ?
        """,
        (gid,),
    )
    row = cur.fetchone()
    if not row:
        return None
    out = {
        "spurs_q1": int(row[0]),
        "spurs_q2": int(row[1]),
        "spurs_q3": int(row[2]),
        "spurs_q4": int(row[3]),
        "opp_q1": int(row[4]),
        "opp_q2": int(row[5]),
        "opp_q3": int(row[6]),
        "opp_q4": int(row[7]),
        "spurs_final": int(row[8]) if row[8] is not None else None,
        "opp_final": int(row[9]) if row[9] is not None else None,
        "opp_abbrev": str(row[10] or "OPP"),
    }
    return out


def game_line_score_markdown(ls: dict) -> str:
    """
    Markdown table: Q1–Q4 are regulation quarters only.
    OT = all overtime points (final minus regulation sum). Final = full game score from API.
    """
    oa = str(ls.get("opp_abbrev") or "OPP")
    sq = [ls["spurs_q1"], ls["spurs_q2"], ls["spurs_q3"], ls["spurs_q4"]]
    oq = [ls["opp_q1"], ls["opp_q2"], ls["opp_q3"], ls["opp_q4"]]
    reg_s, reg_o = sum(sq), sum(oq)
    sf = ls.get("spurs_final")
    of = ls.get("opp_final")
    if sf is None:
        sf = reg_s
    if of is None:
        of = reg_o
    ot_s = max(0, int(sf) - reg_s)
    ot_o = max(0, int(of) - reg_o)
    # Show OT column only when at least one team had OT scoring
    show_ot = ot_s > 0 or ot_o > 0
    ot_cell_s = str(ot_s) if show_ot else "—"
    ot_cell_o = str(ot_o) if show_ot else "—"
    if show_ot:
        return (
            "| Team | Q1 | Q2 | Q3 | Q4 | OT | Final |\n"
            "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
            f"| SAS | {sq[0]} | {sq[1]} | {sq[2]} | {sq[3]} | {ot_cell_s} | {sf} |\n"
            f"| {oa} | {oq[0]} | {oq[1]} | {oq[2]} | {oq[3]} | {ot_cell_o} | {of} |\n"
        )
    return (
        "| Team | Q1 | Q2 | Q3 | Q4 | Final |\n"
        "| :--- | ---: | ---: | ---: | ---: | ---: |\n"
        f"| SAS | {sq[0]} | {sq[1]} | {sq[2]} | {sq[3]} | {sf} |\n"
        f"| {oa} | {oq[0]} | {oq[1]} | {oq[2]} | {oq[3]} | {of} |\n"
    )


def set_loaded_season_metadata(
    conn: sqlite3.Connection, *, nba_season: str, season_type: str
) -> None:
    """Record which NBA season the current player_game rows belong to (call after refresh)."""
    conn.execute("DELETE FROM db_meta")
    conn.executemany(
        "INSERT INTO db_meta (key, value) VALUES (?, ?)",
        (
            ("nba_season", nba_season),
            ("season_type", season_type),
        ),
    )
    conn.commit()


def get_loaded_nba_season(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute(
        "SELECT value FROM db_meta WHERE key = 'nba_season' LIMIT 1"
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def get_loaded_season_type(conn: sqlite3.Connection) -> str | None:
    cur = conn.execute(
        "SELECT value FROM db_meta WHERE key = 'season_type' LIMIT 1"
    )
    row = cur.fetchone()
    return str(row[0]) if row else None


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    ensure_schema(conn)
    return conn


def refresh_from_api(
    conn: sqlite3.Connection,
    *,
    season: str | None = None,
    season_type: str = "Regular Season",
    delay_sec: float = 0.35,
) -> int:
    """
    Clear ``player_game`` and ``game_line_score``, then reload ALL Spurs games for one NBA season.

    For each game: SAS player lines from BoxScoreTraditionalV3 (with per-game retries), then team Q1–Q4 scoring from
    BoxScoreSummaryV3/V2 into ``game_line_score`` (one extra API request per game).

    Failures are summarized on stderr; a second pass retries any game that failed the first time.

    Parameters
    ----------
    season
        NBA season id (e.g. ``2025-26``). Default: :func:`current_nba_season_id`.

    Returns
    -------
    int
        Number of **player_game** rows inserted.
    """
    if season is None:
        season = current_nba_season_id()

    team_id = _spurs_team_id()
    finder = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        season_nullable=season,
        season_type_nullable=season_type,
    )
    games_df = finder.get_data_frames()[0]
    if games_df.empty:
        return 0

    if "GAME_DATE" in games_df.columns:
        games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"], errors="coerce")
        games_df = games_df.dropna(subset=["GAME_DATE"])

    spurs_rows = games_df[games_df["TEAM_ID"] == team_id].sort_values("GAME_DATE", ascending=False)
    seen: set[str] = set()
    game_meta: list[dict] = []
    for _, r in spurs_rows.iterrows():
        gid = str(int(r["GAME_ID"])).zfill(10)
        if gid in seen:
            continue
        seen.add(gid)
        game_meta.append(
            {
                "game_id": gid,
                "game_date": str(r["GAME_DATE"].date()) if hasattr(r["GAME_DATE"], "date") else str(r["GAME_DATE"]),
                "matchup": str(r.get("MATCHUP", "")),
                "wl": str(r.get("WL", "")),
            }
        )
    conn.execute("DELETE FROM player_game")
    conn.execute("DELETE FROM game_line_score")
    conn.commit()
    inserted = 0
    expected_games = len(game_meta)
    failed_games: list[tuple[str, str]] = []
    retry_delay = max(0.25, float(delay_sec))

    def _load_one_game(meta: dict) -> None:
        nonlocal inserted
        gid = meta["game_id"]
        frames, err = _boxscore_traditional_frames(
            gid, retries=3, retry_delay_sec=retry_delay
        )
        if frames is None:
            failed_games.append((gid, err or "box score unavailable"))
            return
        df = frames[0]
        sas = df[df["teamTricode"].astype(str) == SAS_ABBREV]
        if sas.empty:
            failed_games.append((gid, "no SAS rows in box score"))
            return
        try:
            for _, row in sas.iterrows():
                name = str(row.get("nameI", "")).strip()
                if not name:
                    fn = str(row.get("firstName", "") or "")
                    ln = str(row.get("familyName", "") or "")
                    name = f"{fn} {ln}".strip()
                mins = row.get("minutes", "")
                conn.execute(
                    """
                    INSERT INTO player_game (
                        game_id, game_date, matchup, wl, team, player_name,
                        min, pts, reb, ast, stl, blk, turnovers, plus_minus, nba_season
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        gid,
                        meta["game_date"],
                        meta["matchup"],
                        meta["wl"],
                        SAS_ABBREV,
                        name,
                        str(mins) if mins is not None else "",
                        int(row.get("points", 0) or 0),
                        int(row.get("reboundsTotal", 0) or 0),
                        int(row.get("assists", 0) or 0),
                        int(row.get("steals", 0) or 0),
                        int(row.get("blocks", 0) or 0),
                        int(row.get("turnovers", 0) or 0),
                        int(row.get("plusMinusPoints", 0) or 0),
                        season,
                    ),
                )
                inserted += 1
            try:
                ls_rows = line_scores_from_api(gid)
                if ls_rows and len(ls_rows) >= 2:
                    sas_row = ls_rows[0]
                    opp_row = ls_rows[1]
                    if str(sas_row.get("team_abbrev")) != SAS_ABBREV:
                        sas_row, opp_row = opp_row, sas_row
                    conn.execute(
                        """
                        INSERT OR REPLACE INTO game_line_score (
                            game_id, spurs_q1, spurs_q2, spurs_q3, spurs_q4,
                            opp_q1, opp_q2, opp_q3, opp_q4,
                            spurs_final, opp_final, opp_abbrev, nba_season
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            gid,
                            int(sas_row["q1"]),
                            int(sas_row["q2"]),
                            int(sas_row["q3"]),
                            int(sas_row["q4"]),
                            int(opp_row["q1"]),
                            int(opp_row["q2"]),
                            int(opp_row["q3"]),
                            int(opp_row["q4"]),
                            int(sas_row.get("total", 0) or 0),
                            int(opp_row.get("total", 0) or 0),
                            str(opp_row.get("team_abbrev") or "")[:12],
                            season,
                        ),
                    )
            except Exception:
                pass
        except Exception as e:
            failed_games.append((gid, f"{type(e).__name__}: {e}"))

    for meta in game_meta:
        _load_one_game(meta)
        if delay_sec > 0:
            time.sleep(delay_sec)

    retry_ids = {g for g, _ in failed_games}
    if retry_ids:
        print(
            f"spurs_season_store: retrying {len(retry_ids)} game(s) after box-score failures...",
            file=sys.stderr,
        )
        failed_games.clear()
        for meta in game_meta:
            if meta["game_id"] in retry_ids:
                _load_one_game(meta)
                if delay_sec > 0:
                    time.sleep(delay_sec)

    if failed_games:
        for gid, reason in failed_games[:20]:
            print(
                f"spurs_season_store: skip game_id={gid}: {reason}",
                file=sys.stderr,
            )
        if len(failed_games) > 20:
            print(
                f"spurs_season_store: ... and {len(failed_games) - 20} more failures",
                file=sys.stderr,
            )
        ok = expected_games - len(failed_games)
        print(
            f"spurs_season_store: loaded {ok}/{expected_games} games "
            f"({inserted} player_game rows). Re-run --refresh if needed.",
            file=sys.stderr,
        )
    else:
        print(
            f"spurs_season_store: loaded all {expected_games} games ({inserted} player_game rows).",
            file=sys.stderr,
        )

    set_loaded_season_metadata(
        conn, nba_season=season, season_type=season_type
    )
    conn.commit()
    return inserted


def _search_tokens(query: str) -> list[str]:
    """Split query into meaningful tokens (so 'Wembanyama scoring' still finds V. Wembanyama)."""
    raw = query.strip()
    if not raw:
        return []
    # Alphanumeric tokens only (keeps Wembanyama, SAS, 2026, etc.)
    tokens = re.findall(r"[A-Za-z0-9]+", raw)
    stop = {
        "a",
        "an",
        "the",
        "and",
        "or",
        "for",
        "with",
        "how",
        "has",
        "have",
        "been",
        "his",
        "her",
        "their",
        "this",
        "that",
        "from",
        "into",
        "about",
        "what",
        "when",
        "who",
        "did",
        "does",
        "is",
        "are",
        "was",
        "were",
        "go",
        "gone",
        "season",
        "stats",
        "stat",
        "line",
        "lines",
        "game",
        "games",
        "spurs",
        "san",
        "antonio",
        # Natural-language fluff; rows are numeric box lines, not prose
        "scoring",
        "points",
        "rebounds",
        "assists",
        "steals",
        "blocks",
        "turnovers",
        "minutes",
        "play",
        "playing",
        "performance",
        "breakdown",
    }
    out = [t for t in tokens if len(t) >= 2 and t.lower() not in stop]
    return out if out else tokens


def _nba_season_filter_sql(nba_season: str | None) -> tuple[str, tuple]:
    """SQL fragment and params matching :func:`search_player_games` season behavior."""
    if nba_season is None:
        return "", ()
    return " AND (nba_season IS NULL OR nba_season = ?)", (nba_season,)


_SELECT_PLAYER_GAME = """
    SELECT game_date, matchup, wl, team, player_name, min, pts, reb, ast, stl, blk, turnovers, plus_minus, game_id, nba_season
    FROM player_game
"""


def player_games_in_calendar_month(
    conn: sqlite3.Connection,
    *,
    year: int,
    month: int,
    player_name_substr: str | None = None,
    nba_season: str | None = None,
    limit: int = 10_000,
) -> pd.DataFrame:
    """
    Rows with ``game_date`` in the given calendar month (inclusive), ISO ``YYYY-MM-DD``.

    Optionally filter to lines whose ``player_name`` contains ``player_name_substr``
    (case-sensitive substring; callers often pass a last name).
    """
    _last = monthrange(year, month)[1]
    date_start = date(year, month, 1).isoformat()
    date_end = date(year, month, _last).isoformat()
    return player_games_in_date_range(
        conn,
        date_start=date_start,
        date_end=date_end,
        player_name_substr=player_name_substr,
        nba_season=nba_season,
        limit=limit,
    )


def player_games_in_date_range(
    conn: sqlite3.Connection,
    *,
    date_start: str,
    date_end: str,
    player_name_substr: str | None = None,
    nba_season: str | None = None,
    limit: int = 10_000,
) -> pd.DataFrame:
    """
    Rows with ``game_date`` between ``date_start`` and ``date_end`` (inclusive), as strings.

    Parameters match SQLite ``TEXT`` ISO dates so lexicographic order equals chronological.
    """
    season_sql, season_params = _nba_season_filter_sql(nba_season)
    player_sql = ""
    params: list = [date_start, date_end]
    if player_name_substr is not None and str(player_name_substr).strip():
        player_sql = " AND player_name LIKE ?"
        params.append(f"%{player_name_substr.strip()}%")
    params.extend(season_params)
    params.append(limit)
    sql = f"""
        {_SELECT_PLAYER_GAME.strip()}
        WHERE game_date >= ? AND game_date <= ?{player_sql}{season_sql}
        ORDER BY game_date DESC, player_name ASC
        LIMIT ?
    """
    return pd.read_sql_query(sql, conn, params=tuple(params))


def latest_game_date(
    conn: sqlite3.Connection, *, nba_season: str | None = None
) -> str | None:
    """Latest ``game_date`` in the store (``TEXT`` ISO), or ``None`` if empty."""
    season_sql, season_params = _nba_season_filter_sql(nba_season)
    sql = f"SELECT MAX(game_date) FROM player_game WHERE game_date IS NOT NULL{season_sql}"
    cur = conn.execute(sql, season_params)
    row = cur.fetchone()
    if not row or row[0] is None:
        return None
    return str(row[0])


def rows_for_game_id(
    conn: sqlite3.Connection,
    game_id: str,
    *,
    nba_season: str | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    All player lines for a single ``game_id`` (Spurs rows only in this DB).

    ``game_id`` is normalized to a 10-digit string when numeric.
    """
    gid = str(game_id).strip()
    if gid.isdigit():
        gid = gid.zfill(10)
    season_sql, season_params = _nba_season_filter_sql(nba_season)
    params: list = [gid]
    params.extend(season_params)
    params.append(limit)
    sql = f"""
        {_SELECT_PLAYER_GAME.strip()}
        WHERE game_id = ?{season_sql}
        ORDER BY player_name ASC
        LIMIT ?
    """
    return pd.read_sql_query(sql, conn, params=tuple(params))


def rows_for_game_on_date(
    conn: sqlite3.Connection,
    game_date: str,
    *,
    nba_season: str | None = None,
    limit: int = 500,
) -> pd.DataFrame:
    """
    All rows for ``game_date`` exactly (``TEXT`` ISO ``YYYY-MM-DD``).

    The Spurs typically have at most one game per calendar day; if multiple ``game_id``
    values exist, all matching rows are returned up to ``limit``.
    """
    d = str(game_date).strip()
    season_sql, season_params = _nba_season_filter_sql(nba_season)
    params: list = [d]
    params.extend(season_params)
    params.append(limit)
    sql = f"""
        {_SELECT_PLAYER_GAME.strip()}
        WHERE game_date = ?{season_sql}
        ORDER BY game_id ASC, player_name ASC
        LIMIT ?
    """
    return pd.read_sql_query(sql, conn, params=tuple(params))


def search_player_games(
    conn: sqlite3.Connection,
    query: str,
    *,
    limit: int = 40,
    nba_season: str | None = None,
) -> pd.DataFrame:
    """
    LIKE search across player_name, matchup, game_date, wl.
    Uses OR across query tokens so 'Wembanyama scoring' matches player_name LIKE '%Wembanyama%'.

    If ``nba_season`` is set (e.g. ``2025-26``), restrict to that NBA season; rows with NULL
    ``nba_season`` (legacy DBs) are still included so old databases keep working until refreshed.
    """
    season_sql = ""
    season_param: tuple = ()
    if nba_season is not None:
        season_sql = " AND (nba_season IS NULL OR nba_season = ?)"
        season_param = (nba_season,)

    tokens = _expand_tokens_with_opponent_nicknames(_search_tokens(query))
    cols_clause = "(player_name LIKE ? OR matchup LIKE ? OR game_date LIKE ? OR wl LIKE ?)"

    if not tokens:
        q = f"%{query.strip()}%"
        sql = f"""
            SELECT game_date, matchup, wl, team, player_name, min, pts, reb, ast, stl, blk, turnovers, plus_minus, game_id, nba_season
            FROM player_game
            WHERE {cols_clause}{season_sql}
            ORDER BY game_date DESC
            LIMIT ?
        """
        return pd.read_sql_query(
            sql, conn, params=(q, q, q, q) + season_param + (limit,)
        )

    or_parts = " OR ".join(cols_clause for _ in tokens)
    sql = f"""
        SELECT game_date, matchup, wl, team, player_name, min, pts, reb, ast, stl, blk, turnovers, plus_minus, game_id, nba_season
        FROM player_game
        WHERE ({or_parts}){season_sql}
        ORDER BY game_date DESC
        LIMIT ?
    """
    params: list = []
    for t in tokens:
        p = f"%{t}%"
        params.extend([p, p, p, p])
    params.extend(list(season_param))
    params.append(limit)
    return pd.read_sql_query(sql, conn, params=params)


def player_games_for_opponent_matchup(
    conn: sqlite3.Connection,
    opponent: str,
    *,
    nba_season: str | None = None,
    limit: int = 10_000,
) -> pd.DataFrame:
    """
    Spurs player rows where ``matchup`` includes the opponent tricode (e.g. OKC).

    ``opponent`` may be a nickname or tricode; see :func:`resolve_opponent_tricode`.
    """
    code = resolve_opponent_tricode(opponent)
    if not code:
        return pd.DataFrame()
    season_sql, season_params = _nba_season_filter_sql(nba_season)
    pat = f"%{code}%"
    params: list = [pat]
    params.extend(season_params)
    params.append(limit)
    sql = f"""
        {_SELECT_PLAYER_GAME.strip()}
        WHERE matchup LIKE ?{season_sql}
        ORDER BY game_date DESC, player_name ASC
        LIMIT ?
    """
    return pd.read_sql_query(sql, conn, params=tuple(params))


def row_count(conn: sqlite3.Connection) -> int:
    cur = conn.execute("SELECT COUNT(*) FROM player_game")
    return int(cur.fetchone()[0])


def row_count_for_nba_season(conn: sqlite3.Connection, nba_season: str | None) -> int:
    """Row count for rows tagged as ``nba_season`` (or NULL legacy rows)."""
    if nba_season is None:
        return row_count(conn)
    cur = conn.execute(
        "SELECT COUNT(*) FROM player_game WHERE nba_season IS NULL OR nba_season = ?",
        (nba_season,),
    )
    return int(cur.fetchone()[0])
