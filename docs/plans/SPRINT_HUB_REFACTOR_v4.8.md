# SPRINT [v4.8]: Hub Decoupling & Refactor
**Status:** DRAFT | **Focus:** Modular Cognitive Architecture

## 🎯 Objective
Reduce the complexity of `acme_lab.py` (~1500 lines) by factoring out core patterns into specialized modules. This improves the "Signal-to-Noise" ratio for debugging and isolates the "Thinking" logic from the "Plumbing."

## 🏛️ Refactoring Map

### 1. The Sensory Manager (`src/equipment/sensory_manager.py`)
*   **Target**: ~200 lines of audio buffer and transcription logic.
*   **Logic**: Move `EarNode` stub and the binary PCM processing from `client_handler`.
*   **Interface**: Hub calls `SensoryManager.process_chunk(data)` and receives text back.

### 2. The Cognitive Hub (`src/logic/cognitive_hub.py`)
*   **Target**: ~600 lines of reasoning and dispatch logic.
*   **Logic**: Extract `process_query`, `execute_dispatch`, `brain_strategy_chain`, and the `sentinel` intent classification.
*   **Interface**: Hub delegates all "Thinking" tasks to this class, passing the active `residents` map.

### 3. The Lifecycle Manager (`src/infra/lifecycle_manager.py`)
*   **Target**: ~150 lines of boot/loop logic.
*   **Logic**: Extract `boot_residents`, the `while True` persistent loop, and `AsyncExitStack` management.
*   **Interface**: Main entry point `run()` becomes a high-level orchestrator calling `LifecycleManager.ignite()`.

## 🛠️ Implementation Strategy
1.  **Phase 1: Cognitive Extraction**: Move the reasoning logic first, as it is the most frequently debugged area.
2.  **Phase 2: Sensory Extraction**: Clean up the WebSocket handler by removing low-level audio manipulation.
3.  **Phase 3: Lifecycle Extraction**: Finalize the persistent loop into a dedicated manager.

## ✅ Validation Requirements
*   **DEEP_SMOKE**: The full "Cycle of Life" test must pass after every module extraction.
*   **Log Fingerprint**: Ensure the Montana Protocol remains active and fingerprints are preserved across the new modules.
*   **Zero Regression**: Verify that social exit phrases ("goodnight") still trigger the persistent "Bounce" loop correctly.

## 🏺 Scars to Avoid
*   **The Circular Import Trap**: Ensure the new modules don't all try to import `acme_lab.py` back. Use a clean "Request/Response" or "Event" pattern.
*   **The Ghost PID Leak**: Verification of `runner.cleanup()` and `AsyncExitStack` parity in the new `LifecycleManager` is mandatory.
