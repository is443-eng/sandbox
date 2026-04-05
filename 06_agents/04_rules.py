# 04_rules.py
# Agent Rules with YAML
# Pairs with 04_rules.R
# Tim Fraser

# This script demonstrates how to use rules in an agentic workflow to make agents more precise.
# Rules are incorporated into the agent's role/system message to guide behavior.

# 0. SETUP ###################################

## 0.1 Load Packages #################################

from pathlib import Path

import pandas as pd  # for data manipulation
import yaml          # for reading YAML files
import requests      # for HTTP requests

# Directory where this script lives (so we find 04_rules.yaml when run from anywhere)
_SCRIPT_DIR = Path(__file__).resolve().parent

# If you haven't already, install these packages...
# pip install pandas pyyaml requests

## 0.2 Load Functions #################################

# Load helper functions for agent orchestration
from functions import agent_run, get_shortages, df_as_text

# 1. CONFIGURATION ###################################

# Select model of interest (llama3 follows "output the thing" better than smollm2)
MODEL = "llama3"

# 2. LOAD RULES FROM YAML ###################################

# Rules are structured guidance that can be incorporated into agent prompts
# to make their behavior more precise and consistent.
# Rules are defined in 04_rules.yaml for easier maintenance and version control.

# Learn more about standard AI rules formatting here: https://aicodingrules.org/

# Load in rules (from same folder as this script)
with open(_SCRIPT_DIR / "04_rules.yaml", "r") as f:
    rules = yaml.safe_load(f)

# Extract rules as dictionaries for easy access
rules_data_analysis = rules["rules"]["data_analysis"][0]
rules_press_release = rules["rules"]["press_release"][0]

# 3. HELPER FUNCTION: FORMAT RULES FOR PROMPT ###################################

def format_rules_for_prompt(ruleset):
    """
    Format a ruleset into a string that can be included in the agent's role.
    
    Parameters:
    -----------
    ruleset : dict
        A ruleset dictionary with 'name', 'description', and 'guidance' keys
    
    Returns:
    --------
    str
        Formatted rules string
    """
    
    return f"{ruleset['name']}\n{ruleset['description']}\n\n{ruleset['guidance']}"

# 4. AGENTIC WORKFLOW WITH RULES ###################################

# Same workflow as 03_agents.py, but with rules incorporated

categories = [
    "Analgesia/Addiction", "Anesthesia", "Anti-Infective", "Antiviral",
    "Cardiovascular", "Dental", "Dermatology", "Endocrinology/Metabolism",
    "Gastroenterology", "Hematology", "Inborn Errors", "Medical Imaging",
    "Musculoskeletal", "Neurology", "Oncology", "Ophthalmology", "Other",
    "Pediatric", "Psychiatry", "Pulmonary/Allergy", "Renal", "Reproductive",
    "Rheumatology", "Total Parenteral Nutrition", "Transplant", "Urology"
]

# 5. WORKFLOW EXECUTION ###################################

# Start with an input type of medication to search
input_category = {"category": "Psychiatry"}

# Task 1 - Function -------------------------
# Get data on drug shortages for the category of interest
data = get_shortages(category=input_category["category"], limit=500)

# Process the data into some summary table
# Filter for items that are currently unavailable
stat = (data
        .groupby("generic_name")
        .apply(lambda x: x.loc[x["update_date"].idxmax()])
        .reset_index(drop=True)
        .query("availability == 'Unavailable'"))

# Convert the data to a text string
result1 = df_as_text(stat)

# Task 2 - Analyst Agent with Rules -------------------------
# Base role for the analyst agent (explicit: output IS the analysis table only)
role2_base = (
    "You analyze medicine shortage data provided by the user and output a markdown table "
    "of currently ongoing shortages. Your entire reply must be the table only: first line "
    "is the header row with pipe characters (e.g. | generic_name | update_type | ... |), "
    "then a separator line, then one row per shortage. No intro text, no 'here is', no steps. "
    "Just the markdown table."
)

# Add rules to the role
role2_with_rules = f"{role2_base}\n\n{format_rules_for_prompt(rules_data_analysis)}"

# Run the agent with rules
result2 = agent_run(role=role2_with_rules, task=result1, model=MODEL, output="text")

# Task 3 - Press Release Agent with Rules -------------------------
# Base role for the press release agent (explicit: output IS the press release)
role3_base = (
    "You write a 1-page press release on the currently ongoing shortages using the "
    "information provided. Your reply must be the press release only: start with a headline "
    "(in quotes or bold), then 2-4 short paragraphs. No 'here is', no numbered lists, "
    "no description of the classification. Just the press release text."
)

# Add rules to the role
role3_with_rules = f"{role3_base}\n\n{format_rules_for_prompt(rules_press_release)}"

# Run the agent with rules
result3 = agent_run(role=role3_with_rules, task=result2, model=MODEL, output="text")

# Note that the performance of the agent depends significantly on how much context you allow in one call.
# https://docs.ollama.com/context-length

# 6. DISPLAY RESULTS ###################################

# View press release
print("📰 Press Release:")
print(result3)
print()

# Display all results
print("=== Agent 1 Result (Data Fetch) ===")
print(result1)
print()

print("=== Agent 2 Result (Analysis with Rules) ===")
print(result2)
print()

print("=== Agent 3 Result (Press Release with Rules) ===")
print(result3)
