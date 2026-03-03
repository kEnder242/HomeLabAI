# Sprint Plan: v4.8 - Hub Modularization & Appliance Hardening
**Status: ✅ COMPLETED | Phase: 9.1**

## 🎯 GOAL
Decouple the monolithic `acme_lab.py` Hub into specialized managers to improve maintainability, VRAM residency efficiency, and establish appliance-grade resilience.

## 🛠️ TASKS

### Phase 1: Sensory Layer & Montana (✅ DONE)
- [x] Create `src/equipment/sensory_manager.py`.
- [x] Extract binary audio buffering and NeMo EarNode residency logic.
- [x] Create `src/infra/montana.py` for centralized logging and fingerprinting.
- [x] **Validation**: Log visibility reclaimed for all nodes (`[MONTANA]`).

### Phase 2: Cognitive Hub & Dispatch (✅ DONE)
- [x] Create `src/logic/cognitive_hub.py`.
- [x] Move reasoning, tool extraction, and node dispatch logic.
- [x] Implement robust regex-based JSON extraction for banter-wrapped payloads.
- [x] **Validation**: **Deep Smoke** PASSED through modular delegation.

### Phase 3: Appliance Resilience [FEAT-149/151] (✅ DONE)
- [x] Implement the `while True` Auto-Bounce loop in `AcmeLab.run()`.
- [x] Implement **[FEAT-151] Trace Monitoring** (`src/debug/trace_monitor.py`).
- [x] Harden `test_goodnight_bounce.py` with state transition polling and log delta capture.
- [x] **Validation**: Verified 20s recovery cycle with full trace evidence.

### Phase 4: Lifecycle Extraction (⏳ NEXT)
- [ ] Create `src/infra/lifecycle_manager.py`.
- [ ] Move process boot/reap logic and `AsyncExitStack` orchestration.
- [ ] Move systemd status handshakes and maintenance locking.

## 📐 ARCHITECTURAL INVARIANTS
1. **Sensory Priority**: EarNode MUST be loaded before Cognitive residents to claim contiguous VRAM.
2. **Atomic Cleanup**: The "Assassin" (Attendant) must reap PGIDs before any ignition attempt.
3. **Trace-First Debugging**: All lifecycle tests MUST use `TraceMonitor` to capture log deltas.
4. **Lint-Gate**: All "Heads Down" code modifications MUST pass `ruff check`.
