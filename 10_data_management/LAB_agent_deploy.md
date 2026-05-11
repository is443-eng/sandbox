# 📌 LAB

## Deploy an Autonomous Agent (Python or R)

🕒 *Estimated Time: 10–15 minutes*

---

## 📋 Lab Overview

You will deploy the same agent you ran locally to **Posit Connect** (or your class hosting environment), set environment variables on the server, and verify **`/health`** and **`/hooks/agent`** on the **public** URL. Pick the track that matches your local work:

| Track | Folder | Connect content type |
|--------|--------|----------------------|
| **Python** | This folder (**`10_data_management/`**); entry [`app.py`](app.py) | **FastAPI** — **`rsconnect deploy fastapi`** with **`app:app`** |
| **R** | [`agentr/`](agentr/) | **Plumber** — **`rsconnect::deployAPI`** with **`plumber.R`** |

### Posit Connect Cloud (hosted)

Use the same tracks as above; point CLI and **`.env`** at the cloud server:

| Item | Value |
|------|--------|
| **`CONNECT_SERVER`** | **`https://connect.posit.cloud`** |
| **`CONNECT_API_KEY`** | **Connect Cloud** → your avatar / **Account** → **API Keys** → create a key |

**IDE:** Install the [Posit Publisher](https://marketplace.visualstudio.com/items?itemName=Posit.publisher) extension, open **`10_data_management/`** (Python) or **`agentr/`** (R), use the Publisher sidebar, sign in to **Connect Cloud**, deploy as **FastAPI** with **`app:app`** or **Plumber** with **`plumber.R`**. See [Publish from the IDE (Connect Cloud)](https://docs.posit.co/connect-cloud/user/publish/ide.html).

**CLI:** Put **`CONNECT_SERVER`** and **`CONNECT_API_KEY`** in **`.env`** at the **repository root** (R) or **`agentpy/.env`** (Python `deployme.sh`), then run **`manifestme.sh`** / **`deployme.sh`** or **`deployme.R`** as in Stage 1. After deploy, set **`OLLAMA_*`** (and optional **`SERPER_API_KEY`**) in the content’s **Vars** on Connect Cloud.

---

## ✅ Your Task

### 🧱 Stage 1: Manifest and deploy

- [ ] **Python:** From **`agentpy/`**, run **[`manifestme.sh`](agentpy/manifestme.sh)** then **[`deployme.sh`](agentpy/deployme.sh)** (both use **`10_data_management/`** as bundle root and **`app:app`**), **or** follow the comments at the top of **[`agentpy/testme.py`](agentpy/testme.py)** (`rsconnect write-manifest fastapi --entrypoint app:app`, then `rsconnect deploy fastapi`).
- [ ] **R:** From the **repository root**, run **`Rscript 10_data_management/agentr/manifestme.R`** (optional, if you need a fresh manifest) then **`Rscript 10_data_management/agentr/deployme.R`** — see **[`agentr/deployme.R`](agentr/deployme.R)** and **[`agentr/README.md`](agentr/README.md)** (**`readRenviron(".env")`**, **`CONNECT_SERVER`**, **`CONNECT_API_KEY`** at repo root).
- [ ] In the Posit Connect UI, set **`OLLAMA_API_KEY`**, **`OLLAMA_HOST`**, and **`OLLAMA_MODEL`**. Optionally set **`SERPER_API_KEY`** so preflight and **`web_search`** hit live results (omit if you accept “search disabled” behavior).
  - <img width="2093" height="1292" alt="image" src="https://github.com/user-attachments/assets/d2638b90-821a-4009-93c0-0e57655499e2" />


### 🧱 Stage 2: Smoke test

- [ ] Send an API call to your deployed API, using the [`testme.py`](https://github.com/timothyfraser/dsai/edit/main/10_data_management/agentpy/testme.py)/[`testme.R`](https://github.com/timothyfraser/dsai/edit/main/10_data_management/agentr/testme.R) script.
   - [ ] For this to succeed, you will need to...
      - [ ] copy your deployed **base URL** (no trailing slash) into **`.env`** as **`AGENT_PUBLIC_URL`**. Then...
      - [ ] Add your Posit Connect Viewer key to the **`.env`** as **`CONNECT_VIEWER_KEY`**. Then... 
      - [ ] **Python:** From **`agentpy/`**, run **`python testme.py`** **or** call **`GET …/health`** manually.
      - [ ] **R:** From the **repository root**, run **`Rscript 10_data_management/agentr/testme.R`** **or** call **`GET …/health`** manually.
- [ ] **`POST`** to **`…/hooks/agent`** on the **live** URL with the same JSON body you used locally; confirm you get **`200`** and a **`reply`**.

   - For example, mine looks like this:
<img width="1138" height="439" alt="image" src="https://github.com/user-attachments/assets/31c63a26-bb91-43e9-9991-5556f5b88048" />


### 🧱 Stage 3: Start / stop (optional)

- [ ] **`POST`** to **`/hooks/control`** with **`{"action":"stop"}`** and confirm **`/health`** shows **`"run_enabled": false`**.
- [ ] **`POST`** with **`{"action":"start"}`** to turn the agent back on.

---

# 📤 To Submit

- Screenshot of **`GET /health`** from the **deployed** base URL showing **`"ok": true`**.
- Screenshot of a successful **`POST /hooks/agent`** against the **deployed** URL (trim long **`reply`** text if needed).

---

![](../docs/images/icons.png)

---

← 🏠 [Back to Top](#ACTIVITY)
