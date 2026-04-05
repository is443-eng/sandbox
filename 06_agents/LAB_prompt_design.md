# 📌 LAB

## Design Effective Prompts for Multi-Agent Systems

🕒 *Estimated Time: 30-45 minutes*

---

## 📋 Lab Overview

Design and implement a multi-agent system with 2-3 agents working together. Create effective system prompts for each agent, test the workflow, and iterate to improve prompt design. This lab focuses on multi-agent orchestration and prompt engineering, distinct from single-agent data reporting.

---

## ✅ Your Tasks

### Task 1: Design Your Multi-Agent System

- [ ] Choose a task that requires multiple steps (e.g., data analysis → report writing → formatting)
- [ ] Design 2-3 agents, each with a specific role:
  - Agent 1: What is its primary function?
  - Agent 2: What does it receive from Agent 1 and what does it produce?
  - Agent 3 (optional): What is its role in the workflow?
- [ ] Sketch the workflow: how information flows between agents

### Task 2: Create System Prompts

- [ ] Write a system prompt for each agent:
  - Define the agent's role clearly
  - Specify what format the agent should produce
  - Include any constraints or requirements
- [ ] Use [`02_using_ollamar.R`](02_using_ollamar.R) and [`03_agents.R`](03_agents.R) as reference
- [ ] Consider using rules (see [`04_rules.yaml`](04_rules.yaml)) if helpful for structure

### Task 3: Test and Iterate

- [ ] Implement your multi-agent workflow using [`functions.R`](functions.R) helper functions
- [ ] Run the workflow and observe each agent's output
- [ ] Identify issues: Are prompts clear enough? Is the output format correct?
- [ ] Refine your system prompts based on results:
  - Add more specific instructions if outputs are too vague
  - Clarify format requirements if outputs don't match expectations
  - Adjust role definitions if agents aren't behaving as intended
- [ ] Test 2-3 iterations until the workflow produces reliable results
- [ ] Document your prompt design choices: What worked? What didn't? Why?

---

## 💡 Tips and Resources

- **System Prompt Design**: Be specific about roles, formats, and constraints. Examples: "You are a data analyst. Always return results as a markdown table with clear headers."
- **Agent Chaining**: Ensure each agent's output format matches what the next agent expects as input
- **Iteration**: Start with simple prompts, then add detail based on actual outputs
- **Reference Files**: 
  - [`02_using_ollamar.R`](02_using_ollamar.R) or [`02_using_ollama.py`](02_using_ollama.py) — Basic system prompts
  - [`03_agents.R`](03_agents.R) or [`03_agents.py`](03_agents.py) — Multi-agent workflow example
  - [`04_rules.R`](04_rules.R) or [`04_rules.py`](04_rules.py) and [`04_rules.yaml`](04_rules.yaml) — Using rules for structure
  - [`functions.R`](functions.R) or [`functions.py`](functions.py) — Helper functions for agent orchestration
- **Distinction from Data Reporter Lab**: This lab focuses on **multi-agent orchestration** and **prompt design for workflows**, not single-agent data reporting

---

## 📤 To Submit

- For credit: Submit:
  1. Your complete multi-agent workflow script
  2. Screenshot showing the output from all agents in your workflow
  3. Brief explanation (3-4 sentences) describing:
     - Your agent roles and workflow design
     - Your prompt design choices and iterations
     - What worked well and what you changed

---

![](../docs/images/icons.png)

---

← 🏠 [Back to Top](#LAB)
