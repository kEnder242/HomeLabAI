# Sprint Plan: [SPR-88.0] The Nightly Accountability Protocol — Quantifiable Verification Matrix & Synthetic Deliberation (`FEAT-607` / `FEAT-608` / `LAB-110` / `BKM-062`)

> **Sprint Type:** Observability, Telemetry, Synthetic Probing & Operational Accountability  
> **Parent Sprints:** SPR-86.1 (DNA Dropped Ball), SPR-42.0 (Nightly Synthesis)  
> **Status:** PROPOSED / BRAINSTORMING  
> **Date:** 2026-09-23  
> **Branches:** `Portfolio_Dev` → `main`, `HomeLabAI` → `main`  
> **Applicable Laws:** BKM-002 (Montana Protocol), BKM-014 (Neural Pager / Deep Dive), BKM-024 (Live Silicon Validation), BKM-062 (Accountability Protocol), FEAT-416 (Single-Epoch Cutoff), FEAT-464 (Vitals Modernization), FEAT-607 (Accountability Digest), FEAT-608 (Synthetic Round Table Probe), LAB-110 (Quantifiable Accountability Invariants)  

---

## 🎯 Strategic Objective
Codify **The Accountability Protocol** across the entire Federated Lab. Replace superficial process exit codes and static frozen vitals with an **End-to-End Quantifiable Accountability Matrix** that evaluates non-zero units of work, conducts automated morning Round Table synthetic deliberation probes, and aggressively exposes the **"Green Lie"** (where daemons report online while cognitive loops are broken).

---

## 📊 The Quantifiable Accountability Matrix (11 Verifiable Stages)

Every nightly stage is held accountable to concrete, non-zero numeric telemetry. A process return code of `0` without verified work units is treated as a **Critical Zero-Work Failure**.

| # | Pipeline Stage | Target Module | Quantifiable Accountability Metric | Silent Failure / Zero-Work Trap Excluded |
| :- | :--- | :--- | :--- | :--- |
| **1** | **GPU Power Clamp** | `verify_gpu_power_limit()` | Target: `165W`, Live Wattage, Load Avg. | `nvidia-smi` missing/errored but returning `True`. |
| **2** | **VRAM Quiesce** | `quiesce_vllm()` | Post-quiesce VRAM: `MB` (Threshold: $\le 250\text{ MB}$). | HTTP 200 returned but zombie threads holding GPU VRAM. |
| **3** | **Curriculum Build** | `build_dna_polymorphic_dataset()` | Dialogue pairs ($N \ge 100$), File size (`KB`), 6 domains. | Stale dataset reuse; generating 0 pairs or 0-byte file without error. |
| **4** | **Multi-LoRA Training** | `nightly_lora_training.py` | Adapters trained ($N$ of 4), Steps ($N_{\text{steps}} \ge 300$), Loss. | **Zero-Work Exit:** Exits code 0 with `adapters_trained: []` (0 steps executed). |
| **5** | **Lab Re-Ignition** | `re_ignite_vllm()` | Foyer state (`OPERATIONAL`), Reload latency (s). | Foyer reports 200 but backend vLLM port 8088 is dead/hung. |
| **6** | **Accountable Dreaming** | `dream_cycle.py` | Candidates scanned ($N \ge 1$), Synthesized tokens ($N_{\text{tok}} > 50$), Output diamonds. | **Zero-Candidate Trap:** Exits in 0.1s without inspecting or synthesizing memory turns. |
| **7** | **Wisdom Synthesis** | `refine_wisdom.py` | Cards parsed ($N \ge 480$), Duplicates merged ($N$), Revision count. | Silent early exit due to path or schema drift. |
| **8** | **ChromaDB Sync** | `sync_sprint_dna.py` | Total vector count ($\ge 600$), Collections validated (6). | Port 8001 connection error caught silently. |
| **9** | **Benchmark Sweep** | `bench_models.py` | Live TTFT (ms), Throughput (tok/s), Live endpoints. | Hardcoded fallback mock estimates used without flagging degradation. |
| **10** | **Synthetic Round Table** | `probe_round_table_accountability.py` | Triage latency ($< 400\text{ms}$), Pinky tokens ($> 10$), Brain tokens ($> 50$), Critic score ($> 0.70$). | Flags critical discrepancy if individual daemons are online but mice are mute. |
| **11** | **Tail Mass Scan** | `mass_scan.py --once` | Queue consumed ($N$), Gems refined ($N$), Duration vs 5AM cutoff. | Terminates in 1s due to leftover `.lock` file. |

