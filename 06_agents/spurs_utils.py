# spurs_utils.py
# Helpers for fetching San Antonio Spurs game data via nba_api.
# Used by spurs_game_agents.py for the two-agent recap chain.

from datetime import datetime

import pandas as pd
from nba_api.stats.static import teams
from nba_api.stats.endpoints import leaguegamefinder
from nba_api.stats.endpoints import boxscoretraditionalv2
from nba_api.stats.endpoints import boxscoretraditionalv3
from nba_api.stats.endpoints import boxscoresummaryv2
from nba_api.stats.endpoints import boxscoresummaryv3


# Spurs team abbreviation and ID
SAS_ABBREV = "SAS"


def _get_spurs_team_id():
    """Return the NBA API team ID for the San Antonio Spurs."""
    nba_teams = teams.get_teams()
    spurs = [t for t in nba_teams if t["abbreviation"] == SAS_ABBREV]
    if not spurs:
        raise ValueError("San Antonio Spurs (SAS) not found in nba_api teams.")
    return spurs[0]["id"]


def get_most_recent_spurs_game():
    """
    Fetch the most recent completed game for the San Antonio Spurs.

    Returns
    -------
    dict
        Keys: game_id, game_date, matchup, wl (Win/Loss), pts (Spurs pts),
        opponent_pts (optional), opponent_name (optional).
    """
    team_id = _get_spurs_team_id()
    # Request games through today so we include the very latest (e.g. yesterday)
    today = datetime.now().strftime("%m/%d/%Y")
    finder = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        date_to_nullable=today,
    )
    games_df = finder.get_data_frames()[0]

    if games_df.empty:
        return None

    # Ensure GAME_DATE is a proper datetime so we sort by real date
    if "GAME_DATE" in games_df.columns:
        games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"], errors="coerce")
        # Drop rows with missing date so they don't end up "first"
        games_df = games_df.dropna(subset=["GAME_DATE"])

    if games_df.empty:
        return None

    # Take the single most recent game by date (no season filter)
    games_df = games_df.sort_values("GAME_DATE", ascending=False).reset_index(drop=True)

    row = games_df.iloc[0]

    game_id = row["GAME_ID"]
    game_date = row["GAME_DATE"]
    matchup = row["MATCHUP"]
    wl = row["WL"]
    pts = int(row["PTS"])

    # Get opponent score: same GAME_ID, other row
    same_game = games_df[games_df["GAME_ID"] == game_id]
    if len(same_game) >= 2:
        other = same_game[same_game["TEAM_ID"] != team_id].iloc[0]
        opponent_pts = int(other["PTS"])
        opponent_name = other.get("MATCHUP", "").replace("vs. ", "").replace("@ ", "").strip()
    else:
        opponent_pts = None
        opponent_name = None

    # Box score endpoint expects a 10-digit game_id (e.g. 0022400123)
    game_id_str = str(int(game_id)).zfill(10)

    return {
        "game_id": game_id_str,
        "game_date": game_date,
        "matchup": matchup,
        "wl": wl,
        "pts": pts,
        "opponent_pts": opponent_pts,
        "opponent_name": opponent_name,
    }


def _game_info_from_row(games_df, team_id, row):
    """Build one game_info dict from a Spurs row and same-game opponent row."""
    game_id = row["GAME_ID"]
    game_id_str = str(int(game_id)).zfill(10)
    same_game = games_df[games_df["GAME_ID"] == game_id]
    other = same_game[same_game["TEAM_ID"] != team_id]
    opponent_pts = int(other.iloc[0]["PTS"]) if len(other) else None
    opponent_name = (
        other.iloc[0].get("MATCHUP", "").replace("vs. ", "").replace("@ ", "").strip()
        if len(other) else None
    )
    return {
        "game_id": game_id_str,
        "game_date": row["GAME_DATE"],
        "matchup": row["MATCHUP"],
        "wl": row["WL"],
        "pts": int(row["PTS"]),
        "opponent_pts": opponent_pts,
        "opponent_name": opponent_name,
    }


def get_recent_spurs_games(limit=15):
    """
    Fetch the most recent completed games for the San Antonio Spurs, most recent first.

    Returns
    -------
    list of dict
        Each dict has keys game_id, game_date, matchup, wl, pts, opponent_pts, opponent_name.
    """
    team_id = _get_spurs_team_id()
    today = datetime.now().strftime("%m/%d/%Y")
    finder = leaguegamefinder.LeagueGameFinder(
        team_id_nullable=team_id,
        date_to_nullable=today,
    )
    games_df = finder.get_data_frames()[0]
    if games_df.empty:
        return []
    if "GAME_DATE" in games_df.columns:
        games_df["GAME_DATE"] = pd.to_datetime(games_df["GAME_DATE"], errors="coerce")
        games_df = games_df.dropna(subset=["GAME_DATE"])
    games_df = games_df.sort_values("GAME_DATE", ascending=False).reset_index(drop=True)
    # One row per game (Spurs side only)
    spurs_rows = games_df[games_df["TEAM_ID"] == team_id]
    seen_ids = set()
    result = []
    for _, row in spurs_rows.iterrows():
        gid = row["GAME_ID"]
        if gid in seen_ids:
            continue
        seen_ids.add(gid)
        result.append(_game_info_from_row(games_df, team_id, row))
        if len(result) >= limit:
            break
    return result


