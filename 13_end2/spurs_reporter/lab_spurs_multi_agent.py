#!/usr/bin/env python3
"""
LAB: multi-agent workflow with Spurs tools (incremental build).

Step 1: SQLite path + imports.
Step 2: search_spurs_player_games() + tool metadata; optional --direct to call the tool without Ollama.
Step 3: Agent 1 — agent_run(..., tools=[tool_search_spurs_player_games], output="text").
Step 4: Agent 2 — agent_run(..., tools=None) turns retrieval into a short written report.
Hybrid stats: tool output includes compute_precomputed_stats; Agent 2 gets explicit games-count constraints when needed.
See LAB_spurs_multi_agent_steps.md and README_SPURS_MULTI_AGENT.md.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

# This folder must be on sys.path for `functions` (agent_run, ensure_ollama).
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from functions import DEFAULT_MODEL, agent_run  # noqa: E402
from spurs_stats import (  # noqa: E402
    _is_consistent_with_precomputed,
    _pick_focus_player,
    _precomputed_sentence,
    compute_precomputed_stats,
)
from spurs_season_store import (  # noqa: E402
    connect,
    current_nba_season_id,
    game_line_score_markdown,
    get_game_line_score,
    get_loaded_nba_season,
    get_loaded_season_type,
    latest_game_date,
    player_games_for_opponent_matchup,
    player_games_in_calendar_month,
    resolve_opponent_tricode,
    row_count,
    row_count_for_nba_season,
    rows_for_game_on_date,
    search_player_games,
)

DEFAULT_DB = _HERE / "data" / "spurs_season.db"

# Agent 1: must use exactly one tool call (no inventing box scores).
ROLE_AGENT_RETRIEVAL = (
    "You are a retrieval assistant for San Antonio Spurs season stats. "
    "You have no data until you call a tool. Call exactly ONE tool once. "
    "Choose tools in this **priority order** (first match wins):\n"
    "(1) **spurs_games_vs_team** — user asks how the Spurs did **against one named NBA team** this season "
    "(vs Thunder, against the Lakers, head-to-head with OKC). Pass opponent as nickname or tricode. "
    "Do not use search for that pattern.\n"
    "(2) **spurs_player_games_in_month** — ONLY when the user explicitly names a **calendar month** "
    "(in March, January stats, …); pass year, month (1-12), and player_name_substr. "
    "Do NOT guess year or month.\n"
    "(3) **spurs_recap_spurs_game** — **one full game**: recaps, **last/latest/most recent game**, "
    "**last night**, **yesterday's game**, or a **specific date** (game_date=YYYY-MM-DD). "
    "**Omit game_date** for the latest game in the database. "
    "You MUST use this for any single-game recap—**never** use search_spurs_player_games for "
    "'last game' / 'latest game' / 'recap of the game' questions (search returns many games' rows and breaks recaps).\n"
    "(4) **search_spurs_player_games** — keyword/LIKE search across the season "
    "(player name, opponent tricode, matchup, date fragment). "
    "Use for trends and multi-game questions **that are not** (1)–(3). "
    "Matchup uses NBA tricodes (OKC, LAL). "
    "Do not make up games, stats, or players."
)

# Agent 2: narrative only — no tools (fact vs recap variants, Phase 5).
# Experiment tuning intent: A = underspecified baseline (lower completeness expected vs B);
# B = maximize grounded completeness + mild honest Spurs-fan color (higher completeness / spurs_bias vs C);
# C = wire-service neutrality + omission (lower spurs_bias; may trade completeness). Same retrieval/model.
# ----------------------------
# A: Weak plain-language baseline
# ----------------------------

ROLE_AGENT_REPORT_FACT = (
    "Answer the user's question using the retrieved Spurs data below. "
    "Keep the answer clear and reasonably brief. "
    "Use the numbers and player names from the data when they are helpful. "
    "If the data does not seem to answer the question, say so. "
    "Do not write code unless the user asks for code."
)

ROLE_AGENT_REPORT_RECAP = (
    "Write a recap of the Spurs game using the retrieved data below. "
    "If the table includes both teams, use the **`team`** column: **`SAS`** is San Antonio; "
    "other codes are the opponent—only attribute stats to a player when their row shows it. "
    "Mention the result, how the game went, and a few players who stood out. "
    "You do **not** need to exhaust every row, quarter, or checklist item—keep the recap **reasonably brief**. "
    "Write in a natural sports-recap style. "
    "Do not write code unless the user asks for code."
)

ROLE_AGENT_REPORT_STRICT_FACT = ROLE_AGENT_REPORT_FACT

ROLE_AGENT_REPORT_STRICT_RECAP = ROLE_AGENT_REPORT_RECAP

ROLE_AGENT_REPORT_FACT_VS_HEAD_TO_HEAD = (
    "Answer the user's head-to-head question using the retrieved Spurs data below. "
    "Mention the Spurs record against the opponent and the main Spurs scorers if that information is available. "
    "Keep it concise and natural. "
    "Do not write code unless the user asks for code."
)

ROLE_AGENT_REPORT_STRICT_FACT_VS_HEAD_TO_HEAD = ROLE_AGENT_REPORT_FACT_VS_HEAD_TO_HEAD


# ----------------------------
# B: Comprehensive grounded synthesis
# ----------------------------

STANDALONE_B_RECAP = (
    "You are a careful Spurs game-recap writer. Use ONLY the retrieved block below. "
    "**Prompt B — design goal:** **maximum supported completeness** (cover every checklist item below that the data supports) "
    "plus **mild, honest Spurs-fan color** in word choice when still truthful (e.g. disappointment after a loss, relief after a win)—"
    "this is intentional contrast vs neutral Prompt C. "
    "Write TWO to THREE substantial narrative paragraphs—plain prose only, no markdown headings or bullet lists. "
    "Prefer inclusion over omission whenever a fact is directly supported by the retrieved data; **when in doubt, include** if the table or quarter lines support it. "
    "Open the recap: **first paragraph** must state who won/lost and the **matchup** early, using Spurs **`wl`**. "
    "**Team rows:** The player table may include **both teams**. **`team` = SAS** identifies Spurs players; "
    "**other `team` values** are the opponent tricode—name opponent players only when their row appears with stats. "
    "**Completeness checklist (satisfy each that applies to the block):** "
    "(1) Final outcome and matchup + Spurs **`wl`**; "
    "(2) If **Score by quarter** exists, describe game flow using **only** those numbers (include **Final** or implied totals if shown); "
    "(3) Name the **top three Spurs by points** this game from rows where **`team` = SAS** (name + pts from table); "
    "(4) If opponent rows exist, at least **one** opponent highlight (name + stat from that row); "
    "(5) Mention at least **one** additional Spurs line beyond the top three if the table has another clearly notable pts/reb/ast line. "
    "Use exact player names as written. "
    "Do not claim dominance, collapse, comeback, or momentum unless quarter or score lines support it. "
    "Do not invent injuries, shooting percentages, advanced metrics, crowd reactions, quotes, coaching decisions, or context outside the retrieved block. "
    "The recap should read **noticeably fuller** than a minimal answer."
)

STANDALONE_B_FACT = (
    "You are a comprehensive Spurs data-answering assistant. Use ONLY the retrieved block below. "
    "**Prompt B — design goal:** **maximum supported completeness**; when unsure whether a supported detail helps, **include it**. "
    "Answer the user's exact question, but include every directly relevant supported element from the retrieval: "
    "player averages, games count, W–L record, opponent or time slice, and any other directly relevant context. "
    "Prefer a fuller answer over a minimal one when the data supports it. "
    "Use precomputed_stats, Trusted line, Spurs record, and the table as evidence. "
    "Do not invent unsupported stats, shooting percentages, injuries, opinions, or context. "
    "Do not treat retrieved_rows as games if distinct_games_in_payload or database_scope is available. "
    "Use exact player names and exact numbers from the retrieved data."
)

STANDALONE_B_FACT_VS_HEAD_TO_HEAD = (
    "You are a comprehensive Spurs head-to-head analyst. Use ONLY the retrieved block below. "
    "Your objective is **maximum supported completeness within exactly two sentences**. "
    "Sentence 1 must state the Spurs W–L record against the opponent tricode from Trusted series and clearly summarize the series result. "
    "Sentence 2 must list the top three Spurs scorers by PPG in that matchup, including each exact player name and exact PPG value. "
    "Use Trusted series, Spurs scoring in this matchup, matchup_spurs_scoring_ranked, and the table as evidence. "
    "Do not omit supported scorer PPG values. "
    "Do not mention unsupported stats, shooting percentages, or outside context. "
    "Do not use bullets or headings."
)


# ----------------------------
# C: Strict evidentiary grounding
# ----------------------------

STANDALONE_C_RECAP = (
    "You are a neutral evidence-only NBA recap writer. Use ONLY the retrieved block below. "
    "**Prompt C — design goal:** **wire-service / national-audience neutrality**—**minimum Spurs homer tone** and "
    "**minimum unsupported inference**, even if that means **less** scene-setting than Prompt B. "
    "Your objective is **maximum factual precision**; **when unsure whether a detail is essential, omit it**. "
    "Prefer **two** concise paragraphs; use a third only if strictly needed for clarity—plain prose, no markdown headings or bullet lists. "
    "Every factual claim must be directly supported by the retrieved table, Score by quarter, Trusted line, or precomputed_stats. "
    "If a detail is absent, ambiguous, or only implied, omit it. "
    "**Team rows:** Use **`team` = SAS** for Spurs and **other `team` values** for the opponent—never swap teams. "
    "Do not praise or blame teams or players with **subjective** adjectives; stick to verifiable facts tied to the block. "
    "Do not infer momentum, dominance, collapse, clutch play, strategy, emotions, causes, or significance unless directly shown by the data. "
    "Do **not** use evaluative sportswriter clichés ('standout', 'explosive', 'dominant', 'clutch', 'surge', 'took over') "
    "unless you tie the word to a **specific number or quarter line** in the same sentence from the block. "
    "Use exact player names as written. Never expand initials. "
    "Do not use fan framing such as 'we' or 'our'. "
    "Do not invent injuries, shooting percentages, advanced metrics, crowd reactions, quotes, coaching decisions, or context outside the retrieved block. "
    "When uncertain, omit."
)

STANDALONE_C_FACT = (
    "You are a strict evidence-only Spurs data assistant. Use ONLY the retrieved block below. "
    "**Prompt C — design goal:** **maximum factual precision and minimum unsupported inference**; "
    "**when unsure, omit** optional context even if it appears in the retrieval but is not strictly required to answer the question. "
    "Answer only what the user asked. "
    "Every statistic, player name, record, opponent reference, games count, and numerical value must be directly supported by precomputed_stats, "
    "Trusted line, Spurs record, database_scope, or the table. "
    "If the evidence is missing, incomplete, or ambiguous, omit the claim rather than infer. "
    "Do not add context, opinions, explanations, scouting language, trend language, or narrative interpretation unless directly supported. "
    "Do not mention shooting percentages, advanced metrics, injuries, or outside information unless present in the retrieval. "
    "Use exact numbers and exact player names."
)

STANDALONE_C_FACT_VS_HEAD_TO_HEAD = (
    "You are a strict evidence-only Spurs head-to-head assistant. Use ONLY the retrieved block below. "
    "Your objective is **maximum factual precision within exactly two sentences**. "
    "Sentence 1 must state only the Spurs W–L record against the opponent using Trusted series or team_series_in_payload. "
    "Sentence 2 must state only the top three Spurs scorers by PPG using Spurs scoring in this matchup or matchup_spurs_scoring_ranked. "
    "Every player name, team code, record, and PPG value must exactly match the retrieved evidence. "
    "Do not add series interpretation, adjectives, opinions, trend claims, shooting percentages, or outside context. "
    "If a required value is missing, omit that part rather than guess. "
    "Do not use bullets or headings."
)


# ----------------------------
# Strict suffixes
# ----------------------------

_FOCUS_GAMES_SUFFIX_RECAP = (
    " If a focus player and required games count appear in precomputed_stats, include that exact games count "
    "and do not contradict it."
)

_FOCUS_GAMES_SUFFIX_FACT = (
    " If a focus player and required games count appear below, state that exact games count "
    "and do not contradict it."
)

_GEN_PROMPT_VARIANT: str = "A"


def set_generation_prompt_variant(variant: str) -> None:
    global _GEN_PROMPT_VARIANT
    u = (variant or "A").strip().upper()
    if u not in ("A", "B", "C"):
        raise ValueError(f"gen-prompt must be A, B, or C, got {variant!r}")
    _GEN_PROMPT_VARIANT = u


def _agent2_role_for_variant(strict: bool) -> str:
    """Resolve full Agent 2 system prompt for Homework 3 variants A/B/C."""
    v = _GEN_PROMPT_VARIANT
    tool = _LAST_RETRIEVAL_TOOL

    if tool == TOOL_NAME_RECAP:
        if v == "A":
            return ROLE_AGENT_REPORT_STRICT_RECAP if strict else ROLE_AGENT_REPORT_RECAP
        if v == "B":
            return (
                STANDALONE_B_RECAP + _FOCUS_GAMES_SUFFIX_RECAP
                if strict
                else STANDALONE_B_RECAP
            )
        return (
            STANDALONE_C_RECAP + _FOCUS_GAMES_SUFFIX_RECAP if strict else STANDALONE_C_RECAP
        )

    if tool == TOOL_NAME_VS_TEAM:
        if v == "A":
            return (
                ROLE_AGENT_REPORT_STRICT_FACT_VS_HEAD_TO_HEAD
                if strict
                else ROLE_AGENT_REPORT_FACT_VS_HEAD_TO_HEAD
            )
        base = (
            STANDALONE_B_FACT_VS_HEAD_TO_HEAD
            if v == "B"
            else STANDALONE_C_FACT_VS_HEAD_TO_HEAD
        )
        return base + _FOCUS_GAMES_SUFFIX_FACT if strict else base

    if v == "A":
        return ROLE_AGENT_REPORT_STRICT_FACT if strict else ROLE_AGENT_REPORT_FACT
    base = STANDALONE_B_FACT if v == "B" else STANDALONE_C_FACT
    return base + _FOCUS_GAMES_SUFFIX_FACT if strict else base


# Used by search_spurs_player_games; main() sets this from --db before calling the tool.
_SPURS_DB: Path = DEFAULT_DB

# If the LLM omits `query` in the tool call, fall back to this (set in main before agent_run).
_PENDING_USER_QUERY: str = ""

# Filled by search_spurs_player_games after a successful table return (for consistency check).
_LAST_PRECOMPUTED: dict | None = None
_LAST_FOCUS_PLAYER: str | None = None

# Max rows for tool/search when the model omits `limit` (main sets from row count for the active NBA season).
_EFFECTIVE_ROW_LIMIT: int = 40

# NBA season id (e.g. 2025-26) for SQL filter; None = do not filter (legacy DB with no metadata).
_ACTIVE_NBA_SEASON: str | None = None

# Which retrieval tool produced the current block (Phase 5: Agent 2 prompt branch).
TOOL_NAME_SEARCH = "search_spurs_player_games"
TOOL_NAME_MONTH = "spurs_player_games_in_month"
TOOL_NAME_RECAP = "spurs_recap_spurs_game"
TOOL_NAME_VS_TEAM = "spurs_games_vs_team"
_LAST_RETRIEVAL_TOOL: str | None = None
# Set only by spurs_games_vs_team: resolved NBA tricode (e.g. LAL) for Agent 2 wording vs "this opponent".
_LAST_VS_OPPONENT_TRICODE: str | None = None


def set_effective_row_limit(n: int) -> None:
    global _EFFECTIVE_ROW_LIMIT
    _EFFECTIVE_ROW_LIMIT = max(1, int(n))


def set_active_nba_season(season: str | None) -> None:
    global _ACTIVE_NBA_SEASON
    _ACTIVE_NBA_SEASON = season


def set_pending_user_query(text: str) -> None:
    global _PENDING_USER_QUERY
    _PENDING_USER_QUERY = (text or "").strip()


def reset_retrieval_artifacts() -> None:
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER, _ACTIVE_NBA_SEASON, _LAST_RETRIEVAL_TOOL
    global _LAST_VS_OPPONENT_TRICODE
    _LAST_PRECOMPUTED = None
    _LAST_FOCUS_PLAYER = None
    _ACTIVE_NBA_SEASON = None
    _LAST_RETRIEVAL_TOOL = None
    _LAST_VS_OPPONENT_TRICODE = None


def set_spurs_db(path: str | Path) -> None:
    """Point the tool at a specific spurs_season.db (call from main after parsing CLI)."""
    global _SPURS_DB
    _SPURS_DB = Path(path)


def _set_last_retrieval_tool(name: str | None) -> None:
    global _LAST_RETRIEVAL_TOOL
    _LAST_RETRIEVAL_TOOL = name


def _should_direct_latest_recap(query: str) -> bool:
    """
    Call spurs_recap_spurs_game('') without Agent 1 when the question is clearly
    "latest/last single game" — avoids small models using search and returning
    multi-game player slices (wrong game in Agent 2).
    """
    ql = (query or "").strip().lower()
    if not ql:
        return False
    if re.search(r"\b(recap|summary)\b", ql) and re.search(
        r"\b(last|latest|most\s+recent)\s+game\b", ql
    ):
        return True
    if re.search(
        r"\b(last|latest|most\s+recent)\s+game\b.{0,120}\b(database|db)\b",
        ql,
        flags=re.DOTALL,
    ):
        return True
    return False


def agent2_report_role() -> str:
    """Agent 2 system prompt: tighter for facts, slightly richer for single-game recap."""
    return _agent2_role_for_variant(strict=False)


def agent2_report_role_strict() -> str:
    return _agent2_role_for_variant(strict=True)


def _agent2_retrieval_context(
    retrieval_tool: str | None,
    precomputed: dict | None,
    n_scope: int,
) -> str:
    """Tell Agent 2 what kind of slice it is so stats are described accurately."""
    if retrieval_tool == TOOL_NAME_RECAP:
        return (
            "Retrieval: single game — **both teams'** player lines (`team` = SAS for Spurs, opponent tricode for the other side); "
            "**Score by quarter** is optional and comes from the database (run --refresh to populate).\n\n"
        )
    if retrieval_tool == TOOL_NAME_MONTH:
        return (
            "Retrieval: one calendar month — aggregates cover that month only.\n\n"
        )
    if retrieval_tool == TOOL_NAME_VS_TEAM:
        dg = ""
        opp_label = _LAST_VS_OPPONENT_TRICODE or "this opponent"
        if precomputed:
            n = int(precomputed.get("distinct_games_in_payload") or 0)
            rr = int(precomputed.get("retrieved_rows") or 0)
            if n > 0:
                dg = (
                    f"In this block there are **{n} game(s)** vs **{opp_label}** "
                    f"(`distinct_games_in_payload`) and **{rr} player rows** (`retrieved_rows`—not games). "
                )
            ts = precomputed.get("team_series_in_payload")
            if isinstance(ts, dict) and ts.get("games_with_result"):
                dg += (
                    f"**team_series_in_payload** (authoritative team W–L in this slice): "
                    f"{ts.get('wins', 0)}–{ts.get('losses', 0)} over {ts.get('games_with_result', 0)} game(s). "
                    "If losses > 0, the Spurs did not win every game—say so.\n"
                )
        return (
            "Retrieval: head-to-head vs one opponent — season-scoped slice; precomputed_stats apply to these rows only. "
            + dg
            + "If **database_scope** appears below, that is how many **games** are in the database for this matchup—"
            "not retrieved_rows. "
            "For home/away: in matchup, `SAS @ OKC` is San Antonio away, `SAS vs. OKC` is home. "
            "State the series using **team_series_in_payload** and/or `wl` per game_id. "
            "For **scoring leaders** in this matchup, use the **Spurs scoring in this matchup** table below "
            "and/or **matchup_spurs_scoring_ranked** in precomputed_stats (PPG in this slice; sorted by PPG).\n\n"
        )
    if retrieval_tool == TOOL_NAME_SEARCH and precomputed:
        rr = int(precomputed.get("retrieved_rows") or 0)
        out = (
            "Retrieval: search slice — use **Trusted line** for player averages and **Spurs record (this slice)** "
            "for team W–L in these games (same slice). "
            "Report simply in one or two short sentences; do not over-explain or repeat the same figure.\n\n"
        )
        if n_scope > 0 and rr < n_scope:
            out += (
                f"Note: **{rr}** player-game row(s) in this slice vs **{n_scope}** in season scope—"
                "you may add a brief phrase like 'in these games' if needed, not a long caveat.\n\n"
            )
        return out
    return ""


# --- Step 2: tool function (must stay in global scope for agent() in a later step) ---


def _coerce_tool_limit(limit: object) -> int:
    """
    Ollama sometimes passes limit as the string 'None' or other non-int values.
    Fall back to _EFFECTIVE_ROW_LIMIT when missing or invalid.
    """
    if limit is None:
        return _EFFECTIVE_ROW_LIMIT
    if isinstance(limit, str):
        s = limit.strip().lower()
        if s in ("", "none", "null"):
            return _EFFECTIVE_ROW_LIMIT
        try:
            return int(s)
        except ValueError:
            return _EFFECTIVE_ROW_LIMIT
    try:
        return int(limit)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return _EFFECTIVE_ROW_LIMIT





def _coerce_int_arg(v: object, *, name: str, min_v: int | None = None, max_v: int | None = None) -> int:
    """Coerce tool/CLI year or month from int/float/str."""
    if isinstance(v, bool):
        raise ValueError(f"{name} must be a number")
    if isinstance(v, int):
        n = v
    elif isinstance(v, float):
        n = int(v)
    else:
        s0 = str(v).strip()
        m = re.match(r"^(-?\d+)", s0)
        if not m:
            raise ValueError(f"{name}: invalid number {v!r}")
        n = int(m.group(1))
    if min_v is not None and n < min_v:
        raise ValueError(f"{name} must be >= {min_v}")
    if max_v is not None and n > max_v:
        raise ValueError(f"{name} must be <= {max_v}")
    return n


def _matchup_scoring_markdown(precomputed: dict, *, max_rows: int = 18) -> str | None:
    """Compact table: Spurs players' scoring in this head-to-head slice (sorted by PPG)."""
    ranked = precomputed.get("matchup_spurs_scoring_ranked")
    if not isinstance(ranked, list) or not ranked:
        return None
    lines = [
        "| player | games | ppg |",
        "| :--- | ---: | ---: |",
    ]
    for row in ranked[:max_rows]:
        if not isinstance(row, dict):
            continue
        name = str(row.get("player_name", ""))
        if not name:
            continue
        lines.append(
            f"| {name} | {row.get('games', 0)} | {row.get('ppg', 0)} |"
        )
    if len(lines) <= 2:
        return None
    return "\n".join(lines)


