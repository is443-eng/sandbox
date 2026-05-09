# Spurs stack dependencies

Python packages for **`spurs_season_store.py`**, **`spurs_season_rag.py`**, and **`lab_spurs_multi_agent.py`** (SQLite + NBA API + optional Ollama).

---

## Overview

- **`../requirements.txt`** (under `13_end2/`) — pinned minimum versions for **pandas**, **tabulate**, **requests**, and **nba_api**.
- **Ollama** is separate: install the app locally and pull a model; **`functions.py`** talks to `http://localhost:11434` by default.

---

## Install (recommended: virtual environment)

From this directory:

```bash
cd 13_end2/spurs_reporter
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r ../requirements.txt
```

---

## Packages

| Package | Role |
|---------|------|
| **pandas** | DataFrames for SQL results and box-score tables. |
| **tabulate** | Required for **`DataFrame.to_markdown()`** (used by the multi-agent lab tool output). |
| **requests** | HTTP for Ollama in **`functions.py`** (and any HTTPS helpers). |
| **nba_api** | League and box score endpoints for **`refresh_from_api`**. |

---

## Ollama

- Install [Ollama](https://ollama.com/) and start the service.
- Pull a tag your scripts use; **`functions.py`** defaults to **`llama3.2`** (tool-capable in Ollama). Plain **`llama3`** often returns **HTTP 400** when tools are used. Override with **`--model`** (e.g. **`smollm2:1.7b`**).

---

## Related docs

- **`QUICKSTART_SPURS.md`** — How to run the lab with examples (assumes deps and DB are ready).
- **`README_SPURS_MULTI_AGENT.md`** — Multi-agent lab: tools, data, CLI, edge cases, and homework link checklist.
