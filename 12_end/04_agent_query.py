# 04_agent_query.py
# Agent with REST Tool Call
# Pairs with 04_agent_query.R
# Tim Fraser

import sys
import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR / "08_function_calling"))

from dotenv import load_dotenv
from functions import agent

import requests

# 1. CONFIG ###################################

load_dotenv(ROOT_DIR / "12_end" / ".env")

ENDPOINT_URL = os.getenv("API_PUBLIC_URL", "http://localhost:8000").rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "smollm2:1.7b")

UNIT_NOTE = "vehicles observed in one representative minute (1m/t1 interval) within the requested hour and day of week"

# 2. DEFINE TOOL FUNCTION ###################################

def predict_vehicle_count(day_of_week, hours_of_day):
    hours = [int(h) for h in hours_of_day if 0 <= int(h) <= 23]
    if not hours:
        raise ValueError("hours_of_day must contain at least one integer between 0 and 23.")

    predictions = []
    for hour in hours:
        resp = requests.get(
            f"{ENDPOINT_URL}/predict",
            params={"day_of_week": int(day_of_week), "hour_of_day": hour},
            timeout=10,
        )
        resp.raise_for_status()
        predictions.append(
            {
                "hour_of_day": hour,
                "predicted_vehicle_count": float(resp.json()["predicted_vehicle_count"]),
            }
        )

    return {
        "day_of_week": int(day_of_week),
        "unit": "vehicles_observed_in_one_minute",
        "interval": "1m_t1",
        "note": "Each prediction is for one representative minute within that hour and day of week.",
        "predictions": predictions,
    }

# 3. DEFINE TOOL METADATA ###################################

tool_predict_vehicle_count = {
    "type": "function",
    "function": {
        "name": "predict_vehicle_count",
        "description": (
            "Predict Brussels vehicle count for a specific day of week and vector of hours. "
            "Returns one estimated vehicle count per requested hour. "
            "Each value is for one representative minute (1m/t1 interval) within that hour on that day of week."
        ),
        "parameters": {
            "type": "object",
            "required": ["day_of_week", "hours_of_day"],
            "properties": {
                "day_of_week": {"type": "integer", "description": "Day of week (1=Monday, ..., 7=Sunday)"},
                "hours_of_day": {
                    "type": "array",
                    "description": "Vector of hours to predict (0-23), e.g. [8] or [0,1,2,...,23].",
                    "items": {"type": "integer"},
                },
            }
        }
    }
}

tools = [tool_predict_vehicle_count]

SYSTEM_PROMPT = (
    "You are a Brussels traffic assistant. "
    "Always report units clearly as vehicles observed in one representative minute "
    "(1m/t1 interval) within the requested hour and day of week. "
    "Call predict_vehicle_count using day_of_week and hours_of_day vector."
)


def run_agent_round(user_prompt: str):
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    return agent(
        messages=messages,
        model=MODEL,
        output="text",
        tools=tools,
    )


# 4. RUN AGENT (two prompts per ACTIVITY_agent_query.md) ###################################

print("--- Prompt 1: Monday 8 AM ---")
result1 = run_agent_round("Predict Brussels vehicle count for Monday at 8 AM.")
print("Agent result:", result1)

print("\n--- Prompt 2: Wednesday 5 PM ---")
result2 = run_agent_round("Predict Brussels vehicle count for Wednesday at 5 PM.")
print("Agent result:", result2)

# 5. VERIFY (direct API vs agent Monday 8 AM scenario) ###################################

direct = predict_vehicle_count(day_of_week=1, hours_of_day=[8])
print("\nDirect API call predictions returned:", len(direct["predictions"]))
print(
    "Direct API call sample (Monday 08:00):",
    direct["predictions"][0]["predicted_vehicle_count"],
    "(1m/t1)",
)
print("Unit:", UNIT_NOTE)
match_val = str(direct["predictions"][0]["predicted_vehicle_count"])
print("Match:", match_val in str(result1))