---

## 🚦 Strict Evaluator Matrix (Green vs. Yellow vs. Red)

### 🟢 GREEN: Certified Operational Pass
* **Mandatory Non-Zero Work:** Every stage shows verified non-zero units processed.
* **LoRA Multi-Adapters:** $\ge 3$ of 4 discrete adapters trained with $\ge 100$ steps each ($N_{\text{steps}} \ge 300$).
* **Subconscious Dreaming:** $\ge 1$ diamond wisdom turn synthesized with $> 50$ generated tokens.
* **Synthetic Round Table Accountability Probe:** 
  - "Hi Mice" fast probe passes within SLA ($\text{TTFT} < 400\text{ms}$).
  - Full deliberation probe passes: Triage classified, Pinky quip emitted, Brain analysis produced, Deep Thought replied, Pinky Critic score $\ge 0.70$.
* **Live Re-Ignition:** Foyer `OPERATIONAL` on Git HEAD + vLLM TTFT $< 600\text{ ms}$.
* **ChromaDB Active:** Port 8001 reachable with $\ge 500$ vectors across all 6 collections.
* **Window Discipline:** Concluded in $\le 3.5\text{ hours}$ and before 05:00 AM.

### 🟡 YELLOW: Degraded / Partial Execution
* **Partial LoRA:** Exactly 1 or 2 adapters trained, or 1 non-critical adapter failed (e.g. `lab_history_v1`).
* **Partial Round Table Probe:** Triage and Brain succeeded, but Deep Thought or Critic timed out (local fallback mode).
* **Benchmark Fallback:** Live benchmark probe timed out and fell back to estimated baselines.
* **Queue Incomplete:** `mass_scan.py` gracefully yielded at 05:00 AM with remaining items in queue.

### 🔴 RED: Critical Failure / Silent Zero-Work Trap / Green-Lie Discrepancy
* **The "Silent Pass" Trap:** 0 adapters trained ($N_{\text{trained}} = 0$) OR 0 training steps executed, even if returncode is 0.
* **The "Green Lie" Discrepancy:** Individual daemon vitals report `ONLINE/OPERATIONAL`, but the synthetic Round Table probe failed completely (mice are mute/broken).
* **Empty / Corrupted Outputs:** 0-byte dataset generated, or adapter weights directory missing.
* **VRAM Collision Abort:** Quiesce failed / VRAM $> 500\text{ MB}$ (training aborted).
* **Dead Lab at Dawn:** Foyer failed to re-ignite, or left stranded in `HIBERNATING` / `SWAPPING` state.
* **Fatal Process Crash:** Unhandled Python exception, SIGKILL, SIGSEGV, or systemd timeout kill.

---

## ⚙️ Centralized Lab Configuration (`lab_accountability_thresholds.json`)

