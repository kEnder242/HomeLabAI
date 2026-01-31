# Migration Plan: The Federated Lab (WSL to Linux)

**Date:** January 31, 2026
**Objective:** Transition development from WSL (Windows) to a native Linux host (`z87-Linux`) while adopting a "Federated Lab" architecture. This moves the project from a "Remote Development" model to a "Platform & Intelligence" model.

---

## 1. The Core Philosophy: "Platform vs. Intelligence"

We are splitting the "Home Lab" into two distinct, loosely coupled repositories that sit side-by-side in `~/Dev_Lab` on the Linux host.

### Repo A: `Portfolio_Dev` (The Platform)
*   **Role:** The Host, The UI, The Monitor.
*   **Responsibility:** "Running the Lab."
*   **Contents:**
    *   **`web/`:** The new Acme Lab Landing Page (Goal #2) & Mission Control (Goal #3).
    *   **`scrapers/`:** Data ingestion pipelines (Field Notes).
    *   **`monitor/`:** Prometheus, Grafana, and PagerDuty integration (Goal #1).
    *   **`platform/`:** "Root Services" configuration (Systemd units, Cloudflare tunnels, Rclone mounts).
*   **Environment:** Lightweight Python `.venv` (Web frameworks, API clients).

### Repo B: `HomeLabAI` (The Intelligence)
*   **Role:** The Brain, The Voice, The RAG.
*   **Responsibility:** "Being the AI."
*   **Contents:**
    *   **`src/nodes/`:** Pinky, Brain, and MCP nodes.
    *   **`src/archive/wsl_legacy/`:** Retired WSL-specific scripts (`sync_to_linux.sh`, `intercom.py`) and documentation.
*   **Environment:** Heavy Python `.venv` (PyTorch, NeMo, CUDA).

---

## 2. The Migration Checklist

### Step 1: WSL Housekeeping (Current Session)
1.  [ ] **Archive Legacy:** Move `sync_to_linux.sh`, `sync_to_windows.sh`, `run_remote.sh`, and `intercom.py` to `src/archive/wsl_legacy/`.
2.  [ ] **Update Docs:** Move `Remote_Access_Instructions.txt` and `Travel_Guide_2026.md` to `src/archive/wsl_legacy/`.
3.  [ ] **Commit & Push:** Ensure `HomeLabAI` is clean and synced to remote.

### Step 2: Linux Setup (Next Session)
1.  [ ] **Create Workspace:** `mkdir -p ~/Dev_Lab`.
2.  [ ] **Clone/Move:** Ensure `HomeLabAI` and `Portfolio_Dev` are inside `~/Dev_Lab`.
3.  [ ] **Gemini Context:** Create `~/Dev_Lab/.gemini/GEMINI.md`. This file is **untracked** and serves as the "God Mode" context for the Gemini CLI, allowing it to see across both repos.

### Step 3: Platform Extraction
1.  [ ] **Harvest Configs:** Copy active systemd units (`cloudflared`, `code-server`) from `/etc/systemd/system/` into `Portfolio_Dev/platform/`.
2.  [ ] **Harvest Monitoring:** Move the Prometheus/Grafana stack from the Korea trip (in `Portfolio_Dev`) into `Portfolio_Dev/monitor/`.

---

## 3. Future Goals & Architectural Considerations

### Goal 1: PagerDuty Integration
*   **Strategy:** `Portfolio_Dev` owns the PagerDuty client (`monitor/notify_pd.py`).
*   **Integration:** `HomeLabAI` triggers alerts via a local Webhook (provided by the Portfolio web app) or by executing the script if permissions allow.

### Goal 2: Acme Labs Web Page
*   **Strategy:** Build a unified landing page in `Portfolio_Dev/web/`.
*   **Features:**
    *   Status of Pinky/Brain.
    *   "Mission Control" Sidebar (Goal #3).
    *   Links to VS Code and Grafana.

### Goal 4: Workflow Reconciliation
*   **Challenge:** Losing the "Fast Loop" from WSL.
*   **Solution:** Use VS Code Remote SSH. The "Terminal" in VS Code becomes the new primary interface.
*   **Doc Update:** Rewrite `README.md` in `HomeLabAI` to reflect "Native Linux" usage (e.g., "Run `python src/acme_lab.py`" instead of "Run `./run_remote.sh`").

### Goal 6: Integrated Scraping
*   **Strategy:** The scraping logic lives in `Portfolio_Dev` (The Platform).
*   **AI Integration:** It calls `HomeLabAI` (The Intelligence) via API/MCP to process the text it finds (e.g., "Pinky, summarize this log").

---

## 4. "God Mode" Context (GEMINI.md)
*   **Concept:** The `GEMINI.md` file at the root of `~/Dev_Lab` is the bridge.
*   **Usage:** When you start Gemini CLI, point it to this context or symlink it into the active project folder. It reminds the Agent that while it is working in one repo, the other exists right next door.

