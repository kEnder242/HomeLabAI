# Acme Lab: Debug Insights & Operational Wins

## 🏛️ The Lab Attendant Pattern (Feb 2026)
- **Problem:** Frequent "ghost processes" and terminal hijacking when running `acme_lab.py` manually or via `nohup`.
- **Solution:** A dedicated `lab_attendant.py` service (managed by systemd).
- **Benefit:** Provides a stable HTTP API for lifecycle management (Start/Stop/Status) and a clean "Truth Anchor" for system logs.
- **BKM:** Always use `curl -X POST http://localhost:9999/status` to verify the state of the mind before attempting to debug node communication.

## 🛠️ Strategic Patching (The Unified Diff Move)
- **Problem:** The `replace` tool is brittle regarding indentation and whitespace, leading to "Chopstick Coding" thrash.
- **Solution:** Using standard Unix `.patch` files and the `patch` utility.
- **Benefit:** Robust, atomic updates that handle context more intelligently than literal string matching.
- **Workflow:** 
    1. Write a `temp.patch` file.
    2. `run_shell_command("patch target_file temp.patch")`.
    3. Verify and commit.

## 🧠 Bicameral Fallback (Offline Resilience)
- **Problem:** Lab hangs if the 4090 host (Brain) is offline during startup or reasoning.
- **Solution:** Heartbeat-based "Stub" logic.
- **Benefit:** If `BRAIN_HEARTBEAT_URL` fails, Pinky triggers "Panic Mode" and handles requests locally with a characterful excuse.
