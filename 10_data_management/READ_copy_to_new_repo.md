# 📌 READ

## Copying `10_data_management` to another repository

🕒 *Estimated Time: 5 minutes*

---

## Why this note exists

You can copy this entire folder into a different Git repository and keep working, but several scripts and docs assume **this course repo’s layout and naming** (paths under **`10_data_management/`**, the parent folder name **`dsai`** in some R code, and links to other modules). This page lists what to adjust so nothing fails silently after the move.

---

## Recommended layout in the new repo

**Easiest path:** Keep the top-level directory name **`10_data_management`** and place it at the **root** of the new repository (same as here: `…/your-repo/10_data_management/agentpy/`, etc.). That preserves command lines in the labs and many **`Rscript 10_data_management/...`** examples.

If you **flatten** the tree (e.g. move `agentpy/` to the repo root), you must update every path that starts with **`10_data_management/`** and any **Plumber** / **manifest** paths that point at those folders.

---

## 1. R fixer scripts (`fixer/*.R`)

These scripts infer the repo root with **`stringr::str_extract(getwd(), ".*dsai")`** and then set **`FIXER_ROOT`** to **`{REPO}/10_data_management/fixer`**.

- If your clone path **does not contain the string `dsai`**, or you rename the repo directory, **`REPO`** can become **`NA`** and paths break.
- **Mitigation:** Run fixer scripts **from** the `fixer/` directory (Python drivers already **`chdir`** there), or set **`FIXER_ROOT`** in the environment if your port adds support for it consistently across scripts.

After copying, search for **`dsai`** and **`10_data_management`** in **`fixer/*.R`** and align with your new repo name or use a single env-based root.

---

## 2. R agent API (`agentr/`)

- **`runme.R`** calls **`plumber::plumb("10_data_management/agentr/plumber.R")`**. That path is relative to the **repository root** when you run **`Rscript 10_data_management/agentr/runme.R`** from that root.
- **`plumber.R`**, **`manifestme.R`**, and **`deployme.R`** also assume **`10_data_management/agentr`** under the repo root.

If you drop the **`10_data_management`** segment, update these paths and the documented commands in **`LAB_agent_local.md`** / **`LAB_agent_deploy.md`**.

---

## 3. Python (`agentpy/`, `fixer/*.py`)

Running from **`agentpy/`** or **`fixer/`** (or using **`FIXER_ROOT`** where implemented) usually works without the parent repo name. Helpers such as **`fixer/functions.py`** and **`fixer/testme.py`** look for **`…/10_data_management/fixer`** when resolving the fixer root from the repo root; adjust or rely on running inside **`fixer/`**.

**FastAPI** loads **`.env`** from the **`agentpy/`** directory when using the packaged app layout (see **`app/api.py`**). Keep an **`agentpy/.env`** (never commit secrets) in the copied tree.

---

## 4. Markdown and cross-repo links

- **`agentpy/README.md`** links to other modules (e.g. **`../../08_function_calling`**, **`../../04_deployment`**). Those paths are **outside** this folder; copy those modules too, or **edit or remove** broken links.
- **`10_data_management/runme.sh`** invokes **`10_data_management/agentpy/...`** — it expects to be run from the **repository root**; update if your layout changes.
- Lab and activity markdown files may reference **`../docs/images/icons.png`** (or similar). Either copy the relevant files under **`docs/`** into the new repo or adjust image paths and remove broken footers.

---

## 5. Environment variables and secrets

- **`.env`** files are typically **gitignored**. After copying, recreate **`agentpy/.env`**, **`agentr/.env`**, **`fixer/.env`** from each **`.env.example`** and paste keys again.
- Do **not** commit API keys or Connect tokens.

---

## 6. Upstream course URLs

Some files embed links to the original course GitHub tree (e.g. **`api.py`**, **`plumber.R`**). Update those strings if your published project should point at **your** repository’s URL.

---

## 7. Quick verification after the move

From the new repo root (adjust if your root layout differs):

```bash
# Find hardcoded path segments and repo name assumptions
rg '10_data_management|\bsdai\b|timothyfraser/dsai' 10_data_management --glob '*.{R,py,md,sh}'
```

Fix or document every hit that applies to your new repo name and layout.

---

## License and attribution

If the original repo carries a **license** (e.g. MIT), **keep the license file** or **retain copyright notices** required by that license when you publish a derivative. When in doubt, keep the upstream **`LICENSE`** (or equivalent) alongside the copied code.

---

![](../docs/images/icons.png)

---

← 🏠 [Back to Top](#READ)
