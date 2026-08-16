# Sprint Plan: SPR-56.0 — Dynamic Preamble Fusion & Telemetry Realignment

**Sprint ID:** `spr-56-0-preamble-telemetry`  
**Phase:** Phase 12 (Bicameral Polish & Telemetry Alignment)  
**Target Date:** August 16, 2026  
**Status:** IMPLEMENTING  

---

## 🎯 Executive Summary & Objectives

Sprint SPR-56.0 fixes telemetry disconnections in `status.html`, restores BKM-015 compliance by removing hardcoded string arrays for preambles, and fuses $t=0$ HyDE vector synthesis and casual greeting preambles into a **single, LLM-generated JSON pass** from Deep Thought on KENDER (`_spawn_deep_thought_preamble`).

---

## 🛠️ User Stories & Deliverables

### Story 1: `[FEAT-459]` Deep Thought Unified Preamble & Dynamic LLM Greeting Fusion
- **Goal:** Eliminate Python keyword/regex domain matching (`is_domain_match`) and hardcoded `casual_reflections` string arrays in `router.py`. Fuses HyDE synthesis and casual greeting generation into a single non-blocking LLM prompt to Deep Thought on KENDER.
- **Payload Schema:**
  ```json
  {
    "is_casual": boolean,
    "greeting": "Dynamic 1-sentence analytical or readiness quip",
    "hyde_vector": "[VALIDATION]: ... | [STRATEGY]: ... | [SRE]: ..."
  }
  ```
- **Files:** `HomeLabAI/src/v5/foyer/router.py`, `HomeLabAI/src/logic/cognitive_hub.py`.

---

### Story 2: `[FEAT-463]` Remote Lab Control Direct Endpoint Binding & Failure Fallback
- **Goal:** Replace brittle domain-guessing fetch URLs in `triggerLabAction()` with direct LAN/loopback binding (`http://127.0.0.1:8765/${action}` with `mode: 'cors'`) and automatic fallback to `https://pager.jason-lab.dev/${action}` on network timeout.
- **Status:** **COMPLETED & VERIFIED**
- **Files:** `Portfolio_Dev/field_notes/status.html`.

---

### Story 3: `[FEAT-464]` Live Vitals Telemetry Grid Modernization
- **Goal:** Remove obsolete/disconnected 0.0% VRAM and System RAM cards from `status.html`. Rename `Silicon Mode` to `Bicameral State` (`OPERATIONAL`, `HIBERNATING`, `WARMING`), set default `Active Model` to `Llama-3.2-3B-AWQ`, and set default `Web Intercom` status to `HIBERNATING`.
- **Status:** **COMPLETED & VERIFIED**
- **Files:** `Portfolio_Dev/field_notes/status.html`.

---

### Story 4: `[FEAT-465]` FeatureTracker & ChromaDB DNA Alignment
- **Goal:** Record FEAT-463, FEAT-464, FEAT-465, and the updated FEAT-459 scope in `FeatureTracker.md` and trigger auto-sync to ChromaDB `feature_dna` collection via pre-commit git hooks.
- **Files:** `Portfolio_Dev/FeatureTracker.md`.
