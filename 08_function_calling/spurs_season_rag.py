#!/usr/bin/env python3
"""
Spurs season RAG: SQLite player-game lines + Ollama breakdown.

Does not import or modify 06_agents (v1 Spurs game reporter).

Usage
-----
  cd 08_function_calling
  pip install -r requirements_spurs_rag.txt
  python spurs_season_rag.py --refresh    # populate DB for current NBA season (needs network)
  python spurs_season_rag.py "Wembanyama scoring"   # RAG query

Environment
-----------
  OLLAMA model: set MODEL in this file or pass --model
"""

from __future__ import annotations

import argparse
import json
import os
import sys

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

from functions import agent_run

from spurs_season_store import (
    connect,
    current_nba_season_id,
    refresh_from_api,
    row_count,
    search_player_games,
)
from spurs_stats import (
    _is_consistent_with_precomputed,
    _pick_focus_player,
    _precomputed_sentence,
    build_task,
    compute_precomputed_stats,
)

DEFAULT_DB = os.path.join(_SCRIPT_DIR, "data", "spurs_season.db")
DEFAULT_MODEL = "llama3.2"


def main() -> None:
    parser = argparse.ArgumentParser(description="Spurs season stats RAG (SQLite + Ollama).")
    parser.add_argument(
        "query",
        nargs="?",
        default="",
        help="Natural-language question about a Spurs player's season (run after --refresh).",
    )
    parser.add_argument("--refresh", action="store_true", help="Fetch Spurs games for one NBA season into SQLite.")
    parser.add_argument(
        "--season",
        default=None,
        metavar="YYYY-YY",
        help=(
            "NBA season to load on --refresh (default: current season from the calendar)."
        ),
    )
    parser.add_argument(
        "--season-type",
        default="Regular Season",
        help="Season type for --refresh (default: Regular Season).",
    )
    parser.add_argument(
        "--search-limit",
        type=int,
        default=40,
        help="Max rows returned from SQLite for the LLM (default 40).",
    )
    parser.add_argument("--db", default=DEFAULT_DB, help="Path to SQLite database.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Ollama model name.")
    args = parser.parse_args()

    refresh_season = (
        args.season if args.season is not None else current_nba_season_id()
    )

    conn = connect(args.db)

    if args.refresh:
        print(
            f"Refreshing Spurs player lines for season {refresh_season} ({args.season_type}) into {args.db} …"
        )
        n = refresh_from_api(conn, season=refresh_season, season_type=args.season_type)
        print(f"Inserted {n} player-game rows. Total rows: {row_count(conn)}.")
        conn.close()
        if not args.query.strip():
            return

    if not args.query.strip():
        print("Provide a query or use --refresh only. Example: python spurs_season_rag.py 'Fox assists'")
        conn.close()
        sys.exit(1)

    if row_count(conn) == 0:
        cs = current_nba_season_id()
        print(
            "Database is empty. Run: "
            f"python spurs_season_rag.py --refresh --season {cs}"
        )
        conn.close()
        sys.exit(1)

    df = search_player_games(conn, args.query, limit=args.search_limit)
    conn.close()

    if df.empty:
        print("No matching rows in SQLite for that query. Try another keyword (player last name, matchup, date).")
        sys.exit(1)

    records = df.to_dict(orient="records")
    player_names = sorted({str(r.get("player_name", "")) for r in records if r.get("player_name")})

    role = (
        "You are a Spurs season analyst. You receive JSON with a user_query and retrieved_games: "
        "rows of San Antonio Spurs player box-score lines from real NBA games. "
        "Write a concise breakdown answering the user_query using ONLY those rows. "
        "For aggregate numbers (games played, records, averages, totals), you MUST use "
        "precomputed_stats exactly as provided and must not recalculate them. "
        "If the data is thin or ambiguous, say so. "
        "Use only the exact player names from the allowed list or the JSON; never expand initials "
        "to full first names. Do not invent games, stats, opponents, or percentages not present in the JSON."
    )

    precomputed_stats = compute_precomputed_stats(records)
    task = build_task(args.query, records, player_names, precomputed_stats)
    print("\n--- Retrieved rows (preview) ---\n")
    print(df.head(8).to_string(index=False))
    print(f"\n… sending {len(records)} rows to model {args.model}\n")

    focus_player = _pick_focus_player(args.query, player_names)
    precomputed_line = _precomputed_sentence(precomputed_stats, focus_player)
    out = agent_run(role=role, task=task, model=args.model, output="text")
    if not _is_consistent_with_precomputed(out, precomputed_stats, focus_player):
        print("! Consistency check failed (aggregate drift). Re-generating with strict lock on precomputed stats...")
        pstats = precomputed_stats.get("per_player", {}).get(focus_player or "", {})
        strict_role = (
            role
            + " FINAL CHECK: Your response must explicitly include '<games> games' using the exact precomputed value "
              "for the focus player and must not include any conflicting game-count number."
        )
        strict_task = (
            task
            + f"\n\nFOCUS PLAYER: {focus_player or '(none)'}"
            + f"\nFOCUS PLAYER REQUIRED GAMES VALUE: {pstats.get('games', 'N/A')}"
        )
        out = agent_run(role=strict_role, task=strict_task, model=args.model, output="text")
    print("--- Spurs season breakdown ---\n")
    if precomputed_line:
        print(f"(Precomputed averages) {precomputed_line}\n")
    print(out)


if __name__ == "__main__":
    main()
