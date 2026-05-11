# Homework 3 — submission reference (criteria, design, stats, system, usage)

This page is for instructors or peers who want **one place** with criteria, experiment design, statistics, system behavior, technical setup, and run instructions. All paths are relative to the **`sandbox`** repo; validation code lives under **`13_end2/validation/`**.

**Quick links (same file, section anchors on GitHub):**

- [Validation criteria table](#validation-criteria-table)
- [How criteria differ from the Module 9 LAB](#how-criteria-differ-from-the-module-9-lab)
- [Experimental design](#experimental-design)
- [Statistical analysis](#statistical-analysis)
- [System design](#system-design)
- [Technical details](#technical-details)
- [Usage instructions](#usage-instructions)

**Data and code on GitHub (blob URLs):**  
[Rubric source](https://github.com/is443-eng/sandbox/blob/main/13_end2/validation/rubric.py) · [Validator](https://github.com/is443-eng/sandbox/blob/main/13_end2/validation/validator.py) · [Batch validate](https://github.com/is443-eng/sandbox/blob/main/13_end2/validation/batch_validate.py) · [Scores](https://github.com/is443-eng/sandbox/blob/main/13_end2/validation/data/scores.csv) · [Reports batch](https://github.com/is443-eng/sandbox/blob/main/13_end2/validation/data/reports_batch.csv)

---

## Validation criteria table

Each dimension is produced by an **LLM judge** from **strict JSON** (see `rubric.py` for full anchor text sent in the prompt). Likert scores outside 1–5 are **clamped** before analysis so rows are kept.

| Dimension | Description (what it measures) | Scale / method | Benchmark (direction) |
|-----------|--------------------------------|----------------|------------------------|
| **factual_accuracy** | How well claims about teams, players, scores, dates, and stats match facts and the optional retrieval block. | Integer **1–5** Likert | **5** = best match to facts/sources; **1** = serious errors or fabrication risk. |
| **completeness** | Coverage of what the recap (or task) implies: outcome, flow, standouts, implied checklist. Uses **two-team** grounding when opponent rows exist (`team` ≠ SAS). | Integer **1–5** Likert | **5** = main expectations met with minor gaps only; **1** = missing core elements. |
| **structure** | Organization: flow, paragraphs, readable hierarchy. | Integer **1–5** Likert | **5** = strong, genre-appropriate structure; **1** = hard to follow. |
| **spurs_bias** | For a **neutral NBA audience**, how much tone **favors the Spurs** (homer framing, uneven blame/praise, tribal wording). **Not the same as lying**—true facts can still read biased. | Integer **1–5** Likert | **1** = professionally **neutral** (best for national tone); **5** = strongest **pro-Spurs spin** (worst for neutrality). |
| **uses_we_our_for_spurs** | Fan “we/our” voice for the Spurs where a neutral outlet would not. | **Boolean** | **`false`** aligns with neutral outlet norms. |
| **opponent_named_fairly** | Opponent referenced fairly when relevant (not diminished or wrongly omitted). | **Boolean** | **`true`** = fair treatment when the opponent matters to the story. |
| **quality_composite** (derived) | Single headline outcome for ANOVA / contrasts: mean of `factual_accuracy`, `completeness`, `structure`, and **(6 − spurs_bias)** so bias is inverted into the same “higher is better” direction as the other Likerts. | **Computed in Python** (`validator.py`) | **Higher** = better overall under this rubric. |

### How criteria differ from the Module 9 LAB

The Module 9 lab (`09_text_analysis/02_ai_quality_control.py`) uses **six** generic paragraph-quality Likerts—**accuracy, formality, faithfulness, clarity, succinctness, relevance**—plus a boolean accuracy flag, aimed at “paragraph vs data” style QA.

Homework 3 uses **four** recap-focused Likerts (**factual_accuracy, completeness, structure, spurs_bias**) and two **booleans** tuned to **sports reporting** and **this course’s Spurs RAG output**. The main departure is **`spurs_bias`**, which scores **partisan tone** explicitly (the LAB does not). **Completeness** is tied to **two-team** tables when present. The LAB’s separate **formality** and **succinctness** dimensions are **not** duplicated here; instead the rubric emphasizes **fair opponent treatment** and **fan voice** flags.

---

## Experimental design

**What was compared:** Three **Agent 2** system prompts selected with **`--gen-prompt A`**, **`B`**, or **`C`** in `lab_spurs_reporter/lab_spurs_multi_agent.py` (same retrieval path, DB, and model settings across prompts unless you change them on purpose).

| Prompt | Intent (high level) |
|--------|----------------------|
| **A** | **Baseline** — standard lab recap / fact / head-to-head roles from the Spurs multi-agent lab. |
| **B** | **Maximum supported completeness** plus **mild honest Spurs-fan color** when still truthful; explicit recap **checklist** when the retrieval supports it (see `STANDALONE_B_*` strings in `lab_spurs_multi_agent.py`). |
| **C** | **Wire-service style neutrality**, **omit when uncertain**, strict limits on **hype clichés** unless tied to a number in the block; no “we/our” fan framing (see `STANDALONE_C_*`). |

**Validation scores collected:** In the submitted batch, **`scores.csv`** contains **300** rows with a non-empty **`quality_composite`** after dropping validator errors — **100 scores per prompt (A, B, C)** — one score per generated report in **`reports_batch.csv`**.

**Optional control:** **`--recap-game-date YYYY-MM-DD`** in `run_generation_batch.py` pins which game is summarized so replicates do not drift to different “latest” games.

---

## Statistical analysis

**Primary outcome:** **`quality_composite`** (higher = better).

**Hypotheses (typical framing):**

- **Omnibus:** Mean `quality_composite` is **not the same** for all three prompt groups (at least one differs).
- **Pairwise vs baseline A:** With two non-baseline groups, use **Welch t-tests** (unequal variance allowed) **vs A** and a **Bonferroni-adjusted** alpha **≈ 0.05 / 2 = 0.025** for declaring significance on those two tests.

**Tests run (implemented in `analyze_experiment.py`):**

1. **One-way ANOVA** on `quality_composite` across `prompt_id` (three groups).
2. **One-way ANOVA** on raw **`spurs_bias`** (same grouping; on this scale **lower** = less homer tone).
3. **Welch t-tests:** **A vs B** and **A vs C** on the **primary** outcome (default `quality_composite`).
4. **Descriptive:** Pairwise means, mean differences, and **Cohen’s d** (pooled SD) for effect size language.

**Optional:** `--contrast B C` for a planned **B vs C** contrast on the same `--primary` outcome; `--primary completeness` or `--primary spurs_bias` when the hypothesis is about a **single** Likert rather than the composite.

**Results from the committed run** (`validation/data/scores.csv` as analyzed by `analyze_experiment.py`):

| Analysis | Result | Interpretation |
|----------|--------|----------------|
| ANOVA `quality_composite` | **F ≈ 14.98**, **p ≈ 6.3 × 10⁻⁷** | Strong evidence that **average composite differs** by prompt. |
| Group means (composite) | **A ≈ 3.84**, **B ≈ 3.91**, **C ≈ 3.62** (SDs ≈ 0.26–0.54) | **B** highest sample mean, **C** lowest. |
| ANOVA `spurs_bias` | **F ≈ 3.94**, **p ≈ 0.021** | Prompts also differ on **average homer tone** at α = 0.05. |
| Welch **A vs C** (composite) | **t ≈ 3.57**, **p ≈ 4.8 × 10⁻⁴** | **Significant** at Bonferroni **0.025** — **A beats C** on composite. |
| Welch **A vs B** (composite) | **t ≈ −1.64**, **p ≈ 0.10** | **Not significant** at 0.025 — cannot claim **B beats A** from this test despite B’s higher mean. |
| Descriptive **B vs C** | **Cohen’s d ≈ 0.68** | Large **descriptive** separation on composite; inferential focus stayed on baseline contrasts unless `--contrast B C` was used. |

**Plain interpretation:** The three prompts are not exchangeable on overall rubric score. Under the corrected pairwise rules against **A**, only **A vs C** is clearly significant on **`quality_composite`**; **B** is best **on average** but **not** significantly above **A** in this run.

---

## System design

**Goal:** Automatically score each AI-generated report so prompts **A / B / C** can be compared with **reproducible** numbers.

**Roles:**

1. **Writer (Agent 2)** — `lab_spurs_multi_agent.py` produces **`report_text`** (and the lab prints a retrieval block used as **`source_context`** when captured).
2. **Batch builder** — `run_generation_batch.py` runs the lab many times, writes **`reports_batch.csv`** (columns include `prompt_id`, `report_id`, `report_text`, optional `source_context`).
3. **AI reviewer (judge)** — `batch_validate.py` sends each row to `validator.py`, which calls **Ollama** or **OpenAI** with the rubric prompt from **`rubric.py`** and parses **JSON** into scores + `quality_composite`.
4. **Analysis** — `analyze_experiment.py` reads **`scores.csv`**, drops rows with validator **`error`**, and runs ANOVA / Welch / descriptive summaries.

The **reviewer never chooses the prompt**; it only **scores** whatever text is in the CSV. That separation is what makes the comparison an **experiment** on prompts rather than a single model chatting with itself.

---

## Technical details

**Repository layout (validation slice):**

```text
13_end2/
  requirements.txt          # pandas, requests, nba_api, dotenv, scipy, matplotlib, …
  .env                      # optional; not committed — create from .env.example
  validation/
    rubric.py               # anchors + build_validator_prompt()
    validator.py            # HTTP to Ollama/OpenAI, JSON parse, clamp, quality_composite
    batch_validate.py       # CSV → scores CSV
    single_validate.py      # one file / stdin
    analyze_experiment.py   # ANOVA, Welch, Bonferroni note, Cohen's d
    run_generation_batch.py # subprocess lab runs → reports_batch.csv; optional --validate --analyze
    plot_scores_boxplot.py  # PNG figure from scores
    data/
      reports_batch.csv     # inputs validated
      scores.csv            # outputs
  spurs_reporter/
    lab_spurs_multi_agent.py  # --gen-prompt A|B|C and DB tools
```

**Environment variables** (see `validation/.env.example`; load via `python-dotenv` from `13_end2/.env` if present):

| Variable | Role |
|----------|------|
| **`VALIDATION_AI_PROVIDER`** | `ollama` (default) or `openai`. |
| **`OLLAMA_HOST`** | Default `http://localhost:11434`. |
| **`OLLAMA_MODEL`** | Default `llama3.2:latest`. |
| **`OPENAI_API_KEY`** | Required if provider is `openai`. |
| **`OPENAI_MODEL`** | Default `gpt-4o-mini`. |

**API keys:** Only **OpenAI** needs a secret key in `.env` or the environment. **Ollama** uses your local daemon (no key). Do **not** commit `.env`.

**Python packages:** See `13_end2/requirements.txt` — for validation and stats you need at least **`pandas`**, **`requests`**, **`python-dotenv`**, **`scipy`**; plotting adds **`matplotlib`**. The Spurs lab also uses **`nba_api`**, **`tabulate`**, etc.

---

## Usage instructions

### 1. Install

```bash
cd /path/to/sandbox/13_end2
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure the grader

- **Ollama (easiest for graders):** Install and run Ollama; pull a model (e.g. `llama3.2`). Copy `validation/.env.example` to **`13_end2/.env`** and keep `VALIDATION_AI_PROVIDER=ollama`.
- **OpenAI:** Set `VALIDATION_AI_PROVIDER=openai` and set **`OPENAI_API_KEY`** in `13_end2/.env`.

### 3. Generate reports (optional if you already have `reports_batch.csv`)

From **`13_end2`** (adjust `-n` for replicate count per prompt):

```bash
python validation/run_generation_batch.py -n 100 --recap-game-date YYYY-MM-DD
```

Add **`--validate --analyze`** to chain scoring and stats in one go. Outputs default to **`validation/data/reports_batch.csv`** and **`validation/data/scores.csv`** (override with **`--scores-out`** / batch flags as documented in `run_generation_batch.py --help`).

### 4. Score existing reports

From **`13_end2`**:

```bash
python validation/batch_validate.py \
  -i validation/data/reports_batch.csv \
  -o validation/data/scores.csv
```

Input CSV must include **`report_text`** and **`prompt_id`** (and optionally **`source_context`**). See `batch_validate.py --help` for column overrides.

### 5. Run statistics

```bash
python validation/analyze_experiment.py --scores validation/data/scores.csv
```

Try **`--primary completeness`**, **`--primary spurs_bias`**, or **`--all-likerts`** for richer tables. Plot:

```bash
python validation/plot_scores_boxplot.py \
  --scores validation/data/scores.csv \
  -o validation/data/quality_composite_boxplot.png
```

### 6. From repo root (`sandbox/`) instead

If your shell is in **`sandbox/`** (not `13_end2/`), use the same commands with the `validation/` prefix and paths under `13_end2/` — see the main [`README.md`](README.md) in this folder for copy-paste examples.

---

*Repo default branch is **`main`**; if your fork uses another branch, replace `main` in any `github.com/.../blob/main/...` link.*