def _vs_team_top_scorers_copy_block(precomputed: dict, *, top_n: int = 3) -> str | None:
    """
    Exact lines for the task prompt so small LMs cannot skip player scoring.
    Uses matchup_spurs_scoring_ranked; skips rows with no points in the slice.
    """
    ranked = precomputed.get("matchup_spurs_scoring_ranked")
    if not isinstance(ranked, list) or not ranked:
        return None
    picked: list[dict] = []
    for row in ranked:
        if not isinstance(row, dict):
            continue
        if int(row.get("total_pts") or 0) <= 0:
            continue
        picked.append(row)
        if len(picked) >= top_n:
            break
    if not picked:
        return None
    parts = [
        f"{row.get('player_name')} at {row.get('ppg')} PPG" for row in picked
    ]
    return (
        "Second sentence must include these **PPG** figures and spellings (names + averages only): "
        + "; ".join(parts)
        + ". Do not omit the numeric PPG values."
    )


def _team_series_trusted_line(
    precomputed: dict, *, opponent_tricode: str | None = None
) -> str | None:
    """One sentence for head-to-head record — small models often skip JSON."""
    ts = precomputed.get("team_series_in_payload")
    if not isinstance(ts, dict):
        return None
    w = int(ts.get("wins") or 0)
    l = int(ts.get("losses") or 0)
    g = int(ts.get("games_with_result") or 0)
    if g <= 0:
        return None
    opp = f"**{opponent_tricode}**" if opponent_tricode else "this opponent"
    return (
        f"Spurs **{w}–{l}** vs {opp} in this slice (**{g}** game(s)); "
        f"losses={l} means they did not sweep. Copy this record—do not infer from per_player wins."
    )


