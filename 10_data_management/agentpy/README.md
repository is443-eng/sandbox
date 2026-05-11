![Banner Image](../docs/images/icons.png)

# README `10_data_management/agentpy`

> A **disaster situational brief agent**: a bounded **FastAPI** + **Ollama** loop for **coordination / resilience** roles—morning-style snapshots of a **user-specified ongoing disaster** and **follow-ups** (neighborhoods, time windows, lifelines). Uses **`AGENT.md`**, **`skills/`**, optional **web search** (Serper), and **plain HTTP JSON**—no Slack or Telegram required. **Not** a substitute for official ICS or field reporting.

**FastAPI entrypoint:** [`../app.py`](../app.py) (`uvicorn app:app` from **`10_data_management/`**). **Implementation package:** [`../agent_backend/`](../agent_backend/) — [`api.py`](../agent_backend/api.py) (HTTP surface), [`loop.py`](../agent_backend/loop.py) (Ollama **`/api/chat`** + tool loop), [`guardrails.py`](../agent_backend/guardrails.py) (limits + safe paths), [`context.py`](../agent_backend/context.py) (**`AGENT.md`** + skill list), [`tools.py`](../agent_backend/tools.py) (**`read_skill`**, **`web_search`** via [Serper](https://serper.dev)), [`logging_setup.py`](../agent_backend/logging_setup.py) (optional turn trace file).

---

## Table of Contents

- [Quick start](#quick-start)
- [Helper scripts](#helper-scripts)
- [Architecture](#architecture)
- [HTTP contract](#http-contract)
- [Guardrails](#guardrails)
- [Project structure](#project-structure)
- [Activities](#activities)
- [Readings](#readings)

---

## Quick start

- Copy [`.env.example`](.env.example) → `.env` and set **`OLLAMA_API_KEY`**. Defaults target **Ollama Cloud** (`OLLAMA_HOST=https://ollama.com`, `OLLAMA_MODEL=nemotron-3-nano:30b-cloud`). Confirm the exact cloud tag in the [Ollama model library](https://ollama.com/library) if your key rejects a name.
- Optional: set **`SERPER_API_KEY`** for live search (see [Serper](https://serper.dev)). Preflight and the **`web_search`** tool use [CrewAI](https://docs.crewai.com/) **`SerperDevTool`** (`pip` installs **`crewai[tools]`**—heavier than `httpx` alone). Without a key, preflight and the tool return a “search disabled” message; **`AGENT.md`** instructs the model not to invent URLs.
- `pip install -r` [`requirements.txt`](requirements.txt)
- From **`10_data_management/`** (parent of this folder): `python -m uvicorn app:app --host 0.0.0.0 --port 8000`, or run **`./runme.sh`** from this folder (it `cd`s up and starts **`app:app`**).
- `GET http://127.0.0.1:8000/health` → should report `"ok": true` plus **`max_autonomous_turns`**, **`min_completion_turns`**, and related fields.
- Optional: watch turn-by-turn activity in **`logs/agent.log`** (default when **`AGENT_LOG_FILE`** is unset; see [Guardrails](#guardrails)).
- `POST http://127.0.0.1:8000/hooks/agent` with JSON `{"task": "Disaster snapshot or follow-up (incident, area, time window)"}` (no auth header).

---

## Helper scripts

Same idea as [`08_function_calling/mcp_fastapi/`](../../08_function_calling/mcp_fastapi/) (Python) and [`04_deployment/positconnect/fastapi/`](../../04_deployment/positconnect/fastapi/) (shell): small wrappers so you do not retype paths.

| Script | What it does |
|--------|----------------|
| [`runme.sh`](runme.sh) | `cd` to **`10_data_management/`** and run **`python -m uvicorn app:app`** on port **8000** |
| [`testme.py`](testme.py) | After deploy: **`GET /health`** and **`POST /hooks/agent`** against **`AGENT_PUBLIC_URL`** in **`.env`** |
| [`manifestme.sh`](manifestme.sh) | From **`10_data_management/`**: **`rsconnect write-manifest fastapi`** with **`--entrypoint app:app`** |
| [`deployme.sh`](deployme.sh) | **`rsconnect deploy fastapi`** (bundle root **`10_data_management/`**, **`app:app`**) using **`CONNECT_*`** from **`agentpy/.env`** |

On macOS/Linux, make the shell scripts executable once: `chmod +x *.sh`.

---

## Architecture

```mermaid
sequenceDiagram
  participant Client
  participant FastAPI
  participant Loop
  participant OllamaCloud
  participant Tools
  participant Disk
  participant Serper

  Client->>FastAPI: POST /hooks/agent JSON
  FastAPI->>Loop: run_research_loop
  Loop->>Disk: AGENT.md + skills index
  Loop->>OllamaCloud: POST /api/chat with tools
  OllamaCloud-->>Loop: assistant, optional tool_calls
  Loop->>Tools: read_skill / web_search
  Tools->>Disk: skills/*.md
  Tools->>Serper: POST search when SERPER_API_KEY set
  Loop->>OllamaCloud: follow-up messages until END_BRIEF or turn cap
  FastAPI-->>Client: status, reply, turns_used, turn_cap, min_completion_turns, prefetch_search_used, forced_tool_round, session_id
```

- **`../app.py`** — Re-exports the FastAPI **`app`** from **`agent_backend.api`** (use **`app:app`** with uvicorn / Connect).
- **`agent_backend/api.py`** — FastAPI **`app`**: **`GET /health`**, **`POST /hooks/agent`**, **`POST /hooks/control`**. Imports **`run_research_loop`** from **`loop.py`**; startup configures optional file logging.
- **`agent_backend/loop.py`** — Bounded Ollama **`/api/chat`** with **[tool calling](https://docs.ollama.com/capabilities/tool-calling)** (**`read_skill`**, **`web_search`**). Each model round counts toward the same cap (**`MAX_AUTONOMOUS_TURNS`**, **10** server-wide; optional lower **`max_turns`** per request) until **`END_BRIEF`** or **`paused_for_human`** + **`resume_token`**. Emits **`agent`** logger lines per turn (tool names, previews, outcomes).
- **`agent_backend/context.py`** — Loads **[`AGENT.md`](AGENT.md)** (fallback string if missing) and appends a list of loadable **`skills/*.md`** names to the system message.
- **`agent_backend/tools.py`** — Implements tools and truncates tool payloads (~**4k** chars). **`web_search`** uses CrewAI **`SerperDevTool`** and **`SERPER_API_KEY`**; **`read_skill`** uses **`guardrails.read_skill_file`**.
- **`agent_backend/guardrails.py`** — **`MAX_AUTONOMOUS_TURNS`** (**10**), **`MAX_WEB_SEARCHES_PER_REQUEST`** (**3**), **`MAX_SKILL_READS_PER_REQUEST`** (**8**), task size, safe **`skills/`** reads. Activity root = this **`agentpy/`** folder (where **`AGENT.md`** lives).
- **`agent_backend/logging_setup.py`** — Optional **`logs/agent.log`** (or path from **`AGENT_LOG_FILE`**); disable with **`AGENT_LOG_FILE=0`** (or **`off`** / empty). **`AGENT_LOG_LEVEL`** defaults to **`INFO`**. Task text may appear in logs—do not log in production with sensitive prompts unless you accept that risk.

For local-only development without a cloud key, point **`OLLAMA_HOST`** at **`http://127.0.0.1:11434`** and use a pulled local model name (optional path—your instructor may require cloud only).

---

## HTTP contract

**`POST /hooks/agent`**

| Field | Required | Meaning |
|--------|-----------|---------|
| `task` | yes | Disaster situational request or continuation after a pause |
| `session_id` | no | Stable id for follow-up; omit to start new |
| `resume_token` | if paused | Must match server token from `paused_for_human` |
| `max_turns` | no | Integer **1…`MAX_AUTONOMOUS_TURNS`** (currently **10**); caps LLM round-trips for this request. Omit = use full server cap. Over the cap → **422** validation error. |

**Response (JSON):**

- `status`: **`ok`** | **`paused_for_human`** | **`error`**
- `reply`: assistant text ( **`END_BRIEF`** line stripped on success )
- `turns_used`: **Ollama `/api/chat`** round-trips in **this** HTTP request (including tool follow-ups); does **not** count the server’s Serper preflight.
- `turn_cap`: Effective maximum turns allowed for this request (same as **`clamp_turns(max_turns)`**; **`GET /health`** exposes **`max_autonomous_turns`**).
- `min_completion_turns`: Minimum LLM rounds before **`END_BRIEF`** is honored (default **2** when **`SERPER_API_KEY`** is set, else **1**; override with **`AGENT_MIN_COMPLETION_TURNS`**). Capped by **`turn_cap`** for this request.
- `prefetch_search_used`: whether an automatic preflight search ran (uses one slot of **`MAX_WEB_SEARCHES_PER_REQUEST`** when enabled).
- `forced_tool_round`: whether the server injected a **`read_skill`** tool turn before the first LLM call (default **on** for new sessions; see **`AGENT_FORCE_FIRST_TOOL`** / **`AGENT_FORCE_FIRST_SKILL`**).
- `session_id`: echoed or assigned
- `resume_token`: present when paused
- `detail`: error or pause explanation

**`POST /hooks/control`** — body `{"action":"start"}` or `{"action":"stop"}` toggles whether new agent work runs (**503** when stopped).

---

## Guardrails

- **Turn cap**: [`../agent_backend/guardrails.py`](../agent_backend/guardrails.py) exports **`MAX_AUTONOMOUS_TURNS`** (**10**). Clients may send a lower **`max_turns`** on each **`POST /hooks/agent`** (validated ≤ that maximum). Every **`/api/chat`** round in one HTTP call counts toward that budget (including tool follow-ups). The loop stops early when the model includes **`END_BRIEF`** **and** at least **`min_completion_turns`** rounds have run; otherwise it sends a **verification** user nudge (see **`AGENT_MIN_COMPLETION_TURNS`** / Serper default).
- **Tool caps**: **`MAX_WEB_SEARCHES_PER_REQUEST`** (**3**) and **`MAX_SKILL_READS_PER_REQUEST`** (**8**); the default **preflight** uses one search when **`AGENT_PREFETCH_WEB_SEARCH`** is on; further **`web_search`** tool calls share the same cap. By default, **`AGENT_FORCE_FIRST_TOOL`** injects one **`read_skill`** before the first LLM call on a **new** session (uses one skill read).
- **Instructions**: edit **[`AGENT.md`](AGENT.md)** for role, output shape, and tool policy—no need to change Python for prose.
- **Skills**: add **`*.md`** under [`skills/`](skills/) (see [`skills/README.md`](skills/README.md)); the model can load them with **`read_skill`** (basename must match **`^[a-zA-Z0-9_-]+\.md$`**).
- **Turn trace log**: by default the server appends to **`logs/agent.log`** under this folder (gitignored). Set **`AGENT_LOG_FILE`** to a relative or absolute path to override, or to **`0`** / **`off`** / **`false`** / **`no`** / empty string to disable file logging. **`AGENT_LOG_LEVEL`** (e.g. **`DEBUG`**) adjusts verbosity. **Secrets:** **`OLLAMA_API_KEY`** and **`SERPER_API_KEY`** are never written to this log; previews of task, tool args, tool results, assistant text, and Ollama errors are passed through a small redaction step (e.g. **`Bearer …`**, **`sk-…`**, obvious **`api_key=`** patterns). Do not rely on redaction alone—avoid pasting live keys into **`task`**.
- **Secrets**: never commit **`.env`**; on **Posit Connect**, set **`OLLAMA_API_KEY`** and optional **`SERPER_API_KEY`** in the server environment.

---

## Project structure

| Path | Role |
|------|------|
| [`../app.py`](../app.py) | Uvicorn / Connect entrypoint (`python -m uvicorn app:app` from **`10_data_management/`**) |
| [`../agent_backend/api.py`](../agent_backend/api.py) | FastAPI **`app`** object |
| [`../agent_backend/loop.py`](../agent_backend/loop.py) | Ollama **`/api/chat`** loop + tool rounds + **`agent`** logger |
| [`../agent_backend/guardrails.py`](../agent_backend/guardrails.py) | Turn cap, tool caps, **`skills/`** read policy |
| [`../agent_backend/context.py`](../agent_backend/context.py) | Load **`AGENT.md`**, list skills for system prompt |
| [`../agent_backend/tools.py`](../agent_backend/tools.py) | **`read_skill`**, **`web_search`** (CrewAI **SerperDevTool**) |
| [`../agent_backend/logging_setup.py`](../agent_backend/logging_setup.py) | Optional **`logs/agent.log`** file handler |
| [`../requirements.txt`](../requirements.txt) | Python deps (also at module root for Connect bundle) |
| [`AGENT.md`](AGENT.md) | System instructions (editable) |
| [`skills/`](skills/) | Markdown skills loaded via **`read_skill`** |
| [`logs/`](logs/) | Default turn trace log directory (gitignored except **`.gitkeep`**) |
| [`.env.example`](.env.example) | Env template |
| [`runme.sh`](runme.sh), [`manifestme.sh`](manifestme.sh), [`deployme.sh`](deployme.sh) | Local uvicorn + Posit Connect deploy |
| [`testme.py`](testme.py) | Smoke test the **deployed** URL (**`AGENT_PUBLIC_URL`**) |

---

## Activities

Module activities live in the parent **[`10_data_management/`](../)** folder and cover **either** Python (**this folder**) or R (**[`agentr/`](../agentr/)**). Complete in order:

1. [ACTIVITY: Run the Autonomous Agent Locally](../ACTIVITY_agent_local.md) — **Python track:** use the files below; **R track:** see **[`agentr/README.md`](../agentr/README.md)**.
   - [`../app.py`](../app.py) — FastAPI entrypoint (**`app:app`**)
   - [`../agent_backend/loop.py`](../agent_backend/loop.py) — bounded situational brief loop (Ollama + tools)
   - [`../agent_backend/guardrails.py`](../agent_backend/guardrails.py) — turn cap and path rules
   - [`requirements.txt`](requirements.txt) — dependencies
   - [`.env.example`](.env.example) — environment template
   - [`runme.sh`](runme.sh) — local server
2. [LAB: Deploy the Autonomous Agent](../LAB_agent_deploy.md) — **Python track:** [`manifestme.sh`](manifestme.sh), [`deployme.sh`](deployme.sh), [`testme.py`](testme.py); **R track:** [`agentr/deployme.R`](../agentr/deployme.R), [`agentr/testme.R`](../agentr/testme.R) from repo root (see **[`agentr/README.md`](../agentr/README.md)**).

---

## Readings

- None.

---

![Footer Image](../docs/images/icons.png)

---

← 🏠 [Back to Top](#Table-of-Contents)
