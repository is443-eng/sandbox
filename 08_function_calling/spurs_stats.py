# spurs_stats.py
# Deterministic aggregates and RAG helpers for Spurs season tools (used by lab + spurs_season_rag).

from __future__ import annotations

import json
import re


def _to_float(v) -> float:
    try:
        return float(v)
    except Exception:
        return 0.0


def compute_precomputed_stats(records: list[dict]) -> dict:
    """Deterministic aggregates computed in Python to prevent LLM math errors."""
    by_player: dict[str, dict] = {}
    games_set = set()
    for r in records:
        game_id = str(r.get("game_id", ""))
        if game_id:
            games_set.add(game_id)
        name = str(r.get("player_name", "")).strip()
        if not name:
            continue
        if name not in by_player:
            by_player[name] = {
                "games": 0,
                "wins": 0,
                "losses": 0,
                "pts_sum": 0.0,
                "reb_sum": 0.0,
                "ast_sum": 0.0,
                "stl_sum": 0.0,
                "blk_sum": 0.0,
                "turnovers_sum": 0.0,
                "plus_minus_sum": 0.0,
            }
        st = by_player[name]
        st["games"] += 1
        wl = str(r.get("wl", "")).upper()
        if wl == "W":
            st["wins"] += 1
        elif wl == "L":
            st["losses"] += 1
        st["pts_sum"] += _to_float(r.get("pts", 0))
        st["reb_sum"] += _to_float(r.get("reb", 0))
        st["ast_sum"] += _to_float(r.get("ast", 0))
        st["stl_sum"] += _to_float(r.get("stl", 0))
        st["blk_sum"] += _to_float(r.get("blk", 0))
        st["turnovers_sum"] += _to_float(r.get("turnovers", 0))
        st["plus_minus_sum"] += _to_float(r.get("plus_minus", 0))

    out = {}
    for name, st in by_player.items():
        g = max(int(st["games"]), 1)
        out[name] = {
            "games": int(st["games"]),
            "wins": int(st["wins"]),
            "losses": int(st["losses"]),
            "total_pts": int(round(st["pts_sum"])),
            "ppg": round(st["pts_sum"] / g, 2),
            "rpg": round(st["reb_sum"] / g, 2),
            "apg": round(st["ast_sum"] / g, 2),
            "spg": round(st["stl_sum"] / g, 2),
            "bpg": round(st["blk_sum"] / g, 2),
            "tpg": round(st["turnovers_sum"] / g, 2),
            "plus_minus_avg": round(st["plus_minus_sum"] / g, 2),
        }

    # One W/L per game_id (Spurs team result). Use for head-to-head series record — not per_player rows.
    wl_by_game: dict[str, str] = {}
    for r in records:
        gid = str(r.get("game_id", "")).strip()
        if not gid:
            continue
        wl = str(r.get("wl", "")).upper().strip()
        if wl in ("W", "L"):
            wl_by_game[gid] = wl
    series_w = sum(1 for w in wl_by_game.values() if w == "W")
    series_l = sum(1 for w in wl_by_game.values() if w == "L")

    # Sorted by PPG for quick head-to-head narratives (full detail remains in per_player).
    scoring_ranked = sorted(
        (
            {
                "player_name": n,
                "games": int(st["games"]),
                "ppg": round(st["pts_sum"] / max(int(st["games"]), 1), 2),
                "total_pts": int(round(st["pts_sum"])),
            }
            for n, st in by_player.items()
        ),
        key=lambda x: (-x["ppg"], x["player_name"]),
    )

    return {
        "retrieved_rows": len(records),
        "distinct_games_in_payload": len(games_set),
        "team_series_in_payload": {
            "games_with_result": len(wl_by_game),
            "wins": series_w,
            "losses": series_l,
        },
        "matchup_spurs_scoring_ranked": scoring_ranked,
        "per_player": out,
    }


def _pick_focus_player(query: str, player_names: list[str]) -> str | None:
    q = query.lower()
    for n in player_names:
        if n.lower() in q:
            return n
    q_tokens = set(re.findall(r"[a-z0-9]+", q))
    for n in player_names:
        last = n.lower().split()[-1].replace(".", "")
        if last and last in q_tokens:
            return n
    if len(player_names) == 1:
        return player_names[0]
    return None


def _is_consistent_with_precomputed(
    output_text: str, precomputed_stats: dict, focus_player: str | None
) -> bool:
    """If we know focus player, output must include the exact games count."""
    if not focus_player:
        return True
    pstats = precomputed_stats.get("per_player", {}).get(focus_player)
    if not pstats:
        return True
    expected_games = int(pstats.get("games", 0))
    if expected_games <= 0:
        return True
    return (
        re.search(rf"\b{expected_games}\s+games?\b", output_text, flags=re.IGNORECASE)
        is not None
    )


def _precomputed_sentence(precomputed_stats: dict, focus_player: str | None) -> str | None:
    """Short deterministic sentence with trusted averages."""
    if not focus_player:
        return None
    p = precomputed_stats.get("per_player", {}).get(focus_player)
    if not p:
        return None
    return (
        f"{focus_player} averages {p.get('ppg', 0)} PPG, {p.get('rpg', 0)} RPG, "
        f"and {p.get('apg', 0)} APG across {p.get('games', 0)} games in this dataset."
    )


def build_task(
    user_query: str, records: list[dict], player_names: list[str], precomputed_stats: dict
) -> str:
    payload = {
        "user_query": user_query,
        "retrieved_games": records,
        "precomputed_stats": precomputed_stats,
    }
    body = json.dumps(payload, indent=2)
    names_line = ", ".join(player_names) if player_names else "(none)"
    return (
        body
        + "\n\n---\nAllowed player names (use these exact forms only; never expand initials to full first names): "
        + names_line
    )
