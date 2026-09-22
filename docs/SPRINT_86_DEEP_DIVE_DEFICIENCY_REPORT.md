# Sprint 86 — Deep-Dive Deficiency Report
**Generated:** 2026-09-21  
**Method:** Direct source file audit + git log cross-reference  
**Scope:** Code vs. Sprint 86 claims, DNA docs, and user intent

---

## ⚠️ Findings Summary

| # | Area | Severity | Status Claim | Reality |
|---|------|----------|--------------|---------|
| 1 | `nightly_forge.py` step order | 🔴 High | "Aligned" | Training still fires before ingestion |
| 2 | `nightly_lora_training.py` never called by forge | 🔴 High | Not addressed | `nightly_forge.py` calls `train_expert.py` directly, multi-adapter pipeline is dead |
| 3 | `scan_curator.py` / `evaluate_gem_quality()` disconnected | 🔴 High | Not addressed | Only referenced in tests. Zero quality gate on mutations. |
| 4 | `ensure_datasets()` stale lockout — NOT fixed | 🔴 High | "Resolved" | File-exists check at line 382 still skips full regeneration |
| 5 | FEAT domain absent from LoRA training | 🔴 High | "Resolved" | `FEATURES_MD` constant defined but never used in `build_dna_polymorphic_dataset()` |
| 6 | Mutation cleanup missing after certification | 🟠 Medium | "Resolved" | `mutations[]` array never cleared or marked CERTIFIED after `certify_mutation` |
| 7 | `promote_draft_to_db` doesn't rebuild HTML | 🟠 Medium | "Resolved" | No `wisdom_build.py` or `philosophy_build.py` call after promotion |
| 8 | ID collision in non-WIS/PHL domains | 🟠 Medium | Not addressed | `max(nums, default=len(existing_col)) + 1` can produce BKM-001/FEAT-001 collisions |
| 9 | RDNA cards silently written to `wisdom_data.json` | 🟠 Medium | Not addressed | `handle_wisdom_save_card` has no RDNA branch; RDNA falls through to wisdom |
| 10 | Bulk save diverges from `dna_manifest.json` | 🟠 Medium | Not addressed | `handle_wisdom_save` never updates `dna_manifest.json` |
| 11 | `certifyMutation()` — DOM stays stale | 🟡 Low | "Resolved" | After certification `alert()` fires but pill stays as `mut-pill`; no DOM update |
| 12 | `dna_forge_build.py` reads from `dna_manifest.json`, not `dna/` | 🟡 Low | Not addressed | Two sources of truth remain. Build reads stale manifest. |
| 13 | `window.__CITATION_INDEX__` is static, no revisions/mutations | 🟡 Low | "Resolved" | Baked at build time, contains no `revisions[]` or `mutations[]` |
| 14 | Voice Vector Switcher (Tab 2) disconnected from DNA | 🟡 Low | Claimed out of scope | Operates on `node.variants[]` only, never touches DNA card revisions |
| 15 | WIS schema missing `mutations[]` / `revisions[]` on 481 existing cards | 🟡 Low | Not addressed | No backfill migration; mutation/revision UI invisible on all legacy cards |
| 16 | `dna/` directory now unintentionally tracked in git | 🟡 Low | Not addressed | `Portfolio_Dev/.gitignore` ignores `Portfolio_Dev/` at root — double-negative oddity |
| 17 | `sync_chroma_dna.py` has no `--force` or dry-run mode | 🟡 Low | Not addressed | Full clear-and-reupload every run; destructive if mid-run failure |
| 18 | Redundant `os.makedirs` call in `router.py` | 🔵 Info | Not addressed | Line 881 redundant, harmless but dead code |

---

## 🔴 Critical: Nightly Pipeline Is Still Broken

### Finding 1 — `nightly_forge.py` executes training BEFORE ingestion (not fixed)

**File:** [`nightly_forge.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/infra/nightly_forge.py)

The sprint claimed the execution order was "aligned." The actual code at lines 439–540 shows:

```
Step 2/4 → VRAM Quiesce (line 467)
Step 2/4-FORGE → run_unsloth_forge() — LoRA TRAINING (line 491)  ← runs FIRST
Step 3/4 → re_ignite_vllm() (line 503)
Step 4/4 → run_mass_scan() (line 517)         ← ingestion runs AFTER
Step 4/4b → run_journal_to_dna_bridge() (line 521)
Step 8b → run_wisdom_refine() (line 530)
```

Training fires at step 4 (line 491), ingestion fires at step 7 (line 517). **Nothing changed.** New BKMs, WIS cards, and philosophy notes from the current session are absent from tonight's training data. They will only appear the cycle after next.

---

### Finding 2 — `nightly_lora_training.py` multi-adapter pipeline is never activated

**File:** [`nightly_forge.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/infra/nightly_forge.py) line 491 calls `run_unsloth_forge()`.

