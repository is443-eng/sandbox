# 04_rules.R

# This script demonstrates how to use rules in an agentic workflow to make agents more precise.
# Rules are incorporated into the agent's role/system message to guide behavior.

# Load packages
library(dplyr)
library(stringr)
library(httr2)
library(jsonlite)
library(ollamar)
library(purrr)
library(lubridate)
library(yaml)

source("functions.R")

# Select model of interest
MODEL = "smollm2:135m"

# =============================================================================
# Load Rules from YAML
# =============================================================================
# Rules are structured guidance that can be incorporated into agent prompts
# to make their behavior more precise and consistent.
# Rules are defined in 04_rules.yaml for easier maintenance and version control.

# Learn more about standard AI rules formatting here: https://aicodingrules.org/

# Load in rules
rules = yaml::read_yaml("04_rules.yaml")

# Extract rules as named lists for easy access
rules_data_analysis = rules$rules$data_analysis
rules_press_release = rules$rules$press_release

# =============================================================================
# Helper Function: Format Rules for System Prompt
# =============================================================================
# This function formats a ruleset into a string that can be included in the agent's role
format_rules_for_prompt = function(ruleset) {
  paste0(
    ruleset$name, "\n",
    ruleset$description, "\n\n",
    ruleset$guidance
  )
}

# =============================================================================
# Agentic Workflow with Rules
# =============================================================================
# Same workflow as 03_agents.R, but with rules incorporated

categories = c(
  "Analgesia/Addiction", "Anesthesia", "Anti-Infective", "Antiviral",
  "Cardiovascular", "Dental", "Dermatology", "Endocrinology/Metabolism",
  "Gastroenterology", "Hematology", "Inborn Errors", "Medical Imaging",
  "Musculoskeletal", "Neurology", "Oncology", "Ophthalmology", "Other",
  "Pediatric", "Psychiatry", "Pulmonary/Allergy", "Renal", "Reproductive",
  "Rheumatology", "Total Parenteral Nutrition", "Transplant", "Urology"
)

# =============================================================================
# Workflow Execution
# =============================================================================

# Get data from an API
# data = get_shortages("Psychiatry")

# Start with an input type of medication to search
input = list(category = "Psychiatry")

# Task 1 - Function -------------------------
# Get data on drug shortages for the category of interest
data = get_shortages(category = input$category, limit = 500)
# Process the data into some summary table - eg. just the items that are currently unavailable
stat = data %>%
  group_by(generic_name) %>%
  filter(update_date == max(update_date)) %>%
  filter(availability == "Unavailable") %>%
  ungroup()
# Convert the data to a text string
result1 = df_as_text(stat)

# Task 2 - Analyst Agent -------------------------
role2_base = "Analyze medicine shortage data provide by the user in a table, and return a markdown table of currently ongoing shortages."
role2_with_rules = paste0(role2_base, "\n\n", format_rules_for_prompt(rules_data_analysis))
result2 = agent_run(role = role2_with_rules, task = result1, model = MODEL, output = "text")


# Task 3 - Press Release Agent -------------------------
role3_base = "Write a 1-page press release on the currently ongoing shortages, using the information provided by the user."
role3_with_rules = paste0(role3_base, "\n\n", format_rules_for_prompt(rules_press_release))
result3 = agent_run(role = role3_with_rules, task = result2, model = MODEL, output = "text")


# Note that the performance of the agent depends significantly on how much context you allow in one call.
# https://docs.ollama.com/context-length


# View press release
result3

# Display results
cat("=== Agent 1 Result (Data Fetch) ===\n")
print(result1)
cat("\n=== Agent 2 Result (Analysis with Rules) ===\n")
cat(result2)
cat("\n=== Agent 3 Result (Press Release with Rules) ===\n")
cat(result3)

# Clean up
# rm(list = ls())