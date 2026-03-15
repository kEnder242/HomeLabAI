# Playbook: Silicon Induction (The Living Ledger)
**Role: [SOP] - Technical Pedigree Pipeline**

This playbook defines the multi-stage cycle for moving the Acme Lab from **Prompted Intelligence** to **Native Weight-Based Instinct**. It ensures that 18 years of technical data are surgically extracted, refined, and trained into LoRA adapters.

---

## 🛠️ The Pipeline Sequence

### Stage 1: Raw Capture (Harvesting)
*   **Script**: `HomeLabAI/src/forge/deep_connect_epoch_v2.py`
*   **Input**: `Portfolio_Dev/field_notes/data/20*.json` (Rank 4/5 gems).
*   **Goal**: Query the Brain Node to find the exact 100-word "Bones" (technical paragraphs) in the raw notes.
*   **Output**: `HomeLabAI/src/forge/expertise/raw_stage_1.jsonl` (Persistent buffer).
*   **Command**: `python3 src/forge/deep_connect_epoch_v2.py`
*   **Validation**: `wc -l raw_stage_1.jsonl` (Should reach ~100 entries).

### Stage 2: Surgical Refinement (Curating)
*   **Script**: `HomeLabAI/src/forge/refine_bones.py`
*   **Input**: `raw_stage_1.jsonl`
*   **Goal**: Apply **Bicameral Bridge signal cleaning** to raw LLM outputs. Extract only the technical context.
*   **Output**: `HomeLabAI/src/forge/expertise/bkm_master_manifest.jsonl` (Final training-ready blocks).
*   **Command**: `python3 src/forge/refine_bones.py`
*   **Validation**: Success count should match input line count.

### Stage 3: LoRA Distillation (Formatting)
*   **Script**: `HomeLabAI/src/forge/distill_gems.py`
*   **Goal**: Transform BKMs into instruction-tuning pairs (Prompt/Response) for Unsloth.
*   **Output**: `expertise/sentinel_training_data.jsonl`

### Stage 4: Induction (Training)
*   **Script**: `HomeLabAI/src/train/train_expert.py`
*   **Goal**: Execute local fine-tuning on the 2080 Ti to create the `lab_sentinel_v1` adapter.

---

## 🛡️ Critical Invariants
1.  **Decoupling**: NEVER combine Stage 1 and Stage 2 in a single monolithic script. Inference is fragile; parsing is iterative.
2.  **Physical Truth**: Technical context must remain 100% faithful to the original engineering logs. No summarization.
3.  **Residency**: All capture must be performed on the **Unified Tier** (3B-AWQ) to ensure the Lab Node's situational awareness matches the target training model.

---
**"Data is the bones, LLM is the muscle, flow is the tendons."**