`grep` across all of `nightly_forge.py` finds **zero references** to `nightly_lora_training`. The function `run_unsloth_forge()` calls `train_expert.py` directly — the old single-adapter approach. The discrete multi-LoRA pipeline (`cli_voice_v1`, `lab_history_v1`, `triage_v1`, `reviewer_v1`) implemented in Story 83.7 inside `nightly_lora_training.py` is **never invoked by any production code path**. It is a standalone script that must be run manually.

**Intent (Story 83.7):** Replace the single-adapter nightly pass with four domain-specialized adapters.  
**Reality:** Systemd still fires the old single-adapter pipeline every night.

---

### Finding 3 — `scan_curator.py` / `evaluate_gem_quality()` completely disconnected

`grep -rn "scan_curator" HomeLabAI/src/` returns hits **only** inside training data JSONL files (historical prompts baked into `gemini_prompts_manifest.jsonl` and `refined_prompts.jsonl`). It is never imported or called from any live production module.

The `evaluate_gem_quality()` battery — designed to gate which observations elevate to Rank 4+ DNA cards — is permanently orphaned. Every discovery that passes through the nightly sweep bypasses quality scoring entirely and can be promoted directly to a DNA card without epistemic validation.

---

### Finding 4 — `ensure_datasets()` stale lockout still present

**File:** [`nightly_lora_training.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/infra/nightly_lora_training.py) lines 379–392:

```python
def ensure_datasets() -> None:
    """Auto-build the dataset foundation if the fallback master curriculum is missing."""
    fallback = EXPERTISE_DIR / FALLBACK_DATASET
    if fallback.exists() and fallback.stat().st_size > 0:  # ← STALE LOCKOUT
        return
    ...
```

If `master_forge_curriculum.jsonl` exists on disk (which it does, since Sprint 86 generated it), `ensure_datasets()` returns immediately and never regenerates it. The sprint added 25% new DNA content to the curriculum — but any machine that ran once will never pick up the new composition. The file must be manually deleted before the new curriculum takes effect.

There is a `--force` flag on the CLI argument parser (line 555) for the `check_and_acquire_lock()` function — but `--force` controls the **12-hour debounce**, not dataset regeneration. There is no force flag for `ensure_datasets()`.

---

### Finding 5 — FEAT domain absent from `build_dna_polymorphic_dataset()`

**File:** [`build_lora_datasets.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/forge/build_lora_datasets.py)

- Line 28: `FEATURES_MD = DEV_LAB / "Portfolio_Dev" / "FeatureTracker.md"` — **defined**
- Lines 104–211: `build_dna_polymorphic_dataset()` ingests: PHL (line 117), WIS (line 144), RDNA (line 163), BKM (line 186)
- **FEAT is not present anywhere in the function body.** `FEATURES_MD` is defined and then never referenced.

The docstring at line 107 explicitly lists `FEAT (Feature DNA) → [FEAT-xxx]` as a target domain. The code never reads `FeatureTracker.md`. 430+ FEAT entries produce zero training pairs.

Additionally, the RDNA output only teaches routing (`"This inquiry is governed by [target_id]..."`) — not the underlying synthesis content. The model learns the lookup indirection but not the answer substance.

---

## 🔴 CRITICAL (NEW): `dna_manifest.json` Only Contains 30 of 481 WIS Cards

**DNA Forge is showing 6% of the wisdom database. This was not in the sprint report.**

`dna_manifest.json` (what `dna_forge_build.py` renders from) contains:
- `wisdom`: **30 cards**
- `feature`: 430, `behavioral`: 50, `sprint`: 58, `philosophy`: 33

`Portfolio_Dev/dna/wisdom_data.json` (the Sprint 86 "source of truth") contains **481 WIS cards**.

451 wisdom cards — including all 30 cards ingested from `stories.html` in Story 83.9, and every card harvested since — are silently invisible in the DNA Forge UI. They exist in `wisdom_data.json` and ChromaDB, but the build pipeline never renders them because `dna_forge_build.py` reads only from `dna_manifest.json`.

Compounding this: **6 active code paths still write to `dna_manifest.json`** (`router.py` via 3 endpoints, `draft_decomposer.py`, `sync_sprint_dna.py`, `wisdom_build.py`, `decompose_resume.py`, `compile_manuscript_2.py`). It is not a stale artifact — it is an actively diverging live file. The two sources of truth are drifting further apart every session.

