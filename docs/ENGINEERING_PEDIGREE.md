# 🧬 Engineering Pedigree: The "Why" of Acme Lab
**Active Architecture Laws & Design Breadcrumbs**

This document tracks the high-level architectural decisions and "Invariant Laws" that govern the Federated Lab. Consult this before performing any core refactors to prevent regressions of "Lost Gems."

## 🏛️ Silicon Mandates (The Hardware Law)

*   **Engine Primacy**: **vLLM is the Primary Engine** for the 2080 Ti. Ollama is the stability fallback.

*   **VRAM Budget**: Mistral-7B remains **FORBIDDEN** for concurrent use on the 2080 Ti.

*   **Model Baseline**: All 2080 Ti nodes MUST standardize on **Llama-3.2-3B-AWQ (Unity Pattern)**. This secures a ~30% VRAM headroom buffer for the EarNode.

*   **The Invariant Heart**: The **EarNode (NeMo STT)** is the invariant sensory core. It must remain resident and functional regardless of the reasoning engine state.


*   **GGUF Tokenizer Law**: When loading GGUF models in vLLM, do NOT point the `--tokenizer` flag to a HuggingFace repo. Point both `--model` and `--tokenizer` to the local GGUF blob to ensure 100% offline operation and bypass gated-model authentication.

## 🧠 Cognitive Architecture
*   **Hemispheric Concurrency**: Parallel Dispatch model where queries are fired to Pinky and Brain simultaneously. See **[RoundTable_Architecture.md](./archive/RoundTable_Architecture.md)**.
*   **Amygdala v3**: Intelligent interjection logic based on **Contextual Worthiness** and **Dissonance Detection** rather than brittle keywords.
*   **Memory Bridge**: Handover logic requiring a 3-turn context echo for Brain interjections to ensure cognitive continuity.

## 🛠️ Operational Laws
*   **Unitary Task Lifecycle**: `AsyncExitStack` MUST be managed in a single sequential task. Split-task management causes `aclose` hangs. See **[BKM_RETROSPECTIVE_FEB_15.md](./BKM_RETROSPECTIVE_FEB_15.md)**.
*   **The Resilience Ladder**: 4-Tier degradation hierarchy (vLLM -> Ollama -> Downshift -> Suspend) enforced by native NVML telemetry.
*   **Silicon Manifest**: All models must be tracked by absolute filesystem path in `infrastructure.json` to prevent "Weight Volatility."

## 🔗 Design Breadcrumbs (The Map)
*   **Infrastructure**: **[infrastructure.json](../config/infrastructure.json)** (Dynamic host resolution/KENDER).
*   **VRAM Plan**: **[VLLM_INTEGRATION_PLAN.md](./plans/VLLM_INTEGRATION_PLAN.md)** (Budget management).
*   **Active Sprint**: **[SPRINT_RESURRECTION_FEB_15.md](./plans/SPRINT_RESURRECTION_FEB_15.md)** (Current focus).
