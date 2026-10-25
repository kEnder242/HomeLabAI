# 📊 Pipeline Stage & Deferred Probe Matrix (`BKM-089` / `BKM-090`)

> **Governing Standards**: 
> - [`BKM-083`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1531) (Decouple-and-Stitch Stage Isolation)
> - [`BKM-088`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1712) (Empirical Step Harness & Co-Pilot Loop)
> - [`BKM-089`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1733) (Prompt MO & Evaluation Asymmetry Protocol: *Prompts explain HOW, Prompt MO explains WHY*)
> - [`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783) (The Deferred Probe Protocol: *Prohibition of Self-Declaration & Verdictless Trace Emission*)

---

## 🏛️ Architecture Overview: The 5 Pipeline Handover Stages

Every turn in the Federated Lab cascades down a single invariant sequential Waterfall (`FEAT-658` / `_run_two_mice_handover`). 
- **The Runtime Prompts (HOW)** are kept lean and frugal to prevent instruction bleeding.
- **The Prompt MOs (WHY)** explain the epistemic motive and live out-of-band in this matrix and test rubrics.
- **The Deferred Probes ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783))** execute on live physical silicon, measure real telemetry, and emit unopinionated evidentiary traces to Layer 1 (AGY) without declaring pass/fail verdicts.

---

### Section 1: Triage Definitions (Primer $\to$ Vibe & Domain Selection)

| Pipeline Component / Target | Status (Prompt & Substrate) | Prompt MO (The Epistemic WHY) | Deferred Probe Status ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783)) |
| :--- | :--- | :--- | :--- |
| **System Context Rules** ([`_build_triage_mode_context`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L488)) | ⚠️ **Needs Hardening**: 10 vibe rules active; **`WYWO` rule missing** from prompt context. | Translate user primer into decoupled behavioral posture (`vibe`) and knowledge ontology (`domain`) without collapsing them. | 📋 **Declared**: `--stage=triage` declared in [`test_empirical_step_harness.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_empirical_step_harness.py); live silicon probe pending. |
| **Deterministic Fast-Paths** ([`_WYWO_RE`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L450)) | 🔴 **Orphaned**: Regex defined at L450 but dead code; bypass logic removed in Sprint 64 (`FEAT-536`). | Instantly anchor obvious standup and absence catchup queries into `WYWO` / `dream_stream` to prevent 3B triage misclassification. | 📋 **Pending**: Probe must verify fast-path triggers in $<5\text{ms}$ with zero LLM inference. |
| **Declarative Policy Mapping** ([`config/triage_policy.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/triage_policy.json)) | 🟡 **Draft**: `vibe` definitions exist; decoupled `vibe_registry` and `domain_hooks` schema pending. | Provide external, hot-reloadable defaults for importance floors, interest boosts, and hook targets without editing Python code. | 📋 **Pending**: Schema validation probe to verify JSON parsing without schema drift. |

---

### Section 2: Post-Triage Vibe $\to$ Situational Contextual-Prompt Mapping

| Pipeline Component / Target | Status (Prompt & Substrate) | Prompt MO (The Epistemic WHY) | Deferred Probe Status ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783)) |
| :--- | :--- | :--- | :--- |
| **`WYWO`** (`[MODE]: STANDUP`) | 🔴 **Disconnected**: String at [`cognitive_hub.py:2000`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L2000); not passed to handover. | Jason was away; summarize overnight node debates, stored DNA wisdom, and system health so Jason can set priorities. | 📋 **Pending**: Emits trace testing standup structure and forward-looking priority. |
| **`CASUAL`** (`[MODE]: CASUAL_GREETING`) | 🔴 **Disconnected**: String at [`cognitive_hub.py:1915`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1915); not passed to handover. | Jason offered pleasantry; deliver a warm, laconic in-character greeting without dumping unprompted vitals or tasks. | 📋 **Pending**: Emits trace testing brevity ($\le 1$ sentence) and warmth. |
| **`unclear`** (`[MODE]: SPECULATIVE_FOIL`) | 🔴 **Disconnected**: String at [`cognitive_hub.py:2011`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L2011); not passed to handover. | Intent is ambiguous; deliver an inquisitive, playful 1-sentence foil presenting likely options rather than guessing. | 📋 **Pending**: Emits trace testing clarifying inquiry without hallucinated facts. |
| **`ZERO_CONTEXT`** (`[MODE]: NEGATIVE_IMPLICATION`) | 🔴 **Disconnected**: String at [`cognitive_hub.py:2036`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L2036); not passed to handover. | In an 18-year archive, absence of evidence is evidence of absence; definitively state absence rather than passively asking. | 📋 **Pending**: Emits trace testing direct assertion of absence without hedging. |
| **`TECHNICAL` / `TACTICAL`** (`[MODE]: TECHNICAL_TLDR`) | 🟡 **Rigid**: Hardcoded at [`cognitive_hub.py:624`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L624); needs parameterization. | Ground discussion in engineering reality; deliver a crisp 2-sentence conversational TL;DR directly to Jason. | 📋 **Scaffolded**: `--stage=pinky` active in [`test_empirical_step_harness.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_empirical_step_harness.py). |
| **`OPERATIONAL`** (`[MODE]: SRE_VITALS`) | 🟡 **Draft**: `vibe` definition exists in `triage_policy.json` but Prompt MO and deferred probe criteria need authoring. | Urgent system telemetry requested; deliver high-urgency, compact summary of GPU thermals, power caps, and vitals. | 📋 **Defined**: Prompt MO and deferred probe criteria authored; Schema and substrate hooks pending. |
| **`FORENSIC`** (`[MODE]: CRASH_AUTOPSY`) | 🟡 **Draft**: `vibe` definition exists in `triage_policy.json` but Prompt MO and deferred probe criteria need authoring. | System fault detected; highlight faulting kernel module, panic trace signature, and diagnostic playbook. | 📋 **Defined**: Prompt MO and deferred probe criteria authored; Schema and substrate hooks pending. |
| **`METABOLIC`** (`[MODE]: DNA_CURATION`) | ⚪ **Missing**: Needs authoring in `triage_policy.json`. | Curation requested; focus on DNA spine refinement, memory pruning, and deduplication trade-offs. | 📋 **Pending**: Emits trace testing curation objectivity. |
| **`SOCRATIC`** (`[MODE]: ARCHITECTURAL_WHY`) | ⚪ **Missing**: Needs authoring in `triage_policy.json`. | Conceptual inquiry; explore architectural trade-offs and complexity conservation ([`INS-038`](file:///home/jallred/Dev_Lab/Portfolio_Dev/FeatureTracker.md)) without jumping to code. | 📋 **Pending**: Emits trace testing dialectic reasoning and trade-off weighing. |
| **`CHRONICLE`** (`[MODE]: HISTORICAL_RECAP`) | ⚪ **Missing**: Needs authoring in `triage_policy.json`. | Historical career inquiry; recount past hardware epochs with authentic engineering perspective and scars. | 📋 **Pending**: Emits trace testing chronological accuracy against career ledger. |

---

### Section 3: Triage Domain $\to$ Data / Substrate Hooks

| Pipeline Component / Target | Status (Prompt & Substrate) | Prompt MO (The Epistemic WHY) | Deferred Probe Status ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783)) |
| :--- | :--- | :--- | :--- |
| **`dream_stream`** | 🟡 **Draft**: 5 disk JSONs read at handover; exact schema and paths now specified below. Needs `[CHUNK-N]` serialization. | Ingest volatile overnight state not yet indexed in vector DB, serializing into `[CHUNK-N]` blocks for Brain's Gatekeeper. | 📋 **Declared**: `--stage=rag` in harness; needs chunk serialization validation. |
| **`feedback` / `lab_internal` (META)** | 🟡 **Draft**: 2 META files read at handover; exact schema and paths now specified below. Needs `[CHUNK-N]`. | Ground supervisory and meta-correction turns in past validation failures and state transitions rather than speculative defense. | 📋 **Pending**: Emits trace testing delta chunking and fourth-wall ground truth. |
| **`exp_tlm`** | 🟡 **Direct Sensor Substrate**: Direct MSR/RAPL and NVML read; lacks uniform chunking. | Ground operational turns in live hardware vitals without pulling irrelevant archival history. | 📋 **Pending**: Probe testing live sensor read latency ($<50\text{ms}$). |
| **`exp_for`** | 🟡 **Raw Log Substrate**: Raw dmesg / journalctl dumps; lacks chunk keying. | Provide raw crash artifacts to Brain's Gatekeeper to isolate faulting line without prompt truncation. | 📋 **Pending**: Probe testing log sanitization and chunk bounding. |
| **`lab_history` / `work_history`** | 🟢 **Vector Substrate Active**: ChromaDB `:8001` (`career_ledger`, `artifact_vault`, `wisdom_dna`). | Retrieve 18-year engineering career ground truth and project notes based on HyDE search vectors. | 📋 **Scaffolded**: Validated in litmus tests (Purley / Aurora queries). |
| **`standard`** | 🟢 **Contract Substrate Active**: `feature_dna` / `behavioral_dna`. | Ground architectural turns in formal system specifications and invariant contracts. | 📋 **Pending**: Probe asserting feature invariant recall. |


---

#### Section 3a: Dream Stream Substrate — Exact Schema & Paths

| File | Path | Schema / Structure |
| :--- | :--- | :--- |
| **nightly_dialogue.json** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json` | ``{ "timestamp": "YYYY-MM-DD HH:MM:SS", "topic": "...", "content": "string", "type": "WYWO_MORNING_BRIEFING", "creative_ideas": ["string"] }`` |
| **status.json** | `~/Dev_Lab/HomeLabAI/status.json` | ``{ "active_domain": "string", "timestamp": "ISO8601" }`` — active domain fallback for MCompassRAG |
| **pager_activity.json** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json` | ``{ "activity": "string", "timestamp": "ISO8601" }`` |
| **recruiter_report.json** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json` | ``{ "topic": "string", "content": "string", "timestamp": "ISO8601" }`` |
| **subconscious dreams** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/` (directory) | Long-term consolidated dream digests harvested via `harvest_subconscious_dream()` in `floating_oracle.py`; consumed as `[SUBCONSCIOUS_DREAM]` chunk block |

---

#### Section 3b: META Substrate — Exact Schema & Paths

| File | Path | Schema / Structure |
| :--- | :--- | :--- |
| **validation_ledger.jsonl** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/validation_ledger.jsonl` | JSONL records: ``{ "ts": epoch, "mode": "string", "vibe": "string", "domain": "string", "error": "string", "context": "string" }`` — [BKM-035] FAIL records from `feedback_interceptor` |
| **round_table_deltas.json** | `~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table_deltas.json` | ``{ "deltas": [{ "timestamp": "ISO8601", "source": "string", "delta": "object", "summary": "string" }] }`` — State updates from `blackboard_ledger` |

---

### Section 4: Council Deliberation Funnel (Brain Filter & Deep Thought Blend)

| Pipeline Component / Target | Status (Prompt & Substrate) | Prompt MO (The Epistemic WHY) | Deferred Probe Status ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783)) |
| :--- | :--- | :--- | :--- |
| **Brain's Filter** ([`step_brain_gatekeeper`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L3089)) | 🟢 **Prompt Codified**: Keyed filter prompt at [`cognitive_hub.py:601`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L601) (`Story 108.1`). | Information Gatekeeper. Inspects `[CHUNK-N]` candidate records line-by-line; emits `KEEP`/`DROP` decisions to forward bedrock truth. Never writes essays. | 🟢 **Scaffolded**: Live test rig active in [`test_empirical_step_harness.py --stage=filter`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_empirical_step_harness.py); ready for prompt shootout. |
| **Deep Thought's Blend** ([`step_deep_thought`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L3139)) | 🟡 **Prompt Active**: Prompt at [`cognitive_hub.py:3175`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L3175); needs unburdening from Pinky prompts. | Strategic Architect. Synthesizes high-authority engineering reality strictly from kept chunks and Pinky's opening stance. Persona-agnostic, paced by interest. | 🟢 **Scaffolded**: Live test rig active in [`test_empirical_step_harness.py --stage=dt`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_empirical_step_harness.py); ready for pacing shootout. |

---

### Section 5: Voice Delivery & Intercom Append (Pinky Reply & The Critic)

| Pipeline Component / Target | Status (Prompt & Substrate) | Prompt MO (The Epistemic WHY) | Deferred Probe Status ([`BKM-090`](file:///home/jallred/Dev_Lab/HomeLabAI/docs/Protocols.md#L1783)) |
| :--- | :--- | :--- | :--- |
| **Pinky's Spoken Voice** ([`step_pinky_voice`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L3223)) | 🟡 **Prompt Needs Refinement**: Prompt at [`cognitive_hub.py:623`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L623); needs contextual-prompt layering + 10% pacing rule. | Deliver compressed conversational TL;DR / standup directly to Jason on Left Console. Translates Brain's synthesis into action in $\le 10\%$ of Deep Thought's length. | 🟢 **Scaffolded**: Live test rig active in [`test_empirical_step_harness.py --stage=pinky`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/test_empirical_step_harness.py); ready for shootout. |
| **Adversarial Intercom Append** ([`step_entailment_audit`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L3275)) | 🟡 **Concept Locked**: Core decoupled in `Story 108.2`; append prompt and Intercom card pending in `Story 108.7`. | Out-of-band audit caught an inconsistency or misattribution in Deep Thought's synthesis. Interject as an immediate continuation to Jason and Brain, defending Jason's intent. | 📋 **Declared**: `--stage=audit` declared in harness; probe must emit trace capturing continuation flow and contrastive pivot. |