---

## 🟠 Medium: Backend Persistence Gaps (Confirmed by Direct Code Read)

### Finding 6 — `mutations[]` not cleaned up after certification

**File:** [`router.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/v5/foyer/router.py) lines 1914–1929

The `handle_dna_certify_mutation` handler appends a new entry to `synthesis["revisions"]` and updates `synthesis["narrative_context"]`. Neither block touches `synthesis["mutations"]`. The certified mutation stays in the `mutations[]` array indefinitely, re-appearing as a pending uncertified proposal on every subsequent page load.

**Expected behavior:** After certification, the mutation should either be removed from `mutations[]` or marked with `"status": "CERTIFIED"` to suppress it from the candidate UI.

---

### Finding 7 — `promote_draft_to_db` doesn't trigger static HTML rebuild

**File:** [`draft_decomposer.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/curator/draft_decomposer.py) lines 337–379

The function writes JSON to `Portfolio_Dev/dna/` and returns `{"status": "success", ...}`. No `wisdom_build.py` or `philosophy_build.py` subprocess call is present. Newly promoted cards are invisible in `wisdom.html`/`dna_forge.html` until someone manually runs the build script.

Contrast: `handle_wisdom_save` (bulk save, lines 775–783) **does** trigger `wisdom_build.py`. The draft promotion path doesn't get the same treatment.

---

### Finding 8 — ID collision in non-WIS/PHL domains

**File:** [`draft_decomposer.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/curator/draft_decomposer.py) lines 254–257:

```python
else:
    existing_col = manifest.get(col_key, [])
    nums = [int(re.search(r'\d+', card.get("id", "0")).group()) for card in existing_col ...]
    next_num = max(nums, default=len(existing_col)) + 1
```

If `manifest` has no entries for BKM, FEAT, SPRINT, etc. — or has gaps — `nums` is empty and `default=len(existing_col)` is `0`, yielding `next_num = 1`. Promoting a draft BKM card creates `BKM-001`, which already exists and is a foundational protocol. The fix (reading the highest ID from the domain source file) was only applied to WIS and PHL in Sprint 86.

---

### Finding 9 — RDNA saves routed to `wisdom_data.json`

**File:** [`router.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/v5/foyer/router.py) lines 809–817

```python
is_timeline = collection in ("timeline", "discovery", "timeline_dna", "disc") or str(card_id).startswith("DISC-")
if is_timeline:
    target_file = os.path.join(dna_dir, "timeline_data.json")
elif collection in ("philosophy", "philosophy_dna"):
    target_file = os.path.join(dna_dir, "philosophy_data.json")
elif collection in ("writer", "paper", "writer_dna"):
    target_file = os.path.join(dna_dir, "wisdom_data.json")
else:
    target_file = os.path.join(dna_dir, "wisdom_data.json")  ← RDNA falls here
```

There is no `elif collection in ("rdna", "rdna_questions")` branch. Any save of an RDNA card silently writes into `wisdom_data.json` and upserts into the `wisdom_dna` ChromaDB collection. The `rdna_questions.json` file in `Portfolio_Dev/dna/` is never updated via the REST API.

---

### Finding 10 — Bulk save never updates `dna_manifest.json`

`handle_wisdom_save` (lines 745–794) writes the full card array to disk and calls `wisdom_build.py`, but never touches `dna_manifest.json`. Only `handle_wisdom_save_card` (lines 885–902) mirrors changes into `dna_manifest.json`. A full-collection overwrite via `POST /wisdom/save` can silently diverge the manifest from the source files. `dna_forge_build.py` reads from `dna_manifest.json`, so this divergence produces stale UI on next build.

---

## 🟡 Low: Frontend Gaps

### Finding 11 — `certifyMutation()` DOM stays stale

**File:** [`dna_forge_build.py`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/dna_forge_build.py) lines 2077–2092

After a successful `POST /dna/certify_mutation`, the handler does:
```javascript
.then(function(){
    alert('✓ Certified mutation "' + lens + '" ...');
})
```

No DOM manipulation follows. The `mut-pill` span is not removed, replaced, or reclassed to `rev-pill`. The operator sees the success alert, dismisses it, and the card looks identical to before — mutation still shows as uncertified until the next full `dna_forge_build.py` execution.

---

### Finding 12 — `dna_forge_build.py` still reads from `dna_manifest.json`

