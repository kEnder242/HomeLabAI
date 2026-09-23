# Sprint Plan: [SPR-86.1] The DNA Dropped Ball — Phase 2: Phased Swarm Execution & Full Closure

> **Sprint Type:** Phased Execution & Defect Closure Sprint  
> **Parent Sprint:** SPR-86.0 (DNA End-to-End Audit)  
> **Status:** ACTIVE / HEADS DOWN  
> **Date:** 2026-09-21  
> **Branches:** `Portfolio_Dev` → `sprint-86`, `HomeLabAI` → `sprint-86`  
> **Applicable Laws:** BKM-024 (Live Silicon Validation), BKM-011/BKM-012 (Surgical Edits), BKM-049 (Tri-Loop Delegation, Cloud Swarm Only), BKM-060 (DNA Taxonomy)  
> **Grounding Document:** [`SPRINT_86_DEEP_DIVE_DEFICIENCY_REPORT.md`](file:///home/jallred/.gemini/antigravity-cli/brain/d75e00e7-b3f5-4236-89ea-26c97eee308c/SPRINT_86_DEEP_DIVE_DEFICIENCY_REPORT.md)

---

## 🧭 Operational Grounding Protocol
Before delegating or executing any story below, the executing agent (Primary or Cloud Swarm) MUST review the specific findings in `SPRINT_86_DEEP_DIVE_DEFICIENCY_REPORT.md` corresponding to that story.

---

## 🗺️ Phased Story Breakdown & Delegation Matrix

| Story | Title | Owner | Dispatch Mode | Deficiency Ref |
| :--- | :--- | :--- | :--- | :--- |
| **Phase A: Critical Foundation** | | | | |
| **86.1** | **Manifest Consolidation: `dna_forge_build.py` reads `dna/` directly** | `[AGY:PRIMARY]` | Local In-Session | Finding 12 + CRITICAL NEW |
| **86.2** | **`nightly_forge.py` Step Order Inversion Fix** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 1 |
| **86.3** | **Wire `nightly_lora_training.py` into Nightly Forge** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 2 |
| **86.4** | **`ensure_datasets()` Force-Rebuild Flag** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 4 |
| **Phase B: LoRA Dataset & Domain Completeness** | | | | |
| **86.5** | **FEAT Domain & RDNA Synthesis in `build_dna_polymorphic_dataset()`** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 5 |
| **Phase C: Backend Persistence Hardening** | | | | |
| **86.6** | **`mutations[]` Cleanup After Certification** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 6 |
| **86.7** | **`promote_draft_to_db` Triggers Static HTML Rebuild** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 7 |
| **86.8** | **RDNA Save Path Fix in `handle_wisdom_save_card`** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 9 |
| **86.9** | **ID Collision Fix for Non-WIS/PHL Domain Promotion** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 8 |
| **Phase D: Frontend UX Polish** | | | | |
| **86.10** | **DOM Update After `certifyMutation()` in Forge UI** | `[AGY:PRIMARY]` | Local In-Session | Finding 11 |
| **86.11** | **Rev-Pill Version Number Display** | `[AGY:PRIMARY]` | Local In-Session | Finding 11/13 |
| **Phase E: Schema Migration & Writer Alignment** | | | | |
| **86.12** | **WIS/PHL Schema Backfill Migration (`mutations[]`, `revisions[]`)** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 15 |
| **86.13** | **`writer.html` Tab 2 Voice Switcher → DNA Revision Connection** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 14 |
| **Phase F: Infra Hardening & Full Live Certification** | | | | |
| **86.14** | **`sync_chroma_dna.py` Idempotency Guard & Checksum Diff** | `[SWARM:CLOUD]` | `delegate.py --cloud-only` | Finding 17 |
| **86.15** | **Final End-to-End Live Validation Battery (`BKM-024`)** | `[AGY:PRIMARY]` | Local In-Session | All Findings |

---

## 📋 Detailed Story Execution Specifications

### Story 86.1 — Manifest Consolidation: `dna_forge_build.py` reads `dna/` directly
* **Owner:** `[AGY:PRIMARY]`
* **Grounding:** Finding 12 & Critical New Finding (`dna_manifest.json` only has 30 WIS cards while `wisdom_data.json` has 481).
* **Target Files:** `Portfolio_Dev/field_notes/dna_forge_build.py`
* **Changes:**
  - Load `wisdom_data.json`, `philosophy_data.json`, `rdna_questions.json`, `timeline_data.json` directly from `Portfolio_Dev/dna/`.
  - Assemble unified in-memory manifest for compilation.
  - Re-generate `dna_forge.html` rendering all 481+ WIS cards.

### Story 86.2 — `nightly_forge.py` LoRA Priority First & Tail Mass Scan Mop-Up Architecture (`[FEAT-416]`, `[FEAT-160]`, `[FEAT-213]`, `[FEAT-136]`)
* **Owner:** `[AGY:PRIMARY]`
* **Status:** COMPLETED
* **Grounding:** Finding 1 & Live Timeout RCA. `mass_scan.py` is an unbounded archive-wide deep note crawler that runs for 3.5–4+ hours. When placed before LoRA training, it consumed the entire 4-hour systemd maintenance window (`TimeoutStartSec=14400`), resulting in systemd SIGTERMing the process group right at 05:02 AM as LoRA training began.
* **Target Files:** `HomeLabAI/src/infra/nightly_forge.py`, `HomeLabAI/config/systemd/field-notes-nightly.service`
* **Changes & Execution Architecture:**
  1. **Pre-flight Telemetry & Power Clamp [LAB-109] (~5s):** Pre-flight health probe and GPU power limit clamped to 165W.
  2. **Quiesce Foyer / vLLM [FEAT-213] (~30s):** Evict resident weights to HIBERNATING state to reclaim VRAM down to 169MB baseline.
  3. **Priority Multi-Adapter LoRA Fine-Tuning [FEAT-160/214] (~15–30m bounded):** Runs Unsloth training (`cli_voice_v1`, `lab_history_v1`, `triage_v1`, `reviewer_v1`) FIRST while VRAM is dedicated and clean, with zero starvation risk.
  4. **Guaranteed Foyer Re-Ignition [FEAT-136] (~60s):** Foyer is re-ignited back to `OPERATIONAL` in a `finally` block, ensuring the resident models are online and responsive before 03:00 AM.
  5. **Post-Training Synthesis (~5–10m):** Subconscious Dreaming (`dream_cycle.py`), Wisdom Refinement (`refine_wisdom.py`), Sprint DNA ChromaDB Sync (`sync_sprint_dna.py`).
  6. **Dynamic Benchmark Sweep [FEAT-495] (~2m):** Runs `bench_models.py` against the freshly re-ignited resident endpoints.
  7. **Tail Mass Scan Mop-Up (`mass_scan.py` + `journal_to_dna_bridge.py`) [SPR-52.0 / FEAT-416] (Unbounded, ~1–4+ hours):** Mops up whatever remaining time exists in the maintenance window. Even if note scanning takes hours or runs indefinitely, it cannot starve LoRA training or delay lab re-ignition.
  8. **Systemd Buffer:** Increased `TimeoutStartSec=21600` (6 hours) in `field-notes-nightly.service`.

### Story 86.3 — Wire `nightly_lora_training.py` into Nightly Forge
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 2 (multi-adapter pipeline is dead; monolithic single adapter called).
* **Target Files:** `HomeLabAI/src/infra/nightly_forge.py`
* **Changes:** Replace direct `train_expert.py` single adapter call with `nightly_lora_training.py` multi-adapter orchestration.

### Story 86.4 — `ensure_datasets()` Force-Rebuild Flag
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 4 (stale lockout skips rebuild if `master_forge_curriculum.jsonl` exists).
* **Target Files:** `HomeLabAI/src/infra/nightly_lora_training.py`
* **Changes:** Add `force: bool = False` to `ensure_datasets()` and pass `--force` CLI flag down to dataset builder.

### Story 86.5 — FEAT Domain & RDNA Synthesis in `build_dna_polymorphic_dataset()`
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 5 (`FEATURES_MD` defined but unused; RDNA pairs output only routing IDs).
* **Target Files:** `HomeLabAI/src/forge/build_lora_datasets.py`
* **Changes:** Ingest `FeatureTracker.md` into FEAT training pairs; expand RDNA training pairs with full narrative synthesis.

### Story 86.6 — `mutations[]` Cleanup After Certification
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 6 (`handle_dna_certify_mutation` doesn't clear or flag `mutations[]`).
* **Target Files:** `HomeLabAI/src/v5/foyer/router.py`
* **Changes:** Mark certified mutation as `status: CERTIFIED` or remove from `mutations[]` array in domain files and manifest.

### Story 86.7 — `promote_draft_to_db` Triggers Static HTML Rebuild
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 7 (draft promotion saves JSON but does not trigger `dna_forge_build.py` / `wisdom_build.py`).
* **Target Files:** `HomeLabAI/src/curator/draft_decomposer.py`
* **Changes:** Trigger background HTML recompilation upon successful card promotion.

### Story 86.8 — RDNA Save Path Fix in `handle_wisdom_save_card`
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 9 (RDNA cards saved via REST fall back to `wisdom_data.json`).
* **Target Files:** `HomeLabAI/src/v5/foyer/router.py`
* **Changes:** Route `RDNA-*` and `rdna` collections to `Portfolio_Dev/dna/rdna_questions.json` and ChromaDB `rdna` collection.

### Story 86.9 — ID Collision Fix for Non-WIS/PHL Domain Promotion
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 8 (`max(nums, default=len(existing_col)) + 1` produces ID collisions).
* **Target Files:** `HomeLabAI/src/curator/draft_decomposer.py`
* **Changes:** Compute next IDs safely from source files for BKM, FEAT, DISC, SPRINT.

### Story 86.10 — DOM Update After `certifyMutation()` in Forge UI
* **Owner:** `[AGY:PRIMARY]`
* **Grounding:** Finding 11 (`certifyMutation()` displays alert without updating DOM pill state).
* **Target Files:** `Portfolio_Dev/field_notes/dna_forge_build.py`
* **Changes:** Dynamically replace `mut-pill` with `rev-pill` upon certification.

### Story 86.11 — Rev-Pill Version Number Display
* **Owner:** `[AGY:PRIMARY]`
* **Grounding:** Finding 11 / Flow 6 (rev-pills show only lens name, missing version `v1`, `v2`).
* **Target Files:** `Portfolio_Dev/field_notes/dna_forge_build.py`
* **Changes:** Format rev-pills as `🏆 v{i+1} {lens}`.

### Story 86.12 — WIS/PHL Schema Backfill Migration
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 15 (0/481 legacy WIS cards have `mutations` or `revisions` keys).
* **Target Files:** `Portfolio_Dev/scripts/backfill_card_schema.py`
* **Changes:** One-time migration backfilling empty `mutations: []` and `revisions: []` arrays in `wisdom_data.json` and `philosophy_data.json`.

### Story 86.13 — `writer.html` Tab 2 Voice Switcher → DNA Revision Connection
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 14 (Voice drawer operates solely on AST strings).
* **Target Files:** `Portfolio_Dev/field_notes/writer.html`, `Portfolio_Dev/scripts/build_writer.py`
* **Changes:** Wire DNA card revisions into voice drawer variants and include revisions in `window.__CITATION_INDEX__`.

### Story 86.14 — `sync_chroma_dna.py` Idempotency Guard
* **Owner:** `[SWARM:CLOUD]`
* **Grounding:** Finding 17 (unconditional delete and reload without checksum diffing).
* **Target Files:** `Portfolio_Dev/sync_chroma_dna.py`
* **Changes:** Add SHA256 checksum caching and `--dry-run` support.

### Story 86.15 — Final End-to-End Live Validation Battery (`BKM-024`)
* **Owner:** `[AGY:PRIMARY]`
* **Target Files:** Entire workspace
* **Verification:** Run pytest suite, verify ChromaDB collection counts, compile static assets, test REST endpoints on port 8765.