def get_spurs_boxscore(game_id):
    """
    Fetch traditional box score for a game. Tries V3 first (has data for
    recent 2025-26 games); falls back to V2 for older games.

    Parameters
    ----------
    game_id : str or int
        NBA API game ID (e.g. from get_most_recent_spurs_game). Normalized to
        10-digit string for the API.

    Returns
    -------
    pandas.DataFrame
        Player box score (one row per player) with PLAYER_NAME, MIN, PTS, REB, AST, etc.
    """
    game_id_10 = str(int(game_id)).zfill(10)

    # V3 returns data for recent games (e.g. 2025-26) with full-game params
    try:
        box_v3 = boxscoretraditionalv3.BoxScoreTraditionalV3(
            game_id=game_id_10,
            start_period=0,
            end_period=14,
            start_range=0,
            end_range=0,
            range_type=0,
        )
        frames_v3 = box_v3.get_data_frames()
        if frames_v3 and len(frames_v3[0]) > 0:
            df = frames_v3[0].copy()
            # Map V3 columns to V2-style names so spurs_data_as_text works
            if "nameI" in df.columns:
                df["PLAYER_NAME"] = df["nameI"].astype(str)
            else:
                df["PLAYER_NAME"] = (df["firstName"].fillna("") + " " + df["familyName"].fillna("")).str.strip()
            df["MIN"] = df.get("minutes", "")
            df["PTS"] = df.get("points", 0)
            df["REB"] = df.get("reboundsTotal", 0)
            df["AST"] = df.get("assists", 0)
            df["STL"] = df.get("steals", 0)
            df["BLK"] = df.get("blocks", 0)
            df["TO"] = df.get("turnovers", 0)
            df["TEAM"] = df.get("teamTricode", "").astype(str)
            return df[["TEAM", "PLAYER_NAME", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO"]]
    except Exception:
        pass

    # Fallback: V2 (works for older seasons / some game_id formats)
    box = boxscoretraditionalv2.BoxScoreTraditionalV2(game_id=game_id_10)
    frames = box.get_data_frames()
    if not frames:
        return pd.DataFrame()
    df = frames[0].copy()
    if "TEAM_ABBREVIATION" in df.columns and "TEAM" not in df.columns:
        df["TEAM"] = df["TEAM_ABBREVIATION"].astype(str)
    return df


def get_spurs_line_score(game_id):
    """
    Fetch quarter-by-quarter (line) score for a game. Tries V3 first, then V2.

    Parameters
    ----------
    game_id : str or int
        NBA API game ID (10-digit string).

    Returns
    -------
    list of dict or None
        Each dict: team_abbrev, q1, q2, q3, q4, total. Optional keys q5+ for OT.
        Spurs row first when available. None if fetch fails or no data.
    """
    game_id_10 = str(int(game_id)).zfill(10)

    # V3: frame index 4 has period1Score, period2Score, period3Score, period4Score, score
    try:
        summary_v3 = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id_10)
        frames = summary_v3.get_data_frames()
        if len(frames) > 4 and not frames[4].empty:
            df = frames[4]
            rows = []
            for _, r in df.iterrows():
                row = {
                    "team_abbrev": r.get("teamTricode", r.get("team_id", "")),
                    "q1": int(r.get("period1Score", 0) or 0),
                    "q2": int(r.get("period2Score", 0) or 0),
                    "q3": int(r.get("period3Score", 0) or 0),
                    "q4": int(r.get("period4Score", 0) or 0),
                    "total": int(r.get("score", 0) or 0),
                }
                rows.append(row)
            # Spurs first
            rows.sort(key=lambda x: (0 if str(x.get("team_abbrev")) == SAS_ABBREV else 1))
            return rows
    except Exception:
        pass

    # V2: frame index 5 has PTS_QTR1, PTS_QTR2, PTS_QTR3, PTS_QTR4, PTS
    try:
        summary_v2 = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id_10)
        frames = summary_v2.get_data_frames()
        if len(frames) > 5 and not frames[5].empty:
            df = frames[5]
            rows = []
            for _, r in df.iterrows():
                row = {
                    "team_abbrev": r.get("TEAM_ABBREVIATION", ""),
                    "q1": int(r.get("PTS_QTR1", 0) or 0),
                    "q2": int(r.get("PTS_QTR2", 0) or 0),
                    "q3": int(r.get("PTS_QTR3", 0) or 0),
                    "q4": int(r.get("PTS_QTR4", 0) or 0),
                    "total": int(r.get("PTS", 0) or 0),
                }
                rows.append(row)
            rows.sort(key=lambda x: (0 if str(x.get("team_abbrev")) == SAS_ABBREV else 1))
            return rows
    except Exception:
        pass

    return None