def _slice_spurs_record_line(precomputed: dict) -> str | None:
    """Spurs W–L across distinct games in this retrieval (`wl` per game_id)."""
    ts = precomputed.get("team_series_in_payload")
    if not isinstance(ts, dict):
        return None
    w = int(ts.get("wins") or 0)
    l = int(ts.get("losses") or 0)
    g = int(ts.get("games_with_result") or 0)
    if g <= 0:
        return None
    return f"Spurs **{w}–{l}** in those **{g}** games."


def _finalize_retrieval_block(
    df: pd.DataFrame,
    *,
    focus_query: str,
    append_team_series_trusted: bool = False,
    opponent_tricode_for_labels: str | None = None,
) -> str:
    """Shared markdown + precomputed_stats + Trusted line; sets consistency globals."""
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER
    records = df.to_dict(orient="records")
    precomputed = compute_precomputed_stats(records)
    player_names = sorted(
        {str(r.get("player_name", "")) for r in records if r.get("player_name")}
    )
    focus_q = (focus_query or "").strip()
    _LAST_PRECOMPUTED = precomputed
    _LAST_FOCUS_PLAYER = _pick_focus_player(focus_q, player_names)

    display_df = df.drop(columns=["nba_season"], errors="ignore")
    table_note = ""
    if "team" in display_df.columns:
        teams_u = (
            display_df["team"].dropna().astype(str).str.upper().unique().tolist()
        )
        if len(teams_u) > 1:
            table_note = (
                "**Table note:** Rows with `team=SAS` are Spurs players; other `team` values are the opponent tricode.\n\n"
            )
    md = table_note + display_df.to_markdown(index=False)
    trusted = _precomputed_sentence(precomputed, _LAST_FOCUS_PLAYER)
    block = (
        md
        + "\n\n---\n**precomputed_stats** (authoritative — do not recompute these from the table):\n```json\n"
        + json.dumps(precomputed, indent=2)
        + "\n```"
    )
    if trusted:
        block += "\n\n**Trusted line:** " + trusted
    if not append_team_series_trusted:
        sr = _slice_spurs_record_line(precomputed)
        if sr:
            block += "\n\n**Spurs record (this slice):** " + sr
    if append_team_series_trusted:
        ts_tr = _team_series_trusted_line(
            precomputed, opponent_tricode=opponent_tricode_for_labels
        )
        if ts_tr:
            block += "\n\n**Trusted series:** " + ts_tr
        sc_md = _matchup_scoring_markdown(precomputed)
        if sc_md:
            block += (
                "\n\n---\n**Spurs scoring in this matchup** "
                "(per player in this slice; **ppg** = points per game in these games only; sorted by PPG):\n\n"
                + sc_md
            )
    return block


