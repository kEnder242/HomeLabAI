# ✈️ HomeLabAI Travel Guide (2026 Edition)

**Destination:** `jason-lab.dev`
**Safe Zone:** `~/HomeLabAI_Dev` (This folder contains the full git repo & docs)
**Runtime Zone:** `~/AcmeLab` (Production)

---

## 🔑 Access Codes
*   **VS Code (Terminal):** [https://code.jason-lab.dev](https://code.jason-lab.dev)
    *   **Password:** `b51020421d5b2b920546274f`
*   **The Pager (Logs):** [https://pager.jason-lab.dev](https://pager.jason-lab.dev)
    *   **Tunnel Auth:** If asked, use the email you registered with Cloudflare.

---

## 🛠️ Remote Dev Environment
You are working directly on `z87-Linux`.
*   **Working Directory:** `cd ~/HomeLabAI_Dev`
*   **Virtual Env:** `.venv` (Linked to AcmeLab, shared libs).

### 🤖 Using Gemini CLI Remotely
I am installed in a dedicated venv to avoid conflicts with Pinky.
1.  **Start Session:**
    ```bash
    cd ~/HomeLabAI_Dev
    tmux new -s agent  # Keeps me alive if WiFi drops
    .venv/bin/gemini chat
    ```
2.  **Authentication:**
    If I ask to authenticate, I will print a URL. Copy it to your local browser (phone/laptop) to sign in.


---

## 🏃‍♂️ Exercises & Modes

### Mode 1: The SRE (Observability)
*   **Goal:** Install Prometheus & Grafana via Docker.
*   **Why:** Learn time-series DBs for your interview.
*   **Commands:**
    ```bash
    # 1. Install Docker (if not present)
    sudo apt update && sudo apt install docker.io docker-compose

    # 2. Create docker-compose.yml in ~/HomeLabAI_Dev
    # (Ask Gemini to generate a basic Prom/Grafana config)

    # 3. Spin it up
    sudo docker-compose up -d
    ```
*   **Verification:**
    *   Route a new Cloudflare tunnel for Grafana (port 3000) or just `curl localhost:3000`.

### Mode 2: The Lobe Surgeon (Pinky Logic)
*   **Goal:** Refactor `pinky_node.py` to handle "Offline Brain".
*   **Why:** Make the system robust when the 4090 is down.
*   **Task:**
    *   Edit `src/nodes/pinky_node.py`.
    *   Find where it calls `ASK_BRAIN`.
    *   Add a fallback: If Brain is offline (timeout), use a local "Canned Response" or check RAG directly.
*   **Test:**
    *   Run `src/test_round_table.py` to verify logic changes.

### Mode 3: The Dream Weaver (Data)
*   **Goal:** Organize `~/knowledge_base`.
*   **Why:** Better RAG results.
*   **Task:**
    *   Use VS Code to browse `~/knowledge_base`.
    *   Create a script `src/clean_notes.py` to fix markdown formatting in your exported Google Docs.

---

## 🆘 Emergency Reset
If you break the environment or processes get stuck:
```bash
# Kill all python processes
pkill -f python

# Restart Infrastructure
sudo systemctl restart code-server@jallred
sudo systemctl restart acme-pager
sudo systemctl restart cloudflared
```

Safe travels!
- Pinky 🧠