def get_spurs_extra_stats(game_id):
    """
    Fetch notable game stats (largest lead, lead changes, times tied, biggest run).
    Uses BoxScoreSummaryV3 frame 7; no V2 fallback for run data.

    Parameters
    ----------
    game_id : str or int
        NBA API game ID (10-digit string).

    Returns
    -------
    list of dict or None
        Each dict: team_abbrev, biggest_lead, lead_changes, times_tied, biggest_scoring_run.
        Spurs first when available. None if fetch fails or no data.
    """
    game_id_10 = str(int(game_id)).zfill(10)

    try:
        summary = boxscoresummaryv3.BoxScoreSummaryV3(game_id=game_id_10)
        frames = summary.get_data_frames()
        if len(frames) <= 7 or frames[7].empty:
            return None
        df = frames[7]
        rows = []
        for _, r in df.iterrows():
            row = {
                "team_abbrev": str(r.get("teamTricode", "")),
                "biggest_lead": int(r.get("biggestLead", 0) or 0),
                "lead_changes": int(r.get("leadChanges", 0) or 0),
                "times_tied": int(r.get("timesTied", 0) or 0),
                "biggest_scoring_run": int(r.get("biggestScoringRun", 0) or 0),
            }
            rows.append(row)
        rows.sort(key=lambda x: (0 if str(x.get("team_abbrev")) == SAS_ABBREV else 1))
        return rows
    except Exception:
        pass
    return None


def spurs_data_as_text(game_info, box_df):
    """
    Convert game info and box score into a single text block for the analyst agent.

    Parameters
    ----------
    game_info : dict
        From get_most_recent_spurs_game().
    box_df : pandas.DataFrame
        From get_spurs_boxscore().

    Returns
    -------
    str
        Markdown-style header plus box score table.
    """
    lines = [
        "# San Antonio Spurs – Most Recent Game",
        "",
        f"**Date:** {game_info.get('game_date', 'N/A')}",
        f"**Matchup:** {game_info.get('matchup', 'N/A')}",
        f"**Result:** {game_info.get('wl', 'N/A')}",
        f"**Spurs PTS:** {game_info.get('pts', 'N/A')}",
    ]
    if game_info.get("opponent_pts") is not None:
        lines.append(f"**Opponent PTS:** {game_info['opponent_pts']}")
    if game_info.get("opponent_name"):
        lines.append(f"**Opponent:** {game_info['opponent_name']}")

    # Score by quarter (how the score changed through the game)
    line_score = get_spurs_line_score(game_info.get("game_id", ""))
    if line_score:
        lines.extend(["", "## Score by quarter", ""])
        for row in line_score:
            abbrev = row.get("team_abbrev", "")
            q1, q2, q3, q4 = row.get("q1", 0), row.get("q2", 0), row.get("q3", 0), row.get("q4", 0)
            total = row.get("total", 0)
            lines.append(f"- **{abbrev}:** Q1 {q1}, Q2 {q2}, Q3 {q3}, Q4 {q4} — Total {total}")
        lines.append("")

    # Notable game stats (largest lead, biggest run, etc.) — report only these, do not infer
    extra = get_spurs_extra_stats(game_info.get("game_id", ""))
    if extra:
        lines.extend(["", "## Notable game stats (use only these; do not infer runs or leads)", ""])
        for row in extra:
            abbrev = row.get("team_abbrev", "")
            lead = row.get("biggest_lead", 0)
            changes = row.get("lead_changes", 0)
            tied = row.get("times_tied", 0)
            run = row.get("biggest_scoring_run", 0)
            lines.append(f"- **{abbrev}:** Biggest lead {lead} pts, biggest scoring run {run} pts, lead changes {changes}, times tied {tied}")
        lines.append("")

    lines.extend(["", "## Player box score (traditional)", ""])

    if box_df.empty:
        lines.append("(No player data available.)")
        return "\n".join(lines)

    # Subset to key columns; include team and all players from both teams who played (exclude DNP)
    cols = ["TEAM", "PLAYER_NAME", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TO"]
    use = [c for c in cols if c in box_df.columns]
    if not use:
        use = list(box_df.columns)
    sub = box_df[use].copy()
    if "MIN" in sub.columns:
        min_str = sub["MIN"].astype(str).str.strip()
        sub = sub[(min_str != "") & (min_str != "-")]
    try:
        table = sub.to_markdown(index=False)
    except Exception:
        table = sub.to_string(index=False)
    lines.append(table)
    names = sub["PLAYER_NAME"].astype(str).tolist()
    lines.append("")
    lines.append(f"Use only these exact player names in your analysis: {', '.join(names)}. Do not expand initials or invent first names.")
    return "\n".join(lines)