def search_spurs_player_games(query: str = "", limit: int | None = None) -> str:
    """
    Search Spurs player-game lines in SQLite; return a markdown table string.

    Parameters match the Ollama tool schema: query tokens match player_name, matchup, date, etc.
    `query` defaults to "" so small models that omit an argument do not crash the run.
    If `limit` is omitted, uses _EFFECTIVE_ROW_LIMIT (set in main; default = all rows in DB).
    """
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER, _LAST_VS_OPPONENT_TRICODE
    _LAST_VS_OPPONENT_TRICODE = None

    query = (query or "").strip()
    if not query:
        query = _PENDING_USER_QUERY
    if not query:
        _LAST_PRECOMPUTED = None
        _LAST_FOCUS_PLAYER = None
        _set_last_retrieval_tool(None)
        return (
            "Tool error: pass a non-empty `query` (player name, matchup keyword, or date)."
        )
    lim = _coerce_tool_limit(limit)
    lim = min(max(lim, 1), 10**9)

    conn = connect(str(_SPURS_DB))
    try:
        df = search_player_games(
            conn, query, limit=lim, nba_season=_ACTIVE_NBA_SEASON
        )
        if df.empty:
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                f"No matching rows for query {query!r}. "
                "Try a player last name, opponent, or date fragment."
            )
        focus_q = (_PENDING_USER_QUERY or query).strip()
        _set_last_retrieval_tool(TOOL_NAME_SEARCH)
        return _finalize_retrieval_block(df, focus_query=focus_q)
    finally:
        conn.close()


