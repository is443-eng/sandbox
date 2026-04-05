# 08_lab – Spurs Game Two-Agent Recap

Self-contained copy of the San Antonio Spurs game summary app. Fetches the most recent Spurs game via **nba_api**, then runs a two-agent chain (analyst → writer) to produce a sectioned recap.

## Files

| File | Purpose |
|------|--------|
| `spurs_game_agents.py` | Main script: fetches game, runs Agent 1 (summary) and Agent 2 (sectioned recap). |
| `spurs_utils.py` | NBA data helpers: most recent game, box score (V3/V2), text formatting. |
| `functions.py` | Shared agent helpers: `agent_run`, Ollama chat. |

## Prerequisites

- Python 3 with pip
- **Ollama** running locally with a model (e.g. `llama3`): `ollama pull llama3`
- Network access for nba_api and Ollama

## Setup

```bash
pip install -r requirements.txt
```

## Run

From the repo root (sandbox):

```bash
python3 06_agents/08_lab/spurs_game_agents.py
```

Or from inside the lab folder:

```bash
cd 06_agents/08_lab
python3 spurs_game_agents.py
```

## Behavior

- **Most recent game has box score:** Full two-agent recap (summary + Overview / Key Players / Key Moments / Turning Points).
- **Most recent game has no box score:** Team-only 3-sentence summary, then full recap for the most recent game that does have box score data.