**File:** [`dna_forge_build.py`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/dna_forge_build.py) line 21:
```python
MANIFEST_PATH = DATA_DIR / "dna_manifest.json"
```
Line 60–62: reads from `MANIFEST_PATH`. The build reads from `field_notes/data/dna_manifest.json` (858KB, 17,751 lines, last modified Sep 20), not from `Portfolio_Dev/dna/wisdom_data.json`. These are two separate files. Single-card saves via `/wisdom/save_card` mirror to both, but bulk saves and direct file edits only update `Portfolio_Dev/dna/`. The next `dna_forge_build.py` run re-renders from potentially stale manifest data.

---

### Finding 13 — `window.__CITATION_INDEX__` is static, contains no revisions or mutations

**File:** [`writer.html`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/writer.html) line 1849

`window.__CITATION_INDEX__` is baked at build time by `build_writer.py`. The Citation Inspector can now save back to the DB (via `fetch('/wisdom/save_card')`, line 16738) but **cannot display available revisions for a card** because the static index contains only top-level card metadata — no `revisions[]` or `mutations[]` fields. The "select a revision → apply to writing" flow is incomplete at the display end.

---

### Finding 14 — Voice Vector Switcher (Tab 2) never touches DNA

**File:** [`writer.html`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/writer.html) lines 15815+, 17596–18683

The voice drawer operates entirely on `node.variants[targetKey]` — AST strings from the manuscript. Lines 18677–18683 switch voice variants from the parsed document AST. There is no code that fetches DNA card revisions, calls any DNA endpoint, or allows saving back to a card. Tab 2 was not touched in Sprint 86. The user's explicit intent was bidirectional wordsmithing "in both tabs."

---

### Finding 15 — 481 legacy WIS cards have no `mutations[]` or `revisions[]`

All three sampled cards (WIS-001, WIS-101, WIS-251) have `synthesis` keys:
```
['title', 'narrative_context', 'lab_anchors', 'review_notes', 'last_refined_by', 'refinement_version']
```
No `mutations` or `revisions` field. The `dna_forge_build.py` renderer only generates pills when `revisions` or `mutations` lists are non-empty (line 219). **The mutation/revision UX is completely invisible on all 481 legacy cards.** No backfill migration was planned or run.

---

## 🔵 Informational

### Finding 16 — Git tracking intent for `dna/` directory is ambiguous

`Portfolio_Dev/.gitignore` contains `Portfolio_Dev/` as an entry — which from the root repo perspective would ignore the entire submodule path. The `dna/` directory inside the submodule is not explicitly in `.gitignore`. The 663KB `wisdom_data.json` and 858KB `dna_manifest.json` are now silently tracked, which may or may not be the intent. No explicit decision was documented.

### Finding 17 — `sync_chroma_dna.py` has no idempotency guard

Located at `Portfolio_Dev/sync_chroma_dna.py` (20KB). Each run performs a full clear-and-reupload of all collections. No checksum or `--dry-run` flag exists. If the process dies between the clear and the reupload, ChromaDB is left empty until the next successful run.

### Finding 18 — Redundant `makedirs` call

`router.py` line 808: `os.makedirs(dna_dir, exist_ok=True)`. Line 881: `os.makedirs(os.path.dirname(target_file), exist_ok=True)`. Since `target_file` is always inside `dna_dir`, line 881 is a no-op. Harmless but dead code.

---

## Cross-Cutting: What Was Actually Left Incomplete

The sprint self-reported all 8 flows as **"RESOLVED & VERIFIED"**. Based on direct source reading:

| Flow | Sprint Claim | Actual State |
|------|-------------|--------------|
| Flow 1: Nightly Mutation Ingestion | Resolved | Step order inversion NOT fixed; nightly_lora_training.py NOT wired |
| Flow 2: UI Mutation Candidates | Resolved | Pills render but certify leaves DOM stale; no nightly candidate generation |
| Flow 3: Mutation Certification | Resolved | `mutations[]` cleanup missing; promote_draft doesn't rebuild HTML |
| Flow 4: Atomic Persistence | Resolved | RDNA silently written to wisdom; bulk save diverges from manifest |
| Flow 5: Cold-Start Kickstart | Resolved | Hook wired correctly — this one holds |
| Flow 6: Revision History UX | Resolved | Data attributes added; version numbers still not shown |
| Flow 7: Bidirectional Wordsmithing | Resolved | Tab 1 (Citation Inspector) save wired; Tab 2 (Voice Switcher) not touched |
| Flow 8: LoRA DNA Training | Resolved | FEAT domain absent; ensure_datasets lockout not fixed; RDNA output is stub-only |