tool_search_spurs_player_games = {
    "type": "function",
    "function": {
        "name": "search_spurs_player_games",
        "description": (
            "Default tool for player performance and season questions: search the Spurs DB for box-score lines "
            "(player last name like Fox or Wembanyama, opponent tricode/nickname, matchup). "
            "Matchup text uses NBA tricodes (e.g. OKC). For 'how did we do vs [one team] this season', prefer spurs_games_vs_team. "
            "Use for 'how is X playing', trends, and any question without a named calendar month. "
            "Returns a markdown table plus precomputed_stats (trusted aggregates)."
        ),
        "parameters": {
            "type": "object",
            "required": ["query"],
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search string (player name, matchup keyword, date fragment, etc.).",
                },
                "limit": {
                    "type": "integer",
                    "description": (
                        "Maximum rows to return. Omit to use all rows for the active NBA season in the DB."
                    ),
                },
            },
        },
    },
}


def spurs_games_vs_team(opponent: str = "", limit: int | None = None) -> str:
    """
    Player-game rows for Spurs games vs one opponent (filtered on matchup tricode).
    """
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER, _LAST_VS_OPPONENT_TRICODE

    opp = (opponent or "").strip()
    if not opp:
        opp = (_PENDING_USER_QUERY or "").strip()
    if not opp:
        _LAST_VS_OPPONENT_TRICODE = None
        _LAST_PRECOMPUTED = None
        _LAST_FOCUS_PLAYER = None
        _set_last_retrieval_tool(None)
        return (
            "Tool error: pass opponent (NBA team nickname or 3-letter tricode, e.g. Thunder or OKC)."
        )
    tri = resolve_opponent_tricode(opp)
    if not tri:
        _LAST_VS_OPPONENT_TRICODE = None
        _LAST_PRECOMPUTED = None
        _LAST_FOCUS_PLAYER = None
        _set_last_retrieval_tool(None)
        return (
            f"Could not resolve opponent {opp!r} to a team code. "
            "Try a nickname (e.g. Thunder, Lakers) or tricode (e.g. OKC, LAL)."
        )

    lim = _coerce_tool_limit(limit)
    lim = min(max(lim, 1), 10**9)

    conn = connect(str(_SPURS_DB))
    try:
        df = player_games_for_opponent_matchup(
            conn,
            opp,
            nba_season=_ACTIVE_NBA_SEASON,
            limit=lim,
        )
        if df.empty:
            _LAST_VS_OPPONENT_TRICODE = None
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                f"No rows for games vs {opp!r} in this database/season filter. "
                "Check spelling or refresh the season data."
            )
        focus_q = (_PENDING_USER_QUERY or opp).strip()
        _LAST_VS_OPPONENT_TRICODE = tri
        _set_last_retrieval_tool(TOOL_NAME_VS_TEAM)
        block = _finalize_retrieval_block(
            df,
            focus_query=focus_q,
            append_team_series_trusted=True,
            opponent_tricode_for_labels=tri,
        )
        dg = int(
            (_LAST_PRECOMPUTED or {}).get("distinct_games_in_payload") or 0
        ) or int(df["game_id"].nunique())
        season_hint = _ACTIVE_NBA_SEASON or "YYYY-YY"
        block += (
            "\n\n---\n**database_scope:** "
            f"{dg} distinct game(s) vs **{tri}** appear in this SQLite database. "
            "Counts and records refer to loaded rows only. The full NBA schedule may include more meetings; "
            f"run `python spurs_season_rag.py --refresh --season {season_hint}` in this folder (needs network) to reload."
        )
        return block
    finally:
        conn.close()


