# Stabilization Report: Sovereign & Watchdog Hardening (Feb 20, 2026)
**"Breaking the Silence Loop"**

## 🎯 The Objective
To resolve the "Sovereign Silence" (Windows 4090 returning dots) and stabilize the Lab Attendant's boot sequence to prevent recursive watchdog kills.

## 📉 The "Manic Phase" Audit
Between 22:00 and 23:00, the system entered a high-velocity debug cycle. The following items were implemented and committed:

### 1. Sovereign Recovery (The Voice)
- **Problem**: `gemma2:2b` on KENDER was returning empty responses (`...`).
- **Fix**: Implemented **Model Prioritization** in `loader.py`. The Brain now explicitly prefers `llama3:latest` on Ollama engines.
- **Protocol Shift**: Implemented **Engine-Aware Routing**. Linux uses Chat API; Windows uses Generate API (Raw Prompt) for maximum robustness.
- **Quality-Gate [FEAT-077]**: Added logic to `acme_lab.py` to detect "dotted" or empty responses and immediately trigger a local "Shadow" failover to Pinky, ensuring the UI always gets an answer.

### 2. Watchdog Hardening (The Boot)
- **Problem**: The Attendant was killing the Lab server because port 8765 was unresponsive while residents were loading.
- **Fix**: Implemented a **Graceful Boot Window** in `lab_attendant.py`. The watchdog now allows for 60 seconds of initialization before declaring the service "DEAD."
- **Lint Fixes**: Corrected scope errors (`boot_grace_period`) and missing imports (`time`) introduced during the sprint.

### 3. Forensic Visibility [FEAT-078]
- **Tool**: Implemented `_mirror_forensics` in `loader.py`.
- **Logic**: All raw prompts and JSON responses are now mirrored to `HomeLabAI/logs/forensic_brain.json`. This provides bit-perfect visibility into exactly what is being sent to and received from the Windows host.

## 💡 Rationale (The "Why")
- **Sovereign Silence**: The Windows host was collapsing under complex Chat API templates. Raw prompts are the "Law of Least Resistance" for remote Ollama instances.
- **Watchdog Collision**: A validation engineer's worst nightmare is a "helpful" recovery script that kills the process it's trying to save. The grace period breaks this cycle.

## 🏃 Next Steps (Cold-Start Mandate)
1.  **Check Forensics**: If the Brain is silent, run `cat HomeLabAI/logs/forensic_brain.json`.
2.  **Verify READY**: Wait 60s for the new Graceful Boot Window to expire and confirm `Mind is READY` in the UI.
3.  **Audit Routing**: Ensure `System` strategic messages are correctly shunting to the Insight panel.

---
**Baseline Commit**: `c292960` (HomeLabAI)
**DNA Mapping**: Feature Matrix updated with [FEAT-077], [FEAT-078], [FEAT-079].
