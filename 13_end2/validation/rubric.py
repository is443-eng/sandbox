"""
Homework 3: custom validation rubric (four 1–5 Likerts + optional booleans).
Differs from LAB (`09_text_analysis/02_ai_quality_control.py`) by dimensions and anchors.
"""

from __future__ import annotations

# JSON keys expected from the model (integers 1–5; booleans for optional checks)
LIKERT_KEYS = ("factual_accuracy", "completeness", "structure", "spurs_bias")
BOOLEAN_KEYS = ("uses_we_our_for_spurs", "opponent_named_fairly")

# spurs_bias: 5 = strongest pro-Spurs / homer tone; 1 = most neutral

RUBRIC_LIKERT_ANCHORS = """
### factual_accuracy (integer 1–5)
How well claims about teams, players, scores, dates, and statistics match facts (and provided source text if included).

| Score | Meaning |
|-------|---------|
| 1 | Major factual errors or fabricated outcomes; wrong teams/scores. |
| 2 | Several clear errors; specifics untrustworthy. |
| 3 | Mostly plausible with minor slips or vagueness that avoids falsifiability. |
| 4 | No errors noticed; small omissions only. |
| 5 | Precise and consistent with facts/sources throughout. |

### completeness (integer 1–5)
Coverage of what the task implies (result, turning points, standouts, requested context).

| Score | Meaning |
|-------|---------|
| 1 | Missing core elements (e.g. no outcome or no substantive answer). |
| 2 | Sparse; large gaps relative to the brief. |
| 3 | Adequate but uneven. |
| 4 | Covers main expectations with minor gaps. |
| 5 | Fully addresses the implied checklist. |

### structure (integer 1–5)
Organization: flow, sections/paragraphs, readable hierarchy (not an unreadable wall unless required).

| Score | Meaning |
|-------|---------|
| 1 | Disorganized; hard to follow. |
| 2 | Followable but messy ordering or repetition. |
| 3 | Acceptable with weak transitions. |
| 4 | Clear sections/progression; minor polish issues. |
| 5 | Strong hierarchy appropriate to the genre. |

### spurs_bias (integer 1–5)
For a **general or neutral NBA audience**, how much the tone **favors the San Antonio Spurs** (homer framing, cheerleading, uneven blame/praise, inappropriate "we/our", opponent diminished). **Higher = more Spurs bias** (5 = most biased; 1 = professionally neutral).

| Score | Meaning |
|-------|---------|
| 1 | Professionally neutral—fair to both sides; proportional praise/criticism. |
| 2 | Mostly neutral; isolated fan slips. |
| 3 | Mild tilt toward Spurs; some partisan coloring. |
| 4 | Noticeable lean toward Spurs in framing or word choice. |
| 5 | Markedly homer: persistent pro-Spurs spin, excuse-making, tribal tone. |

**Overlap note:** High factual_accuracy can co-occur with high spurs_bias (true facts framed in a partisan way).
"""

BOOLEAN_INSTRUCTIONS = """
Also set these booleans from the report text:
- **uses_we_our_for_spurs**: true if the author uses "we", "our", or equivalent fan voice for the Spurs where a neutral outlet would not.
- **opponent_named_fairly**: true if the opposing team is referenced fairly (not consistently diminished or unnamed when relevant); false if unfair or absent when needed.
"""


def build_validator_prompt(
    report_text: str,
    source_context: str | None = None,
) -> str:
    """Build the full user message for the validation model."""
    src = ""
    if source_context and source_context.strip():
        src = (
            "\n\n--- Source text / retrieval block for factual checks (optional):\n"
            f"{source_context.strip()}\n"
        )
    return f"""You are a validation reviewer for AI-generated sports reports. Apply ONLY the rubric below.
Return **one JSON object** with the exact keys specified—no markdown fences, no extra keys.

Report to evaluate:
---
{report_text.strip()}
---{src}

{RUBRIC_LIKERT_ANCHORS}

{BOOLEAN_INSTRUCTIONS}

Return valid JSON in this **exact** shape (all keys required):
{{
  "factual_accuracy": <int 1-5>,
  "completeness": <int 1-5>,
  "structure": <int 1-5>,
  "spurs_bias": <int 1-5>,
  "uses_we_our_for_spurs": <true or false>,
  "opponent_named_fairly": <true or false>,
  "details": "<brief justification, under 80 words>"
}}
"""