tool_spurs_games_vs_team = {
    "type": "function",
    "function": {
        "name": "spurs_games_vs_team",
        "description": (
            "Spurs player box-score lines for games against one NBA opponent in the active season. "
            "Use for head-to-head questions: how the Spurs played vs Thunder/Lakers, record against a team, "
            "and per-player **PPG** in that matchup (headline answer: record + top scorers' averages). "
            "Pass opponent as nickname (Thunder, Lakers) or tricode (OKC, LAL). Narrower than search_spurs_player_games. "
            "Returns a markdown table, a Spurs scoring summary for the matchup, and precomputed_stats."
        ),
        "parameters": {
            "type": "object",
            "required": ["opponent"],
            "properties": {
                "opponent": {
                    "type": "string",
                    "description": "Opponent nickname (e.g. Thunder) or 3-letter NBA tricode (e.g. OKC).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows; omit to use the session row cap for the active NBA season.",
                },
            },
        },
    },
}


def spurs_player_games_in_month(
    year: object = None,
    month: object = None,
    player_name_substr: str = "",
    limit: int | None = None,
) -> str:
    """
    Box-score lines for one calendar month, optionally filtered to one player name substring.
    Use for questions like scoring in March (year + month + player).
    """
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER, _LAST_VS_OPPONENT_TRICODE
    _LAST_VS_OPPONENT_TRICODE = None

    try:
        y = _coerce_int_arg(year, name="year", min_v=2000, max_v=2100)
        m = _coerce_int_arg(month, name="month", min_v=1, max_v=12)
    except ValueError as e:
        _LAST_PRECOMPUTED = None
        _LAST_FOCUS_PLAYER = None
        _set_last_retrieval_tool(None)
        return f"Tool error: {e}"

    pns = (player_name_substr or "").strip()
    if not pns:
        pns = (_PENDING_USER_QUERY or "").strip()
        # Pull a likely last name from user question if still empty
        if not pns:
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                "Tool error: pass player_name_substr (e.g. Wembanyama) or ask about a named player."
            )

    lim = _coerce_tool_limit(limit)
    lim = min(max(lim, 1), 10**9)

    conn = connect(str(_SPURS_DB))
    try:
        df = player_games_in_calendar_month(
            conn,
            year=y,
            month=m,
            player_name_substr=pns,
            nba_season=_ACTIVE_NBA_SEASON,
            limit=lim,
        )
        if df.empty:
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                f"No rows for {y}-{m:02d} matching player name containing {pns!r}. "
                "Check spelling or month/year."
            )
        focus_q = (_PENDING_USER_QUERY or pns).strip()
        _set_last_retrieval_tool(TOOL_NAME_MONTH)
        return _finalize_retrieval_block(df, focus_query=focus_q)
    finally:
        conn.close()


tool_spurs_player_games_in_month = {
    "type": "function",
    "function": {
        "name": "spurs_player_games_in_month",
        "description": (
            "Get Spurs player box-score lines for one calendar month only. "
            "Use ONLY when the user names a month (e.g. March, January) or says 'in March 2026'. "
            "Do NOT use for 'how has [player] been playing' without a month — use search_spurs_player_games. "
            "Never invent year/month. Requires year, month (1-12), and player_name_substr."
        ),
        "parameters": {
            "type": "object",
            "required": ["year", "month", "player_name_substr"],
            "properties": {
                "year": {
                    "type": "integer",
                    "description": "Calendar year of the month (e.g. 2026 for March 2026).",
                },
                "month": {
                    "type": "integer",
                    "description": "Month number 1=January … 12=December.",
                },
                "player_name_substr": {
                    "type": "string",
                    "description": "Substring to match player_name (e.g. Wembanyama, Fox).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows; omit to use the session row cap for the active NBA season.",
                },
            },
        },
    },
}


def spurs_recap_spurs_game(game_date: str = "", limit: int | None = None) -> str:
    """
    All Spurs player lines for one game (latest in DB, or a specific ISO date).
    For questions like recap of last night or yesterday (interpreted as latest loaded game if no date).
    """
    global _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER, _LAST_VS_OPPONENT_TRICODE
    _LAST_VS_OPPONENT_TRICODE = None

    lim = _coerce_tool_limit(limit)
    lim = min(max(lim, 1), 10**9)

    conn = connect(str(_SPURS_DB))
    try:
        gd = (game_date or "").strip()
        if not gd:
            gd = latest_game_date(conn, nba_season=_ACTIVE_NBA_SEASON) or ""
        if not gd:
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return "Tool error: no games in database for this season filter."
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", gd):
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                f"Tool error: game_date must be YYYY-MM-DD or omit for latest game; got {gd!r}."
            )
        df = rows_for_game_on_date(
            conn, gd, nba_season=_ACTIVE_NBA_SEASON, limit=lim
        )
        if df.empty:
            _LAST_PRECOMPUTED = None
            _LAST_FOCUS_PLAYER = None
            _set_last_retrieval_tool(None)
            return (
                f"No rows for game_date={gd!r}. Check the date or refresh the database."
            )
        focus_q = (_PENDING_USER_QUERY or "").strip()
        _set_last_retrieval_tool(TOOL_NAME_RECAP)
        block = _finalize_retrieval_block(df, focus_query=focus_q)
        gid = str(df["game_id"].iloc[0])
        ls = get_game_line_score(conn, gid)
        if ls:
            block += (
                "\n\n---\n**Score by quarter** (Q1–Q4 are regulation; **OT** is overtime only; "
                "**Final** is the full game score — use for game flow)\n\n"
                + game_line_score_markdown(ls)
            )
        return block
    finally:
        conn.close()


