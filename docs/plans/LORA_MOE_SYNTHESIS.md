# Poor Man's MoE: Multi-LoRA Expert Routing (PMM)
**Version:** 1.0 (Phase 11 Synthesis)
**Theoretical Anchors:** [ARX-2401.06066], [ARX-2402.07033], [ARX-2603.01853]
**Silicon Host:** Z87-Linux (RTX 2080 Ti)

## 🎯 Executive Summary
The "Poor Man's MoE" (PMM) strategy applies Mixture-of-Experts architectural lessons to a small-memory environment (11GB VRAM). Instead of loading a monolithic 14B-35B MoE model, we maintain a **Unified 3B Base Model** (Llama-3.2) and use the Cognitive Hub as a **Pre-Gated Router** to hot-swap tiny, high-density LoRA "Glasses" (Adapters) in milliseconds via vLLM.

---

## 🔬 Theoretical-to-Silicon Mapping

| MoE Research Pillar | Lab Implementation (PMM) | vLLM / Unsloth Role |
| :--- | :--- | :--- |
| **Fine-Grained Experts** (DeepSeek) | **Granular LoRA Adapters** | **Unsloth**: Train tiny (Rank 16-32) experts from specific archive folders. |
| **Pre-Gated Inference** (Microsoft) | **Cognitive Hub Routing** | **Hub**: Analyzes query intent *before* vLLM call to select adapter set. |
| **Adaptive Expert Split** (MoEpic) | **Multi-Adapter Layering** | **vLLM**: Layering multiple LoRAs (e.g. `telemetry` + `bkm`) in one turn. |
| **Autonomous Exploration** (AT2QA) | **Agentic Backtracking** | **Pinky**: Restarts reasoning with a *different* LoRA if fidelity is low. |
| **GPTQ-Int4 Residency** | **Base Intelligence Upgrade** | **Qwen 3.5 9B**: Evaluation of INT4 quantized base to increase the "Intelligence Floor" on 11GB silicon. |
| **Token-to-Token Editing** | **Real-Time Synthesis** | **LLaDA2.1**: Future watch for diffusion-based document "patching" rather than autoregressive generation. |

---

## 🧬 The "Glasses" Catalog (Expert Adapters)
We are moving away from monolithic "Brain" vs "Pinky" weights toward a library of specialized expertise:

### 1. [EXP-TLM] The Telemetry Expert
*   **Focus:** RAPL, PECI, DCGM, MSR, and performance profiling.
*   **Source Data:** `expertise/telemetry/`, 18 years of silicon validation logs.
*   **Vibe:** Clinical, data-dense, validation-first.

### 2. [EXP-BKM] The Architect (BKM Protocol)
*   **Focus:** Design patterns, "Class 1" philosophy, and system-level BKMs.
*   **Source Data:** `HomeLabAI/docs/protocols/`, `Portfolio_Dev/field_notes/architecture/`.
*   **Vibe:** Stoic, authoritative, architectural.

### 3. [EXP-FOR] The Forensic (Discovery)
*   **Focus:** AT2QA search logic, archive breadcrumb following, and temporal consistency.
*   **Source Data:** 18-year Focal documents and nightly synthesis reports.
*   **Vibe:** Curious, iterative, investigative.

### 4. [EXP-REC] The Recruiter (CVT Strategy)
*   **Focus:** 3x3 CVT Builder logic, matching multi-vector pillars, and recruiter persona.
*   **Source Data:** Job search history, hiring logs, and career strategy docs.
*   **Vibe:** Strategic, professional, uplink-aware.

---

## 🔄 Cognitive Execution Flow (FEAT-174)

1.  **Ingestion**: User speaks or types a query to the Gateway (Pinky).
2.  **Intent Gating**: The Hub performs a sub-100ms pass (Sentinel Node) to identify the domain.
3.  **Adapter Selection**:
    *   *Match Found:* Hub requests `base_model` + `exp_adapter_X` from vLLM.
    *   *Ambiguity Found:* Hub requests a "Layered Set" (e.g. `telemetry` + `forensic`).
4.  **Backtracking Pass (FEAT-173)**: Pinky evaluates the derivation. If the "Glasses" didn't fit (thin output), she triggers a **Strategic Pivot**, swaps adapters, and retries.
5.  **Uplink**: The high-fidelity specialized answer is returned.

---

## 🏺 Master Integration Links

### Backlog & Features
*   **[FEAT-174]**: Defines the Hub-level routing logic.
*   **[FEAT-173]**: Provides the autonomous "Retry" loop if the chosen expert fails.
*   **[FEAT-030]**: The **Unity Pattern** mandates that all these experts share the 3B Base footprint.

### Vibes & DNA
*   **[VIBE-011]**: The "Always Ready" Resident ensures adapters are "Warmed Up" in VRAM.
*   **[DNA-015]**: "Reading Like a Robot" logic is the primary training data for the Forensic expert.

---

## 🏃 Sprint Plan [SPR-11-MoE]: PMM Ignition
**Objective:** Transition the Lab from monolithic personas to dynamic multi-adapter expert routing.

### 📍 Phase 1: Routing Infrastructure (Week 1)
*   **[FEAT-174.1] Pre-Gated Router**: Update `acme_lab.py` to identify "Expert Domains" from queries using keyword vectors or a 1B Sentinel pass.
    *   *Test:* `test_routing_logic.py` (Verify correct adapter ID is selected for mock queries).
*   **[FEAT-174.2] vLLM Multi-Adapter Bridge**: Hardening `loader.py` to support `lora_request` payloads in the OpenAI-compatible endpoint.
    *   *Test:* `test_vllm_adapter_swap.py` (Measure latency of swapping between mock LoRAs).

### 📍 Phase 2: The Forge (Week 2)
*   **[FORGE-01] Archive Distillation**: Script to extract "Pure Expertise" from the 18-year archive (e.g. all `.md` files in `expertise/telemetry/`) into instruction-response pairs.
*   **[FORGE-02] Unsloth Training Template**: Create `train_expert.py` optimized for Turing (SM 7.5) to "burn" Rank 16 adapters.
    *   *Test:* `test_forge_fidelity.py` (Verify training loss and token adherence of a sample 1MB adapter).

### 📍 Phase 3: Recursive Discovery (Week 3)
*   **[FEAT-173.1] Fidelity Gate**: Implement the self-evaluation pass where Pinky judges the density of a tool-result.
*   **[FEAT-173.2] Backtracking Loop**: Implement the `Strategic Pivot` logic allowing an autonomous retry with a different expert adapter.
    *   *Test:* `test_agentic_backtrack.py` (Force a "thin" result and verify Pinky triggers a re-query with a new adapter).

---

## ⚠️ Risk Registry & Guardrails

| Risk ID | Description | Mitigation Strategy |
| :--- | :--- | :--- |
| **[R-01]** | **vLLM Adapter Drift**: Parallel LoRAs on Turing SM 7.5 sometimes cause KV cache corruption. | **Guardrail**: Force `--enforce-eager` and monitor `vllm_server.log` for "NCCL Timeout" during swaps. |
| **[R-02]** | **Forge Throughput**: Fine-tuning 4+ adapters on a single 2080 Ti while the Lab is resident. | **Guardrail**: Lab Attendant must enter `quiesce` mode (Free VRAM) before training cycles begin. |
| **[R-03]** | **Over-Specialization**: Adapters become "too clinical" and lose bantering character. | **Guardrail**: Layer the `pinky_base` adapter at 0.3 weight alongside all specialized experts. |

---
**"Verify the expert before trust the answer."**
