# Report 3 — Honest Code Review: Keep vs. TBD

**Date:** 2026-07-31
**Author:** Sisyphus (OpenAgent orchestrator)
**Scope:** Sprint 44 (FEAT-442 QPR, FEAT-443 PAR-Eval, FEAT-444 Backpressure) — what to keep, what is still TBD or complicated.

---

## Keep — the simple stuff that was right early

| File | Change | Verdict |
|---|---|---|
| `src/v5/foyer/router.py` | `JUDGE_BACKPRESSURE_PATH` JSONL writer (FEAT-444) | **Keep.** Self-contained, streams judge findings, non-blocking. Simple. |
| `src/nodes/mlx_judge_node.py` | Refusal payload `{refusal, reason: PREMISE_MISMATCH}` (FEAT-443) | **Keep.** Small, well-scoped schema addition. |
| `src/debug/uber_5x5_v5.py` | Refusal interceptor: score validated refusals 5/5 (FEAT-443) | **Keep.** The semantic heart of PAR-Eval; aligns with the "validated refusal = intelligence" goal. |
| `generate_judge_ledger.py` + `status.html` | `[JUDGE]` amber badge + curated ledger (FEAT-444) | **Keep.** Renderer is fire-and-forget; build_site.py re-run. |
| `src/tests/test_par_eval_scoring.py` | PAR-Eval scoring tests | **Keep.** Matches repo conventions. |
| `narf` preservation principle | Pinky's catchphrase is a domain vocal signal, not noise | **Keep the principle** (regex itself now deleted). |

## The complicated part that waffled — QPR (FEAT-442)

### What got implemented (in the final refactor)
- **Deleted:** `qpr_refine_query` regex (BKM-015 violation, redundant with AI pass) from `cognitive_hub.py` and `archive_node.py`.
- **Added:** `select_vector_query(query, hyde_vector_text)` — pure helper in `archive_node.py`; picks HyDE override when substantive (>10 chars), else raw query.
- **Added:** `CognitiveHub._fetch_rag_context(turn, t_parsed)` — post-triage RAG retrieval passing `hyde_vector_text` into `get_context`; injected as `[RAG_CONTEXT]` into the Pinky path (~line 849) and `_run_brain_leg` (~line 1152).
- **Retargeted:** the 0.45 distance sentinel — now falls back to the *raw user query* when the HyDE vector's top distance > 0.45 (`vector_query != query`), preserving FEAT-442's "keep original as fallback" semantics without regex.
- **Tests:** `test_qpr_hyde.py` rewritten — 5 tests on `select_vector_query` + FEAT-437 param contract + BKM-015 lock (`qpr_refine_query` must not reappear). Focused suite 9/9 green.

### The intended runtime flow (the blend)
1. User turn → hub.
2. If 2080 Ti cold → `triage_mode_context` sent to **Deep Thought on KENDER** (4090) for immediate 3-part Composite HyDE synthesis ([Task 12.2], BKM-018 §8). If warm → **local Lab (Triage)** runs the same prompt.
3. Either way: one LLM pass emits `inferred_intent`, `vibe`, `domain`, **`hyde_vector_text`** — QPR and HyDE fused in one step (user's design, per FEAT-436).
4. Hub retrieves RAG via `get_context(query=turn, hyde_vector_text=...)` → ChromaDB searches the refined vector → results injected as `[RAG_CONTEXT]` for Pinky/Brain.
5. If the HyDE vector's top distance > 0.45, `get_context` re-queries with the raw user query.

## TBD / not yet proven
- **Live verification of the wiring.** `_fetch_rag_context` has never been exercised against the real archive with a noisy query. The escape is *closed on paper*; not *proven closed at runtime*.
- **Full suite.** 4 pre-existing collection errors (`AcmeLab` import in `test_attendant_sprint20`, `test_hub_persistence`, `test_induction_mutex`, `test_lab_sprint20`) block a clean full run. Predates this sprint.
- **Commit status.** Now committed by user as `88314d5` on `sprint-44-blend` (HomeLabAI) — but the live regression was never run post-refactor.
- **`test_qpr_hyde.py` runner block** — passes functionally; worth a pyright pass.

## Crux areas — hard to pin down
1. **Where does "refinement" actually live?** Docs say QPR is "pre-retrieval ... in cognitive_hub.py prior to ChromaDB vector search", but the architecture makes it *part of the triage LLM prompt* (via `hyde_vector_text`). FEAT-442 text and FEAT-436 design are in tension. Resolution (AI-driven, fused) follows user design + FEAT-436, but the FeatureTracker entry should be updated or the next agent re-discovers the confusion.
2. **The 0.45/0.70 threshold equivalence.** FEAT-442 says fallback if similarity < 0.70; code uses distance > 0.45. 0.45 distance ≈ 0.55 cosine similarity — not the same point. **Either the threshold or the docs is wrong; nobody has calibrated it empirically.**
3. **The delegation trust boundary (BKM-034 vs reality).** Mandate says delegate; the delegate hallucinates file contents. The pivot (orchestrator applies) is a workaround, not a fix. Open governance problem.
4. **Cold/warm determinism.** HyDE synthesis location depends on live VRAM state — by design, but makes live testing non-deterministic. Needs a forced-cold harness.
5. **`_search_query` vestige.** In `archive_node.py` the fallback keys on `vector_query != query`, but the first pass routes through a `_search_query` alias now always equal to `vector_query`. Harmless leftover scaffolding from the regex era.

---

## Bottom line
- **FEAT-443 (PAR-Eval)** and **FEAT-444 (Backpressure)**: simple, correct, keep-worthy.
- **FEAT-442 (QPR)**: the entire drama — implemented wrong once, re-architected correctly in principle, but *unverified live, threshold uncalibrated*.
- The sprint stopped at exactly the point where remaining risk shifted from "is the design right?" to "does the wiring actually work at runtime?" — that question is still open.

---

## BKM-Protocol Dense Summary
- **One-Liner:** 443/444 are keepers; 442 is right-in-principle but unverified-live with an uncalibrated threshold.
- **Core Logic:** Keep the simple (backpressure writer, refusal schema, 5x5 interceptor, badge renderer); treat QPR wiring as TBD until a live noisy-query regression passes.
- **Trigger:** Live retrieval degrading to 0 candidates + design conversation.
- **Scars:** (1) 0.45 vs 0.70 never calibrated, (2) `_search_query` leftover, (3) delegation untrustworthy, (4) cold/warm non-determinism untested.
