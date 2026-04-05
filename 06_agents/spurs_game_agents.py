# spurs_game_agents.py
# Two-agent chain: fetch most recent San Antonio Spurs game,
# Agent 1: technical summary (data only). Agent 2: reporter-style recap (prose).
# If the most recent game has no box score, show a team-only summary and
# then the full breakdown for the most recent game that does have box score.

import os
from pathlib import Path

import pandas as pd

# Set working directory to this script's folder for consistent imports
os.chdir(Path(__file__).resolve().parent)

from functions import agent_run
from spurs_utils import (
    get_most_recent_spurs_game,
    get_recent_spurs_games,
    get_spurs_boxscore,
    spurs_data_as_text,
)

# Ollama model to use for both agents.
MODEL = "llama3"


def _team_only_summary(game_info, model):
    """Three-sentence team summary when no player data is available."""
    task = (
        f"Date: {game_info.get('game_date', 'N/A')}. "
        f"Matchup: {game_info.get('matchup', 'N/A')}. "
        f"Result: {game_info.get('wl', 'N/A')}. "
        f"Spurs {game_info.get('pts', 'N/A')}, Opponent {game_info.get('opponent_pts', 'N/A')}."
    )
    role = (
        "You provide a team-only summary with no player data. "
        "State clearly that this is only a team summary and that no player box score is available. "
        "Then write exactly three sentences summarizing the game outcome and team-level result. "
        "Do not invent player names or stats."
    )
    return agent_run(role=role, task=task, model=model, output="text")


def _full_recap_for_game(game_info, box_df, model):
    """Run Agent 1 + Agent 2 and return (summary, recap) for one game."""
    raw_text = spurs_data_as_text(game_info, box_df)
    role1 = (
        "I am an NBA data analyst. I produce a technical summary only: facts and numbers "
        "from the provided box score and score-by-quarter for ONE San Antonio Spurs game. "
        "Output a structured brief: final score, quarter-by-quarter score progression, "
        "and—when provided—the Notable game stats (biggest lead, biggest scoring run, "
        "lead changes, times tied). You must present the full stat line for every player "
        "from both teams who played in a table. The table must include the team each "
        "player is on (TEAM) and MIN, PTS, REB, AST, STL, BLK, TO. Report only what "
        "appears in the data. Do not infer or invent runs, shutouts, or other in-game "
        "sequences. No narrative or opinion—just the data distilled. Use only the exact "
        "player names as in the data (e.g. 'V. Wembanyama', 'D. Vassell'); do not expand "
        "initials or invent first names."
    )
    summary = agent_run(role=role1, task=raw_text, model=model, output="text")
    # Append canonical player names so Agent 2 has one source of truth—reduces first-name hallucination
    if not box_df.empty and "PLAYER_NAME" in box_df.columns:
        names = box_df["PLAYER_NAME"].dropna().astype(str).unique().tolist()
        summary = summary + "\n\n---\nAllowed player names (use these exact forms only; never expand to full first names like Victor or Devin): " + ", ".join(names)
    role2 = (
        "CRITICAL: Use only the exact player names from the 'Allowed player names' list or "
        "the summary—never expand initials to full first names (e.g. write 'V. Wembanyama' "
        "not 'Victor Wembanyama'). I am the Spurs reporter agent: an honest Spurs fan. I "
        "take a technical game summary and write a single narrative paragraph—one flowing "
        "recap, no sections or headings. Write like a real article lede: who won, how the "
        "game unfolded, who shined. Root for the Spurs but be honest—do not distort the "
        "game or overstate their dominance. Include at least one statement summarizing "
        "the flow of the game using the quarter-by-quarter score (e.g. who led when, how "
        "the score changed by quarter). Include at least one reference to an opposing "
        "player (by name from the summary). Do not contradict the score progression: if "
        "the opponent had their best quarter or a near comeback, do not describe it as "
        "the Spurs holding them or stifling defense in that quarter—stay consistent with "
        "the numbers. Do not add specific details that are not in the technical summary "
        "(e.g. exact runs, shutout lengths, or play-by-play moments). Only dramatize or "
        "rephrase what the summary states."
    )
    recap = agent_run(role=role2, task=summary, model=model, output="text")
    return summary, recap


def main():
    try:
        game_info = get_most_recent_spurs_game()
    except Exception as e:
        print(f"Failed to fetch Spurs games (check network / nba_api): {e}")
        return

    if not game_info:
        print("No recent San Antonio Spurs game found.")
        return

    game_id = game_info["game_id"]
    try:
        box_df = get_spurs_boxscore(game_id)
    except Exception as e:
        print(f"Failed to fetch box score for game {game_id}: {e}")
        box_df = pd.DataFrame()

    if not box_df.empty:
        # Most recent game has player data: full flow only
        summary, recap = _full_recap_for_game(game_info, box_df, MODEL)
        print("\n--- Agent 1 (technical summary) ---\n")
        print(summary)
        print("\n--- Spurs reporter agent (recap) ---\n")
        print(recap)
        return

    # No player data for most recent game: team summary + full breakdown for latest game with box
    print("\n--- Team summary (no player data available for most recent game) ---\n")
    print("This summary is team-only; no player box score is available for this game.\n")
    team_summary = _team_only_summary(game_info, MODEL)
    print(team_summary)

    # Find most recent game that returns a non-empty box score (search back through Dec 2025 and earlier)
    recent = get_recent_spurs_games(limit=80)
    print(f"\n[DEBUG] get_recent_spurs_games(80) returned {len(recent)} game(s).")
    fallback_info = None
    fallback_box = pd.DataFrame()
    for i, g in enumerate(recent):
        if g["game_id"] == game_id:
            print(f"[DEBUG] Skipping game {i+1}: {g['game_id']} ({g.get('game_date')} {g.get('matchup')}) — most recent, no box.")
            continue
        try:
            b = get_spurs_boxscore(g["game_id"])
            n = len(b)
            status = "found" if n else "empty"
            print(f"[DEBUG] Game {i+1}: {g['game_id']} ({g.get('game_date')} {g.get('matchup')}) — box score rows: {n} ({status}).")
            if not b.empty:
                fallback_info = g
                fallback_box = b
                break
        except Exception as e:
            print(f"[DEBUG] Game {i+1}: {g['game_id']} ({g.get('game_date')} {g.get('matchup')}) — error: {e}.")
            continue

    if fallback_info is None or fallback_box.empty:
        print("\nNo other recent game with player box score data was found.")
        return

    print("\n--- Full breakdown (most recent game with player data) ---\n")
    print(f"Game: {fallback_info.get('game_date')} — {fallback_info.get('matchup')}\n")
    _, recap = _full_recap_for_game(fallback_info, fallback_box, MODEL)
    print(recap)


if __name__ == "__main__":
    main()