All quantitative limits are stored in [`HomeLabAI/config/lab_accountability_thresholds.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/lab_accountability_thresholds.json):
```json
{
  "power_clamp_watts": 165,
  "vram_quiesce_max_mb": 250,
  "min_curriculum_dialogue_pairs": 100,
  "min_lora_adapters_trained_green": 3,
  "min_lora_steps_per_adapter": 100,
  "max_maintenance_duration_hours": 3.5,
  "strict_cutoff_hour": 5,
  "dream_min_tokens_synthesized": 50,
  "round_table_probe": {
    "max_triage_latency_ms": 400,
    "min_pinky_tokens": 10,
    "min_brain_tokens": 50,
    "min_thought_tokens": 40,
    "min_critic_score": 0.70
  },
  "min_chromadb_vectors": 500
}
```

---

## 🧬 DNA Registration: `[LAB-110]`, `[BKM-062]`, `[FEAT-607]`, `[FEAT-608]`

* **`[LAB-110]` The Operational Accountability Standard (Quantifiable Verification Invariants):**
  - Registered in `FeatureTracker.md`, `LAB_INFRASTRUCTURE.md`, and ChromaDB.
  - Defines the core rule: Zero-work exits and superficial exit codes are forbidden. All status evaluations must verify non-zero units against `lab_accountability_thresholds.json`.
* **`[BKM-062]` The Green-Lie Prevention Protocol:**
  - Mandates end-to-end synthetic conversational probing to prevent false-positive dashboard states.
* **`[FEAT-607]` Nightly Accountability Digest & Dashboard Integration:**
  - Emits `data/daily_accountability_digest.json` and renders the `[+] ACCOUNTABILITY DIGEST` card in `status.html`.
* **`[FEAT-608]` Synthetic Morning Round Table Accountability Probe:**
  - The automated test harness executing "Hi Mice" and Deep Deliberation probes post-re-ignition.

---

## 📋 Phased Story Execution Breakdown

### Phase 1: Configuration & DNA Grounding (`HomeLabAI` & `Portfolio_Dev`)
- [ ] **Story 88.1 [AGY:PRIMARY]: Register `[LAB-110]`, `[BKM-062]`, `[FEAT-607]`, `[FEAT-608]` in DNA & Author `lab_accountability_thresholds.json`**
  - Create `HomeLabAI/config/lab_accountability_thresholds.json`.
  - Register all four entries in `FeatureTracker.md`, `Protocols.md`, `LAB_INFRASTRUCTURE.md`, and ChromaDB.

### Phase 2: Accountable Dreaming & Round Table Accountability Probe (`HomeLabAI`)
- [ ] **Story 88.2 [SWARM:CLOUD]: Dream Pass Accountability Refactor**
  - Update `HomeLabAI/src/dream_cycle.py` to enforce $\ge 1$ synthesis turn, track token counts, and emit structured JSON telemetry.
- [ ] **Story 88.3 [SWARM:CLOUD]: Synthetic Morning Round Table Accountability Probe (`probe_round_table_accountability.py`)**
  - Create `HomeLabAI/src/infra/probe_round_table_accountability.py`.
  - Execute "Hi Mice" warmup and full technical deliberation test against active Foyer endpoints (:8765).
  - Verify Triage routing, Pinky quip, Brain technical output, Deep Thought response, and Pinky Critic score.

### Phase 3: Orchestrator Synthesis & Accountability Digest Emitter (`HomeLabAI`)
- [ ] **Story 88.4 [SWARM:CLOUD]: Nightly Accountability Digest Emitter & Multi-Metric Evaluator**
  - In `HomeLabAI/src/infra/nightly_forge.py`, implement `evaluate_nightly_accountability(telemetry_dict)` reading thresholds from `lab_accountability_thresholds.json`.
  - Execute `probe_round_table_accountability.py` post-re-ignition.
  - Compile atomic metrics dictionary across all 11 stages and write `Portfolio_Dev/field_notes/data/daily_accountability_digest.json`.
  - Trigger Neural Pager event `[ACCOUNTABILITY DIGEST]`.

### Phase 4: Frontend Modernization & Green-Lie Sentry (`Portfolio_Dev`)
- [ ] **Story 88.5 [AGY:PRIMARY]: `status.html` Interleaved Accountability Card with Expandable Evidence Drawer**
  - Render color-coded `[+] ACCOUNTABILITY DIGEST` card in interleaved timeline with full 11-metric expandable breakdown.
- [ ] **Story 88.6 [AGY:PRIMARY]: Daily Accountability Briefing Grid & Green-Lie Discrepancy Sentry**
  - Replace stale `data/status.json` cards with **Daily Accountability Briefing Cards** (Morning Sweep, Active LoRAs, Silicon State, Dynamic Benchmarks, Round Table Status).
  - Implement **Green-Lie Sentry**: if individual daemons report green but the Round Table probe is degraded/failed, force top status banner to Amber/Red with explicit discrepancy breakdown.
