# Report 2 — Sprint 44 Stories 6–8: The Journey Through Branches

**Date:** 2026-07-31
**Author:** Sisyphus (OpenAgent orchestrator)
**Scope:** FEAT-442 (QPR), FEAT-443 (PAR-Eval), FEAT-444 (Judicial Backpressure) — implementation arc across git branches, assumptions and re-assumptions, retrospective.

---

## The One-Liner

Sprint 44 (FEAT-442 QPR, FEAT-443 PAR-Eval, FEAT-444 Backpressure) went from *"implement the three features"* to *"re-architect QPR from regex to AI-driven because the feature was implemented in the wrong layer and the regex violated BKM-015"* — and the refactor was still mid-flight, uncommitted, when the sprint was stopped.

## Timeline

| When | Branch/Commit | What happened | Assumption in play |
|---|---|---|---|
| Sprint start | `main` → `d19ed0d` | Initial FEAT-442/443/444 implementation landed: QPR regex in `cognitive_hub.py` + `archive_node.py`, MLX judge refusal schema, router backpressure writer, 5x5 interceptor. 15/15 pytest green at the time. | **A1: QPR = regex refinement at retrieval time.** Matched a literal reading of FEAT-442's "pre-retrieval query de-noising" but put it *post-router* inside `get_context`. |
| — | `b918c53` | BKM-034 docs pushed: delegation mandate front-and-center. | A2: orchestration via sisyphus-junior is reliable. |
| Mid | `19cd29f` (`sprint-44-dirty-save`) | Interim dirty save of sprint-44 code. | A3: the sprint-44 work is feature-complete, just needs validation. |
| Mid | `main` vs working tree | Live integration test on `get_context` showed the "can you/about" gap — QPR regex failed to strip that framing; later re-run returned **0 candidates** (noise degradation). | A3 **falsified** — retrieval quality is degrading exactly where QPR was supposed to help. |
| Mid | Working tree on `sprint-44-blend` | **Re-assessment:** user asks "are we hard coding in QPR?" → "Because we don't need that, we have a router." I investigated, concluded "QPR redundant". | **A4: router/triage makes QPR redundant.** *Wrong.* |
| Mid | — | User corrects: look up the roundtable flow; read Protocols.md / FeatureTracker.md. | A4 **falsified** → **A5: QPR is misplaced, not redundant** — needed for HyDE, positioned before triage per docs. |
| Mid | — | **The escape found:** triage produces `hyde_vector_text` (required schema field) but nothing passes it to `get_context`. User: *"hyde vector text to get context is an escape, good catch."* | A6: the fix is wiring, not new logic. |
| Late | — | **The blend clarified:** HyDE runs on KENDER (4090) while the 2080 Ti warms; QPR+HyDE is one LLM step (user's design); warm ⇒ local triage. | A7: QPR must be AI-driven (delete regex, BKM-015), HyDE override wired through. |
| Late | Working tree (uncommitted) | Refactor executed: `qpr_refine_query` deleted; `select_vector_query` helper added; `_fetch_rag_context` wired into Pinky path + `_run_brain_leg`; 0.45 sentinel retargeted to hyde-vs-raw fallback; `test_qpr_hyde.py` rewritten. Focused suite 9/9 green. | A8: the refactor is correct and complete. **Not yet fully verified** — full suite blocked by pre-existing infra errors; live regression not run. |
| Stop | — | User: "Let's stop work on the sprint." | — |

## Assumptions Ledger (the re-assumption arc)

1. **A1:** QPR = regex refinement → **refuted** (it's AI-driven per user design & FEAT-436).
2. **A2:** delegation reliable → **refuted** (hallucinated diffs ×2).
3. **A3:** sprint-44 feature-complete → **refuted** (live retrieval degraded to 0 candidates).
4. **A4:** QPR redundant → **refuted** (needed for HyDE, before triage).
5. **A5→A8:** progressively correct, but the *journey* to them burned most of the sprint's time.

## Retrospective: why wasn't the sprint completed?

1. **The feature was implemented in the wrong layer first.** QPR-as-regex at retrieval time (post-router) was a literal reading of FEAT-442 that ignored the architecture the docs describe (unified pre-reflection pass + HyDE blend). The initial implementation was *correct code for the wrong design* — the kind of error that passes tests (15/15) while still being wrong.
2. **Validation came late.** The live test that exposed the failure (0 candidates on noisy query) came *after* the feature was declared done. BKM-024 mandates live lab testing on core edits; the early green 15/15 created false confidence.
3. **The architecture conversation consumed the latter half of the sprint.** Four assumption reversals (redundant → misplaced → escape → blend) happened through user education, not through code. A docs-first read at sprint start would have collapsed A4/A5 immediately.
4. **Verification was still in flight when stopped.** The refactor is implemented and unit-tested (9/9) but uncommitted; the full suite has 4 pre-existing collection errors (unrelated `AcmeLab` import breakage in `test_attendant_sprint20`, `test_hub_persistence`, `test_induction_mutex`, `test_lab_sprint20`); the live noisy-query regression was never run post-refactor.

---

## BKM-Protocol Dense Summary

- **One-Liner:** Correct implementation of the wrong design passes tests and still fails live; docs-first collapses assumption spirals.
- **Core Logic:** FEAT-442 must live as AI-driven QPR+HyDE in the unified pre-reflection pass (FEAT-436); the escape (`hyde_vector_text` → `get_context`) is the actual gap.
- **Trigger:** Live retrieval degrading to 0 candidates + user's "are we hard coding?" question.
- **Scars:** (1) implemented in wrong layer first, (2) validation after declaration of done, (3) four-assumption correction loop, (4) stopped mid-verification with uncommitted refactor.
