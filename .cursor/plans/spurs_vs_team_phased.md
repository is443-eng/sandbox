# Spurs vs-opponent tool — phased implementation

**Status:** Implemented in-repo (nickname expansion, `spurs_games_vs_team`, prompts, `--direct-vs-team`, QUICKSTART).

Use **phase** (not step) for numbered work. No SQLite schema changes: `player_game.matchup` already uses tricodes.

## Phase 1 — Store (`spurs_season_store.py`)

- Add `_OPPONENT_NICKNAME_TO_TRICODE` and `_expand_tokens_with_opponent_nicknames`; wire into `search_player_games` after `_search_tokens`.
- Add `resolve_opponent_tricode` and `player_games_for_opponent_matchup`.

## Phase 2 — Lab (`lab_spurs_multi_agent.py`)

- Import new store helpers; `TOOL_NAME_VS_TEAM`; `spurs_games_vs_team` + tool metadata; append to `SPURS_RETRIEVAL_TOOLS`.
- Update `ROLE_AGENT_RETRIEVAL`, `tool_search_spurs_player_games` description, Agent 2 no-code lines, `_agent2_retrieval_context`.
- `main`: `--direct-vs-team`, mutual exclusion, `task` text, direct branch.

## Phase 3 — Docs

- One line in `QUICKSTART_SPURS.md` or `README_SPURS_MULTI_AGENT.md`.

## Verification

- `python3 lab_spurs_multi_agent.py --direct --direct-vs-team thunder`
- Optional full pipeline with Ollama when available.
