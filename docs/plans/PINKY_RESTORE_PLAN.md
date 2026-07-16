# 📖 PINKY RESTORE PLAN (Sprint 40)

This plan details the steps required to restore the `pinky` node subprocess, align the triage prompts, and enforce required metrics in `triage_schema` to unlock cascade and grounding capabilities.

---

## 1. Diagnostics & Root Cause

1. **Pinky Subprocess Defunct:** An `IndentationError: unexpected indent` at line 11 of [pinky_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_node.py#L11) prevented the stdio subprocess from booting.
2. **Schema Defaulting:** The `triage_schema` in `cognitive_hub.py` omitted `casual`, `intrigue`, and `importance` from the `"required"` array. Without explicit prompting or constraints, vLLM's guided decoding omitted these fields, causing downstream waterfall cascades and grounding critiques to default to `0.25 <= 0.5` (gated off).
3. **Contradicting Directives:** [pinky_node.py](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_node.py#L11-L20) has contradicting styling directives:
   * Directive 5: `REFRAIN FROM: Writing markdown`
   * Directive 7: `RESPONSE FORMAT: Structure technical responses with clear markdown.`

---

## 2. Step-by-Step Restoration Plan

### Phase 1: Code Repair (Subagent Execution)
1. **Fix `pinky_node.py` Indentation:**
   * De-indent the `PINKY_SYSTEM_PROMPT` block so it is defined at module-level (0 spaces).
2. **Fix `pinky_node.py` Styling Prompt:**
   * Remove Directive 5 (`REFRAIN FROM: Writing markdown`). Clean up the prompt to allow brief, structured markdown bulletins.
3. **Enforce required fields in `cognitive_hub.py`:**
   * Add `"casual"`, `"intrigue"`, and `"importance"` to the `triage_schema` `"required"` list (lines 584-586 of `cognitive_hub.py`).
4. **Update `lab_node.py` Prompt:**
   * Add a section to the `LAB_SYSTEM_PROMPT` outlining how the sentinel should assign metrics:
     * `casual`: `1.0` if chatty or casual, `0.0` if strictly technical.
     * `intrigue`: `1.0` if abstract, complex, or multi-node consensus is needed, `0.0` if factual or simple.
     * `importance`: `1.0` if critical system telemetry, code modifications, or errors, `0.0` if standard chat.

### Phase 2: Verification (Lint-Gated)
1. **Compilability Test:**
   * Verify that the node compiles: `python3 -m py_compile HomeLabAI/src/nodes/pinky_node.py`
2. **Triage Unit Tests:**
   * Run the test suite to verify routing: `pytest HomeLabAI/src/tests/test_triage_v5.py`
3. **Telemetry & Log Checks:**
   * Verify the `telemetry_ledger.jsonl` logs successful `think` calls from `pinky`.

---

## 3. Retrospective: Where did linting fail?

1. **Subprocess Isolation:** `pinky_node.py` is loaded dynamically at runtime via subprocess/stdio stdio_client. It is **not** imported by the parent Foyer webserver at boot. Thus, parent static analysis checks did not automatically trigger standard Python compilation on the node files.
2. **Manual User Commits Bypass:** The commit `abaadd3` was committed manually by the user, bypassing the `git` pre-commit hooks or automated pipeline testing.
3. **Assumed Gating:** Standard lint checks (Ruff) were assumed to run on both sides, but neither side performed them for `abaadd3`.

**BKM Action:** Standardize `python3 -m py_compile` checks for all files in `src/nodes/` during workspace test sweeps.