tool_spurs_recap_spurs_game = {
    "type": "function",
    "function": {
        "name": "spurs_recap_spurs_game",
        "description": (
            "Full-team Spurs box-score lines for a single game (one game_date). "
            "Use for game recaps: last night, latest result, or a specific date. "
            "Omit game_date to use the latest game in the database. "
            "Otherwise pass game_date as YYYY-MM-DD."
        ),
        "parameters": {
            "type": "object",
            "required": [],
            "properties": {
                "game_date": {
                    "type": "string",
                    "description": "Game date YYYY-MM-DD in the database; omit for the most recent game.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max player rows (roster lines); omit for session default.",
                },
            },
        },
    },
}


SPURS_RETRIEVAL_TOOLS = [
    tool_search_spurs_player_games,
    tool_spurs_player_games_in_month,
    tool_spurs_recap_spurs_game,
    tool_spurs_games_vs_team,
]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Spurs multi-agent lab: --direct = tool only; default = Agent 1 + Agent 2."
    )
    parser.add_argument(
        "--db",
        default=str(DEFAULT_DB),
        help=f"Path to spurs_season.db (default: {DEFAULT_DB})",
    )
    parser.add_argument(
        "query",
        nargs="?",
        default="Wembanyama",
        help="Search string / user question (default: Wembanyama).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        metavar="N",
        help=(
            "Max rows for SQLite search (caps tool output size). "
            "Default: all rows in the DB (the loaded season data)."
        ),
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for both agents (default: {DEFAULT_MODEL}).",
    )
    parser.add_argument(
        "--season",
        default=None,
        metavar="YYYY-YY",
        help=(
            "NBA season id (e.g. 2025-26) to scope searches. "
            "Default: season stored in the DB when you ran --refresh. "
            "Must match that value if metadata is present."
        ),
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Skip LLM; call one tool directly (Step 2 smoke test).",
    )
    parser.add_argument(
        "--direct-month",
        nargs=3,
        metavar=("YEAR", "MONTH", "PLAYER"),
        default=None,
        help=(
            "With --direct: call spurs_player_games_in_month(YEAR, MONTH, PLAYER) "
            "instead of search_spurs_player_games."
        ),
    )
    parser.add_argument(
        "--direct-recap",
        nargs="?",
        const="",
        default=None,
        metavar="YYYY-MM-DD",
        help=(
            "With --direct: call spurs_recap_spurs_game. "
            "Omit the date for the latest game; or pass a single game_date."
        ),
    )
    parser.add_argument(
        "--direct-vs-team",
        default=None,
        metavar="OPPONENT",
        help=(
            "With --direct: call spurs_games_vs_team(OPPONENT) "
            "instead of search_spurs_player_games."
        ),
    )
    parser.add_argument(
        "--gen-prompt",
        choices=["A", "B", "C"],
        default="A",
        metavar="PRESET",
        help=(
            "Homework 3: Agent 2 generation preset (same retrieval/model). "
            "A=brief baseline; B=max completeness + mild Spurs-fan color; C=neutral wire-style + omission. "
            "Same tool/output shape per retrieval mode."
        ),
    )
    args = parser.parse_args()
    set_generation_prompt_variant(args.gen_prompt)

    if args.direct_month is not None and not args.direct:
        parser.error("--direct-month requires --direct")
    if args.direct_recap is not None and not args.direct:
        parser.error("--direct-recap requires --direct")
    if args.direct_vs_team is not None and not args.direct:
        parser.error("--direct-vs-team requires --direct")
    _direct_modes = (
        (args.direct_month is not None)
        + (args.direct_recap is not None)
        + (args.direct_vs_team is not None)
    )
    if _direct_modes > 1:
        parser.error(
            "Use only one of --direct-month, --direct-recap, or --direct-vs-team"
        )

    reset_retrieval_artifacts()
    set_spurs_db(args.db)

    conn = connect(args.db)
    try:
        n = row_count(conn)
        if n == 0:
            cs = current_nba_season_id()
            print(
                "Database is empty. Populate it from this folder, e.g.:\n"
                f"  cd {_HERE} && python spurs_season_rag.py --refresh --season {cs}"
            )
            sys.exit(1)
        loaded_season = get_loaded_nba_season(conn)
        loaded_type = get_loaded_season_type(conn)
    finally:
        conn.close()

    resolved_season = args.season if args.season is not None else loaded_season
    if args.season is not None and loaded_season is not None and args.season != loaded_season:
        print(
            f"Error: --season {args.season!r} does not match the DB metadata ({loaded_season!r}).\n"
            "Re-run refresh for that season, or omit --season to use the loaded season."
        )
        sys.exit(1)

    set_active_nba_season(resolved_season)

    conn_scope = connect(args.db)
    try:
        n_scope = row_count_for_nba_season(conn_scope, resolved_season)
    finally:
        conn_scope.close()

    if loaded_season is None and n > 0:
        cs = current_nba_season_id()
        print(
            "Note: No NBA season recorded in db_meta. Run: "
            f"cd {_HERE} && python spurs_season_rag.py --refresh --season {cs}\n"
            "Searches use all rows until metadata exists.\n"
        )

    effective_limit = args.limit if args.limit is not None else n_scope
    set_effective_row_limit(effective_limit)

    season_line = (
        f"NBA season: {resolved_season or 'unknown (run --refresh to record)'}"
        + (f" — {loaded_type}" if loaded_type else "")
    )
    print(f"Database: {args.db}")
    print(season_line)
    print(f"Rows in scope for this season filter: {n_scope}")
    print(
        f"Row limit for search: {effective_limit}"
        + (
            " (default: all rows for this NBA season)"
            if args.limit is None
            else ""
        )
    )
    print(
        "Tools:",
        ", ".join(t["function"]["name"] for t in SPURS_RETRIEVAL_TOOLS),
        end="\n\n",
    )

    if args.direct:
        print("--- Direct tool call (no LLM) ---\n")
        set_pending_user_query(args.query)
        if args.direct_month:
            y_s, m_s, pl = args.direct_month
            out = spurs_player_games_in_month(y_s, m_s, pl, limit=args.limit)
        elif args.direct_recap is not None:
            out = spurs_recap_spurs_game(args.direct_recap, limit=args.limit)
        elif args.direct_vs_team is not None:
            out = spurs_games_vs_team(args.direct_vs_team, limit=args.limit)
        else:
            out = search_spurs_player_games(args.query, limit=args.limit)
        print(out)
        return

    task = (
        f"User question: {args.query}\n"
        f"Active NBA season in this database: {resolved_season or 'unspecified'}.\n"
        "Tool choice (first matching case — see system role for details):\n"
        "• Head-to-head vs one named opponent this season → spurs_games_vs_team(opponent); "
        f"limit={effective_limit} or omit.\n"
        "• User names a calendar month for stats → spurs_player_games_in_month; "
        f"limit={effective_limit} or omit.\n"
        "• Single-game recap, last/latest/most recent game, last night, or a specific game date → "
        f"spurs_recap_spurs_game; omit game_date for latest, or YYYY-MM-DD; limit={effective_limit} or omit. "
        "Do **not** use search_spurs_player_games for these.\n"
        "• Otherwise → search_spurs_player_games(query); "
        f"limit={effective_limit} or omit.\n"
    )

    set_pending_user_query(args.query)

    print(f"Model: {args.model}")
    print(f"Generation preset (--gen-prompt): {args.gen_prompt}\n")
    print("--- Agent 1 (retrieval via tool) ---\n")
    if _should_direct_latest_recap(args.query):
        print(
            "(deterministic routing: latest single-game recap → spurs_recap_spurs_game, "
            "not search_spurs_player_games)\n"
        )
        data_block = spurs_recap_spurs_game("", limit=args.limit)
    else:
        data_block = agent_run(
            role=ROLE_AGENT_RETRIEVAL,
            task=task,
            tools=SPURS_RETRIEVAL_TOOLS,
            output="text",
            model=args.model,
        )
    print(data_block)

    recap_note = (
        "The retrieval is one contest: the player table includes **both teams**—use the **`team`** column "
        "(`SAS` = Spurs, other values = opponent tricode). Name opponent players only when their row appears; "
        "never assign a Spurs line to the opponent or vice versa.\n"
        if _LAST_RETRIEVAL_TOOL == TOOL_NAME_RECAP
        else ""
    )
    report_task = (
        _agent2_retrieval_context(_LAST_RETRIEVAL_TOOL, _LAST_PRECOMPUTED, n_scope)
        + f"Original user question (answer this and only this):\n{args.query}\n\n"
        + (recap_note + "\n" if recap_note else "")
        + "Instructions: Use the retrieval below only as evidence. Do not summarize everything in the block—"
        "extract what is needed to answer the question in the fewest sentences.\n\n"
        f"Retrieved data (markdown table or message from the database tool):\n\n{data_block}"
    )
    if "**Trusted line:**" in data_block and "**Spurs record (this slice):**" in data_block:
        report_task += (
            "\n\nANSWER FORMAT (mandatory): Exactly **two** sentences. "
            "Sentence 1: Restate the **Trusted line** in full (PPG, RPG, APG, and games)—same numbers only. "
            "Sentence 2: Spurs team **W–L** from **Spurs record (this slice)** only (e.g. went 39–11 in those 50 games). "
            "Do not mention FG%, TS%, plus-minus, or any stat not on the Trusted line. "
            "Do not write 'in these games' after already giving the games count in sentence 1.\n"
        )

    # When a focus player has row-level games in the payload, the validator requires "N games" in the answer.
    # Put the same constraint on the first pass that we used to add only on retry, so one Agent 2 call suffices.
    fp = _LAST_FOCUS_PLAYER
    focus_games = 0
    if _LAST_PRECOMPUTED and fp:
        focus_games = int(
            _LAST_PRECOMPUTED.get("per_player", {}).get(fp, {}).get("games") or 0
        )
    if fp and focus_games > 0:
        report_task += (
            f"\n\nFOCUS PLAYER: {fp}\n"
            f'REQUIRED: Include the phrase "{focus_games} games" when stating averages or sample size '
            "for this player (this matches precomputed_stats).\n"
        )
    if _LAST_RETRIEVAL_TOOL == TOOL_NAME_VS_TEAM and _LAST_PRECOMPUTED:
        ts = _LAST_PRECOMPUTED.get("team_series_in_payload")
        if isinstance(ts, dict) and int(ts.get("games_with_result") or 0) > 0:
            w = int(ts.get("wins") or 0)
            l = int(ts.get("losses") or 0)
            opp_l = _LAST_VS_OPPONENT_TRICODE or "this opponent"
            report_task += (
                "\n\nHEAD-TO-HEAD RECORD (mandatory):\n"
                f'You MUST state the Spurs were **{w}–{l}** vs **{opp_l}** in this database slice '
                f'(see **Trusted series** and team_series_in_payload). '
                f'If losses > 0, do NOT say they won every game or swept the series.\n'
            )
        sc_copy = _vs_team_top_scorers_copy_block(_LAST_PRECOMPUTED, top_n=3)
        if sc_copy:
            report_task += "\n\n" + sc_copy + "\n"
    report_role = (
        agent2_report_role_strict() if fp and focus_games > 0 else agent2_report_role()
    )

    print("\n--- Agent 2 (report, no tools) ---\n")
    report = agent_run(
        role=report_role,
        task=report_task,
        tools=None,
        output="text",
        model=args.model,
    )
    print(report)

    if (
        _LAST_PRECOMPUTED
        and _LAST_FOCUS_PLAYER
        and not _is_consistent_with_precomputed(report, _LAST_PRECOMPUTED, _LAST_FOCUS_PLAYER)
    ):
        print(
            "\n! Note: Report did not include the expected games count phrase for the focus player.\n",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
