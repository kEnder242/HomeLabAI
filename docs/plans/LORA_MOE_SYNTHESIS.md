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

### 📍 Phase 7: Surgical Restoration Sprint (The "Parity Pass")
**Status:** INFRASRUCTURAL COMPLETE | **Logic Drift Identified**
**Objective:** Eliminate stubs and "Lost Gems" to achieve 100% technical parity.

- **[FEAT-191] Hardware Status Tools**: (COMPLETED) implemented in `archive_node.py`.
- **[FEAT-192] Engine Priming (The "Blink")**: (COMPLETED) implemented in `loader.py`.
- **[RE-FEAT-045] The "Bounce" Reflex**: (COMPLETED) `bounce_node` live.
- **[RE-FEAT-082] Memory Scribble**: (COMPLETED) `scribble_note` live.
- **[RE-FEAT-193/194] Historical/CV Strategy**: (COMPLETED) plumbed.
- **[FEAT-179] The Hallway Protocol (Ignition)**: (COMPLETED) Live keyword scan.

### 📍 Phase 8: Distillation Ignition (The "Expert" Forge)
**Status:** ACTIVE (Staged)
- **[FEAT-161.1] Distillation Script**: (COMPLETED) `src/forge/distill_gems.py`.
- **[FEAT-161.2] Test Distillation**: (COMPLETED) 4090 test batch forged.
- **[FEAT-160.1] Training Scaffolding**: (COMPLETED) Unsloth ready.
- **[FEAT-160.2] Full Scale Training**: (PENDING) Awaiting Burn completion.

---

## 🏗️ Phase 9: Semantic Alignment (The BKM-015 Refactor)
**Objective:** Replace brittle, hard-coded keyword lists with recovered high-fidelity logic anchors.

### 📍 Immediate Alignment Tasks:
- **[FEAT-174.1-FIX] Vector Routing**: 
    - **Rationale**: BKM-015 Rule of the Ghost Keyword.
    - **Mechanism**: Move technical anchors (`rapl`, `silicon`) into `config/intent_anchors.json`.
- **[FEAT-027-FIX] Shadow Moat (Triage)**:
    - **Rationale**: BKM-015 Vibe-First Mandate.
    - **Mechanism**: Replace `strat_keys` in `acme_lab.py` with Hub intent classification.
- **[FEAT-154-ACTIVATE] Density-Aware Vibe**:
    - **Rationale**: Sentient Sentinel logic.
    - **Mechanism**: Use `turn_density` to adjust classification thresholds.
- **[FEAT-178-ACTIVATE] Deep Map Routing**:
    - **Rationale**: Global Topography grounding.
    - **Mechanism**: Plumb `semantic_map.json` into the Hub.
- **[FEAT-176-RECOVER] Deep-Connect Restoration**:
    - **Source**: `lost_nibble.py` (Commit `303562b`).
    - **Task**: Restore "Reverse RAG" evidence harvesting in `nibble.py`.
- **[FEAT-171-RECOVER] Lifecycle Matrix Restoration**:
    - **Source**: `lost_acme.py` (Commit `0ca8901`).
    - **Task**: Restore `SERVICE_UNATTENDED` vs `DEBUG` idle timer matrix.
- **[GHOST-01-RECOVER] Parallel Turn Bundler**:
    - **Source**: `lost_hub.py` (Commit `8a3a230`).
    - **Task**: Re-implement `asyncio.wait(pending, return_when=FIRST_COMPLETED)`.

---

## 🏺 Distilled Lost Gems (Restoration Anchors)
*These code fragments are for sub-agent implementation or minimal surgical recovery.*

### 💎 Gem 1: DEEP_CONNECT Mode (`nibble.py`)
```python
is_deep_connect = task.get("mode") == "DEEP_CONNECT"
if is_deep_connect:
    prompt = f"""
    [ROLE] You are 'Pinky', a high-fidelity technical forensic investigator.
    [STRATEGIC SEEDS] {strategic_context}
    [TASK] Perform 'Reverse RAG'. Analyze the RAW LOGS to find specific 'Technical Evidence'.
    1. Harvest high-density technical blocks (50-100 words).
    2. Focus on: Error traces, register values, post-mortem logic.
    Return a JSON list of EVIDENCE pairs:
    [{"date": "YYYY-MM-DD", "summary": "...", "evidence": "...", "tags": [...]}]
    """
```

### 💎 Gem 2: Intelligent Socket Matrix (`acme_lab.py`)
```python
async def manage_session_lock(self, active: bool):
    if active:
        if self._disconnect_task: self._disconnect_task.cancel()
        if self.connected_clients:
            with open(ROUND_TABLE_LOCK, "w") as f: f.write(str(os.getpid()))
    else:
        if not self.connected_clients:
            if self.mode == "SERVICE_UNATTENDED":
                logging.info("[SOCKET] Persistence Mode: Staying resident.")
                return
            if not self._disconnect_task:
                self._disconnect_task = asyncio.create_task(self._delayed_lock_clear())
```

### 💎 Gem 3: Parallel Turn Bundler (`cognitive_hub.py`)
```python
# [PHASE 2] Turn Bundling: Collect all responses
pending = {t for t, s in dispatch_tasks}
task_to_source = {t: s for t, s in dispatch_tasks}
bundled_results = []
try:
    async with asyncio.timeout(120):
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                res = await task
                source = task_to_source[task]
                bundled_results.append({"source": source, "text": res.content[0].text})
except asyncio.TimeoutError:
    for t in pending: t.cancel()
```

---

## 🏛️ Final Session Report: The "Parity" Audit [March 10, 2026]
(Summary of restoration completion and remaining stubs...)
