# Quick start: Spurs multi-agent lab

Assumes **Python 3**, **`08_function_calling/.venv`** (optional), **dependencies installed**, **Ollama running**, a **tool-capable model** pulled (e.g. `llama3.2`), and **`data/spurs_season.db`** already filled. If the DB is missing or empty, run **`python3 spurs_season_rag.py --refresh --season 2025-26`** once from this folder (needs network).

---

## 1. Go to the folder and activate the venv

**Replace the path** below with your real clone of the repo.

```bash
cd /Users/YOU/Documents/sandbox/08_function_calling
source .venv/bin/activate    # Windows: .venv\Scripts\activate
```

If you are already in `08_function_calling` in the terminal, you can skip `cd` and only run `source .venv/bin/activate`.

---

## 2. Full run (Agent 1 + Agent 2)

Ollama must be up; the script uses the default model in **`functions.py`** unless you pass **`--model`**.

**Keyword search (Fox):**

```bash
python3 lab_spurs_multi_agent.py --limit 50 "How has Fox been playing?"
```

**Month + player (model should pick the month tool):**

```bash
python3 lab_spurs_multi_agent.py "How did Wembanyama score in March 2026?"
```

**Game recap (model should pick the recap tool):**

```bash
python3 lab_spurs_multi_agent.py "Give me a quick recap of the last game in the database"
```

**Head-to-head vs one team (model should use `spurs_games_vs_team`; `matchup` in the DB uses tricodes like OKC):**

```bash
python3 lab_spurs_multi_agent.py "How did the Spurs play against the Thunder this year?"
```

Answers and row counts reflect **whatever is loaded** in `data/spurs_season.db` (often not all 82 games until you refresh). To pull the latest Spurs games from the NBA API: `python3 spurs_season_rag.py --refresh --season 2025-26` (adjust season id to match your DB).

**Explicit model:**

```bash
python3 lab_spurs_multi_agent.py --model llama3.2 "Wembanyama blocks this season"
```

---

## 3. Direct mode (tools only, no LLM)

Use **`--direct`** to call **one** tool without Agent 1/2. Good for checking the DB and markdown output.

**Search tool:**

```bash
python3 lab_spurs_multi_agent.py --direct --limit 10 "Wembanyama"
```

**Month tool (year, month, player substring):**

```bash
python3 lab_spurs_multi_agent.py --direct --direct-month 2026 3 Wembanyama --limit 20 "context"
```

**Recap tool — latest game:**

```bash
python3 lab_spurs_multi_agent.py --direct --direct-recap --limit 25 "recap"
```

**Recap tool — one date:**

```bash
python3 lab_spurs_multi_agent.py --direct --direct-recap 2026-04-04
```

**Vs one opponent (nickname or tricode):**

```bash
python3 lab_spurs_multi_agent.py --direct --direct-vs-team thunder
```

Use at most one of **`--direct-month`**, **`--direct-recap`**, or **`--direct-vs-team`** per run.

---

## 4. Optional flags

| Flag | Example |
|------|---------|
| Custom DB | `--db /path/to/spurs_season.db` |
| NBA season filter (must match DB metadata if present) | `--season 2025-26` |

---

## 5. What you should see

1. Lines printing **Database**, **NBA season**, row counts, and **Tools:** …  
2. **Agent 1** — tool output: markdown table, **`precomputed_stats`** JSON, sometimes a **Trusted line**.  
3. **Agent 2** — a short natural-language answer grounded in that block.

**Tip:** For a **narrow** question (e.g. one player’s PPG), pass a modest **`--limit`** (e.g. `50` or `100`) so Agent 2 does not receive thousands of rows. Answers must use the table and **`precomputed_stats`** only — not invented SQL or fake table names.

More detail: **[README_SPURS_MULTI_AGENT.md](README_SPURS_MULTI_AGENT.md)**.
