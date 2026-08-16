# FEAT Audit: What the V4→V5 Refactor Neutered

**Date:** 2026-08-15
**Context:** Post-incident audit of the FEAT-028 Deep Thought regression (fixed in commit `549aecd`).
**Question asked:** "Any other FEATs we neutered in the v5 refactor? IIRC we used FEATs to keep v5 in line."

---

## The Core Philosophy: Probe, Not Flag

"Vocal" means **if the lab can reply, it's healthy.** This is a *probe* philosophy: health is
not a state you declare, it's a behavior you observe. You ask the thing a question and see if
it answers.

The refactor quietly replaced *probe vocal* with *flag vocal*:

| | **Probe vocal** (V4 philosophy) | **Flag vocal** (V5 drift) |
|---|---|---|
| How it works | Actively POSTs a real request: "respond with SUCCESS" → waits for actual tokens | `self.status.vocal = True` written when ignition finishes |
| What it proves | The engine *actually generated a response right now* | "We *believe* it should be able to" |
| Cost | ~seconds per check | free |
| Failure mode | catches "ON but loading", dead nodes, wedged LoRA swaps | **lies** — says ON while still loading, says ON after a node dies |

> "The lab thinks it's ON but it's actually still loading" is precisely the flag-vs-probe gap.
> Flags are for routing. Probes are for truth.

---

## What Each Lost FEAT Actually Was

### FEAT-337 — `_check_resident_health()` (Resident Persistence) 🚨 LOST
The lab is a swarm of node processes (pinky, brain, lab, thought, archive), each an MCP client
session. After boot the swarm can *partially* die while the state machine still reports
OPERATIONAL. FEAT-337 issued a `list_tools` call to **each** resident — an MCP-standard request
the node process answers *itself*, crucially **without needing the vLLM engine to be loaded**.
Its docstring: *"does NOT require the vLLM engine to be vocal"* — a process liveness check,
orthogonal to engine loading.
**V5 status:** boots the swarm, never verifies it stayed alive. Absent from tracker entirely.

### FEAT-342 — `_synchronize_and_probe()` (Unified Resumption) 🚨 LOST
Runs **after any wake event** — the exact moment the ON-but-loading window is widest. Probed,
not assumed: physical sanity + resident health, then a hard escape hatch (BKM-009 "Silicon
Scythe", `os._exit(1)`) if the probe found an unrecoverable state. Wake → verify reality →
only then trust OPERATIONAL.
**V5 status:** `start_lab` probes the engine once, never re-probes residents after wake, never
scythes on incoherence. Absent from tracker entirely.

### FEAT-339 — `_run_deep_smoke()` (Cycle of Life) 🚨 LOST
Task-safe end-to-end smoke test: boot → probe → verify the whole loop actually cycles, run in a
way that respects the concurrency mutex so it doesn't fight other tasks.
**V5 status:** the tag was **recycled** onto unrelated task-cleanup helpers in `router.py`.

### FEAT-118 — `get_oracle_signal()` (Resonant Oracle) 🟡 NEVER SHIPPED
Weighted, state-aware UI preamble selection (`RETRIEVING` / `UNCERTAIN` / `VRAM_STRESS` /
`HANDSHAKE`) replacing hardcoded strings. Lost polish, not lost safety.
**Tracker status:** DESIGN — never fully implemented even in V4.

---

## Verified Survivors (No Regression)

- **FEAT-265.7** engine liveness → real `/v1/chat/completions` cognitive probe at ignition (`manager.py:185-215`)
- **FEAT-265.8** spark restoration → `start_lab()`
- **FEAT-287** activity latch → `cognitive_hub.py:628` (resets `last_activity` + `last_prime_callback`)
- **FEAT-302** adaptive cooldown · **FEAT-365** reflexes · **FEAT-437/438/456** (Sprint 54 work)
- **FEAT-134/285/286.2** gates → restored by the FEAT-028 health fix
- **FEAT-028** Deep Thought health probe → restored in `549aecd`

---

## The Systemic Scar (Root Cause)

1. `ca31a51` deleted 51 functions from `acme_lab.py`; tags for dropped features were
   **recycled onto unrelated code** (FEAT-339 → task cleanup, FEAT-287 → mutex).
2. The FeatureTracker was **never cross-referenced** during promotion — FEAT-337/342 aren't
   even recorded, so their loss was invisible.
3. FEAT-028 only got caught because KENDER hammering made it loud.

---

## Recommended Restoration Order (Not Yet Approved)

1. **FEAT-342 first** — in `start_lab`, after the engine probe passes: one resident-health pass
   (`list_tools` each node) before declaring OPERATIONAL. Catches ON-but-loading at the moment
   it matters most.
2. **FEAT-337 second** — periodic (30-60s) resident liveness loop + re-check after any
   hibernate→wake cycle. Cheap — `list_tools` needs no generation.
3. **FEAT-339** — optional; deep smoke test as a diagnostic tool rather than a boot gate.
4. **FeatureTracker** — re-record 337/342/339 so the loss is no longer invisible.

---

*Flags are for routing. Probes are for truth.*
