# Spurs multi-agent lab — step-by-step walkthrough

This file tracks the **incremental build** for [LAB_multi_agent_with_tools.md](LAB_multi_agent_with_tools.md), using the **Spurs season SQLite** stack in this folder (`spurs_season_store.py`, `data/spurs_season.db`). Complete each step and check it off before moving on.

---

## Overview

**Goal:** One script under `08_function_calling/` that (1) exposes a **custom tool** wrapping `search_player_games`, (2) runs **Agent 1** with `agent_run()` + tools to retrieve rows, (3) runs **Agent 2** with `agent_run()` without tools to produce a written report, using `agent_run()` from [`functions.py`](functions.py).

**Prerequisite:** A populated database (run from **`08_function_calling`**):

```bash
cd 08_function_calling
python spurs_season_rag.py --refresh --season 2025-26
```

Adjust `--season` if your course uses another year.

---

## Step 1 — Skeleton and DB smoke test

**Do:**

- Add a new Python file in `08_function_calling/` (e.g. `lab_spurs_multi_agent.py`).
- Ensure this folder (`08_function_calling`) is on `sys.path` so you can import `connect`, `search_player_games` from `spurs_season_store` (same directory as the lab script).
- Parse CLI args: at minimum `--db` (default: path to `data/spurs_season.db` under this folder) and `--query` (test string).
- Open the DB, call `search_player_games` directly, print a small preview (e.g. first 5 rows). **No Ollama yet.**

**Checkpoint:** Running the script prints real rows; exit gracefully if the DB is empty (tell user to run `--refresh`).

---

## Step 2 — Tool function + metadata (no `agent_run`)

**Do:**

- Define **`search_spurs_player_games(query, limit)`** (name can match your script) in **module global scope** so [`agent()`](functions.py) can resolve it when tools run.
- Inside: `connect` → `search_player_games` → return a **string** (markdown table via `to_markdown` or compact JSON). Close the connection safely.
- Beside it, define **Ollama-style tool metadata**: `name`, `description`, `parameters` (`query` string, `limit` integer; cap `limit` in code if needed).

**Checkpoint:** From `main`, call the function directly with a test `query`/`limit` and print the string. No LLM.

---

## Step 3 — Agent 1 (retrieval only)

**Do:**

- `from functions import agent_run` (use the copy in **`08_function_calling/functions.py`**).
- System prompt: retrieval assistant that **must** call the tool to obtain game rows; do not invent stats.
- User message: the natural-language question (CLI `--query` or similar).
- `agent_run(..., tools=[your_tool_dict], output="text", model=...)`.

**Checkpoint:** Terminal shows tool execution and the returned table/text. If the model does not call the tool, tighten the system prompt or try another local Ollama model.

---

## Step 4 — Agent 2 (report) + chain

**Do:**

- Second `agent_run` with **`tools=None`**.
- System prompt: Spurs analyst; you only have the retrieved data below; write a concise, readable answer; say if data is empty or thin.
- User/task message: repeat the original question and paste **Agent 1’s output** (the tool return string).
- Print two clearly labeled blocks, e.g. `--- Agent 1 (tool output) ---` and `--- Agent 2 (report) ---`, for an easy submission screenshot.

**Checkpoint:** Two distinct outputs: raw retrieval string, then narrative report.

---

## Step 5 — Submit

**Do:**

- Run end-to-end; adjust prompts or caps if needed.
- **Submit per the lab:** the complete script, a **screenshot** showing both agent outputs, and **2–3 sentences** explaining the tool and the two-agent workflow.

---

## Reference — example question types

Natural-language questions should be answerable from **your** `player_game` rows, e.g. player name or matchup keywords: “Wembanyama scoring in March”, “Fox assists”, “Spurs vs Boston box score lines”. The **tool** is always **SQLite search**, not a live NBA API call at question time.

---

## Optional later improvements

- Add `--model` and default aligned with your other scripts (`llama3`, `smollm2`, etc.).
- Reuse deterministic aggregates from `spurs_season_rag.py` only if you want stricter math (not required for the minimal two-agent lab).

← [LAB: Multi-Agent System with Tools](LAB_multi_agent_with_tools.md)
