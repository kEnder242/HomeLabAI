# Retrospective Delegation Audit & Deviation Ledger: Sprints 60-63
# Augmented with Session 7581d5b2 Context & Code Anchors

**Original Audit Date:** August 26, 2026
**Augmented:** August 26, 2026 (Session 7581d5b2)
**Original Auditor:** Sisyphus (Sprint 64.5 -- FEAT-477)
**Augmented By:** AGY Orchestrator with forensic subagent corroboration
**Scope:** All code, tests, and configuration produced by subagent delegation during Sprints 60-63.
**Constraint:** Review & report only. No source code modifications.

---

## Executive Summary

This forensic audit compares the **stated architectural intent** of each sprint
plan against the **literal subagent code implementations** across HomeLabAI,
Portfolio_Dev, and config directories. The audit was originally produced by a
delegated OpenAgent (Story 64.5, FEAT-477). This augmented version enriches each
finding with:

1. **Session Context** -- the user's verbatim directives and live-testing observations
   that motivated the sprint, cross-referenced against what was actually delivered.
2. **Code Anchors** -- exact file paths, line numbers, and function signatures so an
   agent with only a narrow window around a single finding can locate and fix the issue.
3. **Corrected Findings** -- the original audit contained factual errors (notably Finding
   #13 on satellite wiring). These are corrected here with evidence.
4. **New Findings** -- discovered through forensic code review of the areas mentioned in
   the original audit.

### Severity Summary (Revised)

| Severity | Count | Category |
|:---------|:------|:---------|
| **HIGH** | 4 | Schema forcing, CriticResult schema mismatch, telemetry leakage, tautological tests |
| **MEDIUM** | 5 | Scope creep, enum drift, domain enum mismatch, diagnostic regex interception, dual-schema divergence |
| **LOW** | 3 | Stale debug schemas, comment ordering, minor naming |
| **RESOLVED** | 5 | WYWO grounding, CASUAL fast-path, lab DNA router, override parser, route incubator |
| **CORRECTED** | 1 | Satellite wiring (originally MEDIUM, now RESOLVED) |

### What Changed From Original Audit

| # | Original Severity | Revised Severity | Reason |
|---|:---:|:---:|:---|
| 1 | HIGH | HIGH | Confirmed. Dual-schema discovery adds depth (new Finding #1A). |
| 2 | MEDIUM | HIGH (escalated, split into #2, #2A, #2B) | CriticResult attribute crash discovered; telemetry leakage confirmed. |
| 3 | MEDIUM | MEDIUM | Confirmed with 142-line dead code count. |
| 4 | HIGH | HIGH | Confirmed. |
| 12 | MEDIUM | MEDIUM (expanded to #12A) | SUPERVISORY missing from schema enums. Domain mismatch discovered. |
| 13 | MEDIUM | **CORRECTED to RESOLVED** | All 3 satellites ARE wired. Original audit was wrong. |
| 15 | UNVERIFIED | **RESOLVED** | 10/10 genuine anchors verified, 100% LLM-mediated path coverage. |
| NEW #16 | -- | MEDIUM | Diagnostic regex interception of chat delivery. |
| NEW #17 | -- | LOW | Stale debug test schemas (3 files). |

---

## Session Context: The User's 5 Live Bugs

The sprint was motivated by 5 bugs the user identified during live interactive
testing of the Acme Lab WebSocket Intercom. These are the authoritative
source-of-truth for evaluating whether delegation delivered the correct fixes:

1. **Triage Delay (50s)**: User stated: *"we don't hibernate anymore, remember?
   But maybe ollama needs to."* Root cause was Remote Ollama cold-loading Qwen
   into GPU memory after idle `keep_alive` timeout on 192.168.1.26. NOT a
   hibernation issue. Sprint 64.1 addressed this with the Speculative Triage
   Relay (head-start window bypasses cold-load).

2. **Triage Text Routing**: Triage pre-reflection text was appearing in the
   crosstalk bar (bottom yellow strip) instead of Brain's Insight console (right
   panel). User directive: *"triage race: the winner gets the route: if pinky
   wins the triage is printed as pinky. if kender wins the triage goes to brain.
   this lets us know who wins."* Sprint 64.1 addressed with winner-based console
   metadata routing.

3. **Greeting Misclassification**: *"how are things?"* was NOT being classified
   as a casual greeting, triggering unnecessary LLM triage and RAG retrieval.
   Sprint 64.2 addressed with `_GREETING_RE` fast-path and `_GREETING_SHORT_CIRCUIT`.

4. **Forced HyDE Vectors**: User stated: *"we should never force hyde. If hyde
   matches are low we get nothing."* The `_TRIAGE_SCHEMA` `required` array was
   forcing the LLM to always emit a non-empty `hyde_vector_text`, causing
   spurious ChromaDB lookups. Sprint 64.3 addressed in the hub's schema copy.

5. **Unexpected RAG Eval Popup**: The RAG evaluation panel was appearing for
   queries that should not have triggered retrieval. Related to Bug #4 (forced
   HyDE vectors causing retrieval when none was warranted).

---

## Finding #1: HyDE Force-Flag in `_TRIAGE_SCHEMA.required`

**Severity:** HIGH
**Sprint:** 61.1 (FEAT-475)
**Status:** PARTIALLY FIXED in Sprint 64.3

### Session Context

User verbatim: *"we should never force hyde. If hyde matches are low we get nothing."*
This was the #4 live bug. The Zero-Context architecture requires that CASUAL,
SUPERVISORY, and META queries emit `hyde_vector_text: ""` and skip vector search.
When the schema forces the LLM to produce a non-empty value, it structurally
undermines the entire Zero-Context gate.

### The Bug (Dual-Schema Problem)

There are **two separate copies** of the triage schema in the codebase. Sprint
64.3 fixed one but not the other:

**FIXED -- CognitiveHub's inline schema:**
- File: [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L853-L877)
- Line 874: `"required": ["inferred_intent", "addressed_to", "vibe", "domain", "casual", "intrigue", "importance"]`
- This is the schema passed to `SpeculativeTriageRelay.relay()` and dispatched
  to Kender/vLLM via `_dispatch_kender_triage()` (L270-277) and
  `_dispatch_vllm_triage()` (L279-286).
- `hyde_vector_text` is NOT in `required`. Correctly fixed.

**NOT FIXED -- TriageEngine's module-level schema:**
- File: [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L307-L354)
- Line 342-351: `"required": ["inferred_intent", ..., "hyde_vector_text"]`
- `hyde_vector_text` IS STILL in `required`.

### Production Impact Assessment

The `TriageEngine.evaluate_triage()` method (line 516-591) is NOT called in the
hub's production relay path. The hub uses its own inline schema passed through
`SpeculativeTriageRelay`. However, `TriageEngine` IS:
- Used in all unit tests (`test_triage_engine.py`: 27+ test cases instantiate
  `TriageEngine()`)
- Potentially used by future callers expecting a standalone triage interface
- A maintenance trap: any developer reading `_TRIAGE_SCHEMA` will assume
  `hyde_vector_text` is still mandatory

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| UNFIXED schema | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L342-L351) | L342-351 |
| FIXED schema | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L874) | L874 |
| Hub relay dispatch | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L895-L900) | L895-900 |
| `scrub_hyde_vector()` definition | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L161-L184) | L161-184 |
| Hub's post-triage scrub call | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L916-L917) | L916-917 |
| `resolve_hyde_vector()` 3-tier cascade | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1449-L1478) | L1449-1478 |
| `_fetch_rag_context()` hyde guard | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1486-L1489) | L1486-1489 |

### Remediation

1. Remove `"hyde_vector_text"` from `_TRIAGE_SCHEMA.required` in `triage_engine.py` L350.
2. Reconcile: only ONE canonical schema definition should exist. The hub's
   inline copy and the engine's module constant should be unified or one should
   import from the other.

---

## Finding #1A: Dual-Schema Divergence (NEW)

**Severity:** MEDIUM
**Sprint:** 61-64 (accumulated drift)

### Observation

The two schema copies have diverged in **three dimensions**:

| Property | `triage_engine.py` L307-354 | `cognitive_hub.py` L853-877 |
|:---------|:---|:---|
| `hyde_vector_text` in `required` | YES (L350) | NO (L874) |
| `domain` enum | 5 values: `exp_tlm, exp_bkm, exp_for, standard, lab_history` (L335) | 6 values: adds `lab_internal` (L863) |
| Additional properties | None | `situation` (L867), `hints` (L868) |

The `lab_internal` domain omission in `triage_engine.py` is particularly problematic
because `_META_DOMAIN_OVERRIDES` (triage_engine.py L246) assigns `domain: "lab_internal"`
for META queries, yet the schema enum at L335 does not include `lab_internal`,
meaning guided JSON decoding on vLLM would reject it if the engine's schema
were used for structured output.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| Engine schema domain enum (5 values) | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L333-L336) | L333-336 |
| Hub schema domain enum (6 values) | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L863) | L863 |
| META domain override assigns `lab_internal` | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L246) | L246 |

### Remediation

Unify into a single `_TRIAGE_SCHEMA` constant imported by both modules. The hub's
version is authoritative (it includes `lab_internal`, `situation`, `hints`, and
has `hyde_vector_text` correctly removed from required).

---

## Finding #2: Crosstalk vs Chat Routing -- CriticResult Attribute Crash (ESCALATED)

**Severity:** HIGH (escalated from MEDIUM)
**Sprint:** 61.3 (FEAT-470)

### Session Context

User live-tested and observed triage text appearing in the crosstalk bar instead
of the chat console. The sprint plan specified: *"Replace robotic 'well-crafted
response' praise with satirical Pinky cartoon quip + 1-sentence technical summary.
Route critic output to `chat` channel, NOT `crosstalk`."*

### The Bug

Forensic review reveals the crosstalk routing issue is actually **pre-empted by
a more severe bug**: the `evaluate_grounding` method crashes at runtime due to
an attribute schema mismatch between what it expects and what `CriticResult`
provides.

**What `evaluate_grounding` accesses** (cognitive_hub.py L1282-1318):
- `critic_res.score` -- AttributeError
- `critic_res.reasoning` -- AttributeError
- `critic_res.slop_found` -- AttributeError
- `critic_res.retort` -- AttributeError

**What `CriticResult` actually provides** (pinky_critic_persona.py):
- `critic_res.cartoon_retort`
- `critic_res.critique_suggestions`
- `critic_res.raw`

At runtime, `critic_res.score` raises `AttributeError`, which is caught by the
generic exception handler at L1322 (`[HUB] Coherence critique failed:`),
**silently suppressing all downstream broadcasts** -- both the telemetry frame
AND the user-facing chat delivery.

### Secondary Issue: Telemetry Leakage

Even if the CriticResult crash were fixed, the telemetry broadcast at L1307-1312
has a routing flaw. It broadcasts with:
- `type: "crosstalk"`
- `brain_source: "Pinky (Coherence Critic)"`
- `brain: "[CRITIC TELEMETRY] Score: .../5 | Slop: ..."`

In `intercom_v2.js`, the crosstalk handler (L570-608) checks if `brain_source`
contains `"Pinky"`. If true and `brain` is non-JSON, it calls `appendMsg()` which
renders the raw telemetry string **in the main chat console** alongside the
user-facing critique. Internal diagnostics leak into the user-visible chat.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| `evaluate_grounding` method | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1199-L1324) | L1199-1324 |
| CriticResult attribute access crash | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1282-L1290) | L1282-1290 |
| `CriticResult` dataclass definition | [`pinky_critic_persona.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_critic_persona.py) | Check dataclass fields |
| `format_chat_delivery()` | [`pinky_critic_persona.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_critic_persona.py#L230-L286) | L230-286 |
| `format_crosstalk_telemetry()` | [`pinky_critic_persona.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_critic_persona.py#L291-L336) | L291-336 |
| Telemetry broadcast (leaks to chat) | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1307-L1312) | L1307-1312 |
| Chat delivery via `execute_dispatch` | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1315-L1321) | L1315-1321 |
| `execute_dispatch` broadcasts as `type: "chat"` | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L681-L689) | L681-689 |
| Crosstalk handler persona leak path | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L570-L608) | L570-608 |

### Remediation

1. **Fix CriticResult attribute mapping**: Align `evaluate_grounding` to use
   `critic_res.cartoon_retort`, `critic_res.critique_suggestions`, etc., OR
   extend `CriticResult` dataclass to include `score`, `reasoning`, `slop_found`,
   `retort` fields.
2. **Fix telemetry leakage**: Either (a) change `brain_source` to a non-persona
   name like `"System (Critic Telemetry)"`, or (b) add a `isPersona` exclusion
   in intercom_v2.js for messages with `type: "crosstalk"`.

---

## Finding #2B: Diagnostic Regex Interception of Chat Delivery (NEW)

**Severity:** MEDIUM
**Sprint:** Cross-cutting (FEAT-453)

### Observation

In `intercom_v2.js`, when a message arrives with `type: "chat"` and has a `brain`
field, line 671 tests against `DIAGNOSTIC_PREFIX_RE`:
```javascript
/^\[(SYSTEM|HEARTBEAT|REMOTE|FOYER|INIT|LOCK|GOVERNOR|LAB|STAGE|PAGER)\]/i
```

If Pinky's user-facing response begins with any of these reserved tags (e.g.,
`[SYSTEM]`, `[LAB]`, `[STAGE]`), the entire response is silently redirected to
the crosstalk bar via `routeDiagnosticToCrosstalk()` and never appears in the
chat console.

This is a latent bug that activates whenever LLM-generated text happens to start
with a bracketed system keyword.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| `DIAGNOSTIC_PREFIX_RE` definition | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L292) | L292 |
| Chat-type diagnostic interception | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L669-L674) | L669-674 |
| `routeDiagnosticToCrosstalk()` | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js) | Search for function def |

### Remediation

Only apply `DIAGNOSTIC_PREFIX_RE` to messages with `type: "crosstalk"`, or add a
`source` allowlist that skips the regex for persona sources.

---

## Finding #3: Traversal Mode Scope Creep (4 Dead Modes)

**Severity:** MEDIUM
**Sprint:** 62.3 (FEAT-117/467)

### Session Context

Sprint 62.3 specified exactly 3 traversal modes: `TOPIC_FIRST`, `TIME_FIRST`,
`STREAM_REPLAY`. The delegated subagent delivered 7.

### The Bug

`TraversalMode` enum has 7 members. The 4 extra modes are:
- `DREAM_CACHE` -- functionally identical to `STREAM_REPLAY` (same collection
  `short_term_stream`, differs only in `session_limit` default: 5 vs 10)
- `COMPOSITE_HYDE` -- unreachable from any policy vibe
- `TEMPORAL_FILTER` -- unreachable from any policy vibe
- `COMPONENT_LOOKUP` -- unreachable from any policy vibe (includes unused helper
  functions `extract_component_ids`, `is_component_query`)

All 4 are additionally **blocked at the validation layer**: both
`triage_policy_loader.py` L25 and `route_incubator.py` L26 hardcode
`_TRAVERSAL_MODES: frozenset[str] = frozenset({"TOPIC_FIRST", "TIME_FIRST", "STREAM_REPLAY"})`.
Any attempt to configure these modes via policy or candidate routes raises
`TriagePolicyError` / `ValueError`.

### Dead Code Count

| Mode | Lines in `traversal_dispatcher.py` | Lines in test file |
|:-----|:--:|:--:|
| `DREAM_CACHE` | 23 | 16 |
| `COMPOSITE_HYDE` | 26 | 27 |
| `TEMPORAL_FILTER` | 40 | 17 |
| `COMPONENT_LOOKUP` | 53 | 65 |
| **Total** | **142** | **125** |

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| `TraversalMode` enum (7 members) | [`traversal_dispatcher.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/traversal_dispatcher.py#L27-L36) | L27-36 |
| `_TRAVERSAL_MODES` allowlist (blocks extras) | [`triage_policy_loader.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_policy_loader.py#L25) | L25 |
| `_TRAVERSAL_MODES` allowlist (route incubator) | [`route_incubator.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/route_incubator.py#L26) | L26 |
| `_build_dream_cache_query` (duplicate of stream_replay) | [`traversal_dispatcher.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/traversal_dispatcher.py#L248-L267) | L248-267 |
| `_build_stream_replay_query` (original) | [`traversal_dispatcher.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/traversal_dispatcher.py#L240) | L240+ |
| Policy traversal mode mapping | [`triage_policy.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/triage_policy.json) | Check each vibe's `rag.traversal` |

### Remediation

Remove the 4 unused modes from the enum and delete their builder functions.
The `_TRAVERSAL_MODES` allowlist already prevents their use.

---

## Finding #4: Tautological Test Patterns

**Severity:** HIGH
**Sprint:** 61.1 (FEAT-468)

### Session Context

User observed that 149+ passing tests gave false confidence when bugs were
found during live testing. The sprint plan stated: *"Rewrite unit tests to test
actual query strings and semantic behavior, preventing tautological pass states."*

### The Anti-Pattern

Tests in `test_triage_engine.py` follow a **construct-then-assert** pattern:
1. Create a `_MockResident` that returns pre-canned JSON
2. Call `evaluate_triage()` with a synthetic query
3. Assert the engine parses the pre-canned JSON correctly

Example (test_evaluate_triage_meta_override): constructs `{"vibe": "TECHNICAL"}`
input, then asserts `vibe == "META"`. But the query `"What is the audio_pipeline
status?"` contains `audio_pipeline` which is in `_META_KEYWORDS` (triage_engine.py
L193), so `is_meta_lexicon()` catches it before the LLM is ever invoked. The
`_MockResident` is never called. The test validates the fast-path, not the
LLM-mediated override.

### What Changed in Sprint 64.2

Story 64.2 (delegated to OpenAgent) rewrote some tests with real greeting and
WYWO queries. The greeting fast-path tests (L711-795) are genuine: they test
`"how are things?"`, `"hello"`, `"what's up?"`, `"good morning"`, `"hi"`,
`"how are you?"`, and `"[ME] hello"` (prefix-stripped). These are correctly
grounded in real user input.

However, the LLM-mediated path tests (L521-694) still use `_MockResident` with
synthetic JSON, meaning the core triage classification pipeline (the path that
handles non-trivial queries) remains untested with genuine prompts.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| `_MockResident` pattern | [`test_triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/tests/test_triage_engine.py#L547-L694) | L547-694 |
| Genuine greeting tests (Sprint 64.2) | [`test_triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/tests/test_triage_engine.py#L711-L795) | L711-795 |
| WYWO regex tests (Sprint 64.2) | [`test_triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/tests/test_triage_engine.py#L798+) | L798+ |
| Validation anchors (10 genuine queries) | [`validation_anchors.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/validation_anchors.json#L1-L83) | L1-83 |

### Remediation

Replace `_MockResident` tests with parameterized test fixtures using the 10
queries from `validation_anchors.json` (VAL-01 through VAL-10). These are
verified to bypass all fast-paths and exercise the full LLM-mediated triage
pipeline.

---

## Finding #5: WYWO Canonical Definition

**Severity:** RESOLVED
**Sprint:** 61.1 / 62.1

### Session Context

User explicitly corrected: *"WYWO means 'while you were out' how did you not
catch that?"* The Sprint 62.1 subagent had hallucinated "Wake You With Oneirics".

### Verification

- `triage_policy.json` L27: Correctly defines WYWO as *"'While You Were Out'
  Standup Briefing -- briefing the user on lab activity, engineering events, and
  subconscious dream synthesis during user absence."*
- `_WYWO_RE` regex in `triage_engine.py` L389-402: Correctly matches "what did
  you do while I was out", "give me the standup briefing", "catch me up",
  "while you were out", "wywo".

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| WYWO policy definition | [`triage_policy.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/triage_policy.json#L27) | L27 |
| `_WYWO_RE` regex | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L389-L402) | L389-402 |

---

## Finding #6: Declarative Triage Policy Loader

**Severity:** LOW (minor)
**Sprint:** 62.1 (FEAT-467)

### Observation

Clean implementation. `get_vibe_rule()` returns `None` for missing vibes rather
than raising, which could mask wiring bugs when vibes like `ANALYTICAL` are
emitted by the LLM but have no policy entry.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| `load_policy()` | [`triage_policy_loader.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_policy_loader.py) | Check module |
| `get_vibe_rule()` returns None on miss | [`triage_policy_loader.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_policy_loader.py#L130-L143) | L130-143 |

---

## Finding #7: Dynamic Route Incubation Sandbox

**Severity:** RESOLVED
**Sprint:** 62.2 (FEAT-472)

Clean implementation. Atomic persistence via `.tmp` + `os.replace()`. One live
route validates the sandbox: `MOUSE_DEF:live_thermal_check`.

---

## Finding #8: Lab DNA Router

**Severity:** RESOLVED
**Sprint:** 61.2 (FEAT-469)

Clean implementation. META/lab_internal queries suppress `career_ledger` and
`behavioral_dna`. Zero Context gate at `max_distance=0.50`.

---

## Finding #9: Override Parser Satellite

**Severity:** RESOLVED
**Sprint:** 60.1 (FEAT-145/REF-01)

Clean implementation. Uses `_GEM_BKM_RE` for ID extraction, atomic `.tmp` +
`os.replace()` persistence.

---

## Finding #10: Maintenance Sweeper Satellite

**Severity:** RESOLVED
**Sprint:** 60.2 (LAB-095/096/099/REF-02)

Clean implementation. Graceful fallback on non-Linux.

---

## Finding #11: Audio Pipeline Satellite

**Severity:** RESOLVED
**Sprint:** 60.3 (FEAT-059/LAB-088/REF-03)

Clean implementation. Zero-copy PCM conversion via `numpy.frombuffer`.

---

## Finding #12: Schema Enum Drift (Vibe Alignment)

**Severity:** MEDIUM (expanded)
**Sprint:** 61-62

### The Bug

Three-way mismatch between schema vibe enums and the declarative policy:

| Vibe | In `_TRIAGE_SCHEMA` (engine) | In hub schema | In `triage_policy.json` |
|:-----|:---:|:---:|:---:|
| TECHNICAL | Y | Y | Y |
| CASUAL | Y | Y | Y |
| HISTORICAL | Y | Y | Y |
| OPERATIONAL | Y | Y | Y |
| FORENSIC | Y | Y | Y |
| META | Y | Y | Y |
| WYWO | Y | Y | Y |
| ANALYTICAL | Y | Y | **NO** |
| DEEP_RESEARCH | Y | Y | **NO** |
| SUPERVISORY | **NO** | **NO** | Y |

**`ANALYTICAL`**: Has partial production routing. Prompt guidance in `lab_node.py`
L25-38 instructs the model to classify comparative/trade-off queries as ANALYTICAL.
Tone mapping exists in `cognitive_hub.py` L1256-1257. But no policy entry exists,
so `get_vibe_rule("ANALYTICAL")` returns `None`, causing retrieval to fall back
to null RAG without target collections or distance thresholds.

**`DEEP_RESEARCH`**: 100% dead enum value. No prompt instructions, no policy
mapping, no tone mapping, no production routing logic anywhere.

**`SUPERVISORY`**: Defined in policy with `rag: null`, `importance: 0.5`. But
NOT in either schema enum, meaning the LLM cannot emit it via guided JSON
decoding. The only way a turn gets classified as SUPERVISORY is via the
`classify_vibe_and_domain()` override function.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| Engine schema vibe enum (9 values) | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L321-L331) | L321-331 |
| Hub schema vibe enum (9 values) | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L862) | L862 |
| Policy vibes (8 keys) | [`triage_policy.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/triage_policy.json#L4-L87) | L4-87 |
| ANALYTICAL tone guidance | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L1256-L1257) | L1256-1257 |
| ANALYTICAL prompt in lab_node | [`lab_node.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/nodes/lab_node.py#L25-L38) | L25-38 |

### Remediation

Either:
- (a) Add `ANALYTICAL` and `SUPERVISORY` to both schema enums and add
  `ANALYTICAL` to `triage_policy.json`. Remove `DEEP_RESEARCH` from enums.
- (b) Remove `ANALYTICAL` from schemas and enums, relying solely on
  `classify_vibe_and_domain()` for vibe overrides.

---

## Finding #12A: Domain Enum Mismatch (NEW)

**Severity:** MEDIUM
**Sprint:** 61-64

### Observation

The `triage_policy.json` maps WYWO to domain `dream_stream` and META to domain
`lab_internal`. Neither `dream_stream` nor (in the engine's case) `lab_internal`
appears in the schema domain enums:

| Domain | Engine schema | Hub schema | Used in policy |
|:-------|:---:|:---:|:---:|
| exp_tlm | Y | Y | Y (TECHNICAL) |
| exp_bkm | Y | Y | Y (OPERATIONAL) |
| exp_for | Y | Y | Y (FORENSIC) |
| standard | Y | Y | Y (CASUAL, SUPERVISORY) |
| lab_history | Y | Y | Y (HISTORICAL) |
| lab_internal | **NO** | Y | Y (META) |
| dream_stream | **NO** | **NO** | Y (WYWO) |

The `_META_DOMAIN_OVERRIDES` in `triage_engine.py` L246 assigns
`domain: "lab_internal"`, but the engine's own schema enum at L335 does not
include `lab_internal`. This means the LLM cannot natively emit `lab_internal`
when using the engine's schema -- it only gets applied via post-hoc override.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| Engine domain enum (5 values, no lab_internal) | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L333-L336) | L333-336 |
| Hub domain enum (6 values, includes lab_internal) | [`cognitive_hub.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L863) | L863 |
| META domain override assigns lab_internal | [`triage_engine.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/triage_engine.py#L246) | L246 |
| WYWO maps to dream_stream in policy | [`triage_policy.json`](file:///home/jallred/Dev_Lab/HomeLabAI/config/triage_policy.json) | Check WYWO entry |

---

## Finding #13: Satellite Wiring Verification -- CORRECTED

**Severity:** CORRECTED (originally MEDIUM, now RESOLVED)
**Sprint:** 60.4/60.5

### Original Claim (WRONG)

The original audit stated: *"override_parser.py, maintenance_sweeper.py, and
audio_pipeline.py are standalone modules with no import evidence in
cognitive_hub.py or router.py."*

### Forensic Correction

All 3 satellites ARE actively wired into production:

**override_parser:**
- Imported in [`cognitive_hub.py` L12](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L12):
  `from logic.override_parser import is_override_query, parse_override_with_resident, save_override_to_file`
- Called in [`cognitive_hub.py` L761-778](file:///home/jallred/Dev_Lab/HomeLabAI/src/logic/cognitive_hub.py#L761-L778):
  `is_override, gem_id = is_override_query(turn)` ... `save_override_to_file(gem_id, updates)`

**maintenance_sweeper:**
- Imported in [`router.py` L34](file:///home/jallred/Dev_Lab/HomeLabAI/src/v5/foyer/router.py#L34):
  `from v5.foyer.maintenance_sweeper import MaintenanceSweeper`
- Called in [`router.py` L1441, L1491, L1501](file:///home/jallred/Dev_Lab/HomeLabAI/src/v5/foyer/router.py#L1441):
  TTL buffer pruning, CPU thermal monitoring, heap GC
- Note: module resides at `src/v5/foyer/maintenance_sweeper.py` not `src/logic/`

**audio_pipeline:**
- Imported in [`sensory_manager.py` L9](file:///home/jallred/Dev_Lab/HomeLabAI/src/equipment/sensory_manager.py#L9):
  `from equipment.audio_pipeline import AudioPipeline`
- Called in [`sensory_manager.py` L106-113](file:///home/jallred/Dev_Lab/HomeLabAI/src/equipment/sensory_manager.py#L106-L113):
  PCM conversion, signal detection, sliding window
- Called from [`router.py` L1169](file:///home/jallred/Dev_Lab/HomeLabAI/src/v5/foyer/router.py#L1169):
  `text = self.sensory.process_binary_chunk(msg.data)`
- Note: module resides at `src/equipment/audio_pipeline.py` not `src/logic/`

### Root Cause of Original Error

The original OpenAgent auditor searched for satellites at `src/logic/` paths
and did not find them because `maintenance_sweeper` lives at `src/v5/foyer/`
and `audio_pipeline` lives at `src/equipment/`. The auditor also may not have
searched for class-based imports (`from v5.foyer.maintenance_sweeper import
MaintenanceSweeper`) versus function-based imports.

---

## Finding #14: CASUAL Grounding

**Severity:** RESOLVED
**Sprint:** 62.1

Correctly implemented. `triage_policy.json` CASUAL entry: `importance: 0.1`,
`rag: null`, examples array. `_GREETING_RE` (triage_engine.py L377-385) and
`_GREETING_SHORT_CIRCUIT` (L363-372) correctly bypass LLM. `evaluate_triage()`
fast-path at L544-554: `importance: 0.1`, `hyde_vector_text: ""`.

Also verified: Hub has its own greeting short-circuit at cognitive_hub.py L836-850
using a simpler set-based lookup (`raw_lower in ["hi", "hey", "hello", ...]`).
This is a redundant but not conflicting fast-path -- the hub catches it before
the relay is even invoked.

---

## Finding #15: Validation Anchor Quality

**Severity:** RESOLVED (was UNVERIFIED)
**Sprint:** 63.1

### Verification Results

`validation_anchors.json` contains exactly 10 anchors (VAL-01 through VAL-10):
- 4 silicon validation queries (PCIe AER, MCTP/PECI, Oakstream simulation, Intel Federal PAE)
- 3 platform telemetry queries (RAPL MSR, DCGM/Prometheus, Kernel BDI writeback)
- 3 lab architecture queries (delegate.py anchors, route incubation lifecycle, Zero Context rationale)

**Fast-path overlap check:** 0/10 match `_GREETING_RE`, 0/10 match `_WYWO_RE`,
0/10 match `_META_KEYWORDS`. All 10 exercise the full LLM-mediated triage path.

All anchors are genuine, domain-specific, real-world queries with non-trivial
expected keyword sets.

---

## Finding #16: Diagnostic Regex Interception of Chat Delivery (NEW)

**Severity:** MEDIUM
**Sprint:** Cross-cutting (FEAT-453)

### Observation

In `intercom_v2.js` L669-674, when a `type: "chat"` message arrives and `data.brain`
matches `DIAGNOSTIC_PREFIX_RE` (`/^\[(SYSTEM|HEARTBEAT|REMOTE|FOYER|INIT|LOCK|GOVERNOR|LAB|STAGE|PAGER)\]/i`),
the entire message is redirected to `routeDiagnosticToCrosstalk()` and **never
rendered in the chat console**.

If Pinky's LLM-generated response starts with `[SYSTEM]`, `[LAB]`, `[STAGE]`,
or any other reserved tag, the user will see nothing in the chat console.

### Code Anchors

| What | File | Line(s) |
|:-----|:-----|:--------|
| DIAGNOSTIC_PREFIX_RE | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L292) | L292 |
| Chat diagnostic interception | [`intercom_v2.js`](file:///home/jallred/Dev_Lab/Portfolio_Dev/field_notes/intercom_v2.js#L669-L674) | L669-674 |

### Remediation

Scope `DIAGNOSTIC_PREFIX_RE` to messages with `type: "crosstalk"` only, or add
a source allowlist that skips the regex for persona sources like "Pinky" and "Brain".

---

## Finding #17: Stale Debug Test Schemas (NEW)

**Severity:** LOW
**Sprint:** Pre-Sprint 60 legacy

### Observation

Three debug test harnesses contain legacy triage schemas from before the
Sprint 61 refactoring:

| File | Schema Issues |
|:-----|:---|
| [`hub_mimic_test.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/hub_mimic_test.py#L22-L42) | Uses `intent` (not `inferred_intent`), 3 legacy vibes, 4 domains |
| [`mcp_triage_test.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/mcp_triage_test.py#L11-L31) | Same legacy schema |
| [`silo_triage_test.py`](file:///home/jallred/Dev_Lab/HomeLabAI/src/debug/silo_triage_test.py#L22-L42) | Same legacy schema |

These use vibes `["SILICON_TELEMETRY", "ARCHIVE_HISTORY", "PINKY_INTERFACE"]`
which have not existed since Sprint 61.

### Remediation

Update debug schemas to match the current production schema or delete stale
debug scripts.

---

## Mitigation Recommendations Summary (Revised)

| # | Finding | Priority | Action |
|---|---------|:--------:|:-------|
| M1 | HyDE force-flag in `_TRIAGE_SCHEMA` (engine copy) | P0 | Remove `hyde_vector_text` from `required` at `triage_engine.py` L350. |
| M1A | Dual-schema divergence | P1 | Unify into single canonical schema constant. Hub version is authoritative. |
| M2 | CriticResult attribute crash | P0 | Align `evaluate_grounding` attribute access with `CriticResult` dataclass fields. |
| M2A | Telemetry leakage to chat console | P1 | Change telemetry `brain_source` to non-persona identifier. |
| M2B | Diagnostic regex intercepts chat delivery | P1 | Scope `DIAGNOSTIC_PREFIX_RE` to `type: "crosstalk"` only. |
| M3 | Tautological test suites (LLM path) | P1 | Use `validation_anchors.json` queries for parameterized LLM-path tests. |
| M4 | Traversal mode scope creep (142 dead lines) | P2 | Remove `DREAM_CACHE`, `COMPOSITE_HYDE`, `TEMPORAL_FILTER`, `COMPONENT_LOOKUP`. |
| M5 | Schema enum drift (vibes) | P1 | Add `SUPERVISORY` to enums. Remove `DEEP_RESEARCH`. Decide on `ANALYTICAL`. |
| M5A | Schema enum drift (domains) | P1 | Add `lab_internal` to engine schema. Decide on `dream_stream`. |
| M6 | Stale debug test schemas | P3 | Update or delete `hub_mimic_test.py`, `mcp_triage_test.py`, `silo_triage_test.py`. |

---

## Architectural Health Assessment

### What Went Well (Sprints 60-63)

1. **BKM-015 Compliance**: All satellite modules use zero third-party dependencies
   beyond Python stdlib (except `audio_pipeline.py` which requires `numpy`).
2. **Atomic Persistence**: `override_parser.py` and `route_incubator.py` both use
   `.tmp` + `os.replace()` crash-safe writes.
3. **WYWO Grounding**: Canonical "While You Were Out" definition correctly restored.
4. **CASUAL Fast-Path**: Greeting regex and `_GREETING_SHORT_CIRCUIT` correctly
   bypass the LLM for colloquial pleasantries.
5. **Zero Context Gate**: `lab_dna_router.py` properly enforces distance thresholds.
6. **Satellite Wiring**: All 3 Sprint 60 satellites (override_parser,
   maintenance_sweeper, audio_pipeline) ARE wired into production, contrary to
   the original audit's claim.
7. **Validation Anchors**: 10/10 genuine, high-density, real-world queries with
   100% LLM-mediated path coverage.

### What Needs Remediation

1. **CriticResult Attribute Crash** (Finding #2): `evaluate_grounding` is
   **completely broken at runtime** due to dataclass field name mismatch. This
   silently suppresses all coherence critique output.
2. **Schema HyDE Forcing** (Finding #1): The engine copy still mandates
   `hyde_vector_text`. While not in the production relay path, it misleads tests
   and future callers.
3. **Dual-Schema Divergence** (Finding #1A): Two copies of the triage schema
   have drifted apart in required fields, domain enums, and property sets.
4. **Dead Code** (Finding #3): 142 lines of unreachable traversal mode code
   plus 125 lines of tests for unreachable code.
5. **Enum Drift** (Finding #12): Three-way mismatch between engine schema, hub
   schema, and policy definitions for both vibes and domains.
6. **Telemetry Leakage** (Finding #2): Critic diagnostics leak into user chat
   due to persona-matching in crosstalk handler.

---

## Handover Reflection (Augmented)

**What the original audit got wrong:** Finding #13 (satellite wiring) was
factually incorrect. The auditor searched for imports at `src/logic/` paths only
and missed that `maintenance_sweeper` lives at `src/v5/foyer/` and
`audio_pipeline` lives at `src/equipment/`. This underscores the importance of
using codebase-wide grep rather than path-assumption-based searches.

**What the session discussion revealed that the audit missed:**
1. The CriticResult attribute crash (Finding #2) is arguably the most severe
   bug discovered -- it completely disables the coherence critique pipeline at
   runtime. The original audit noted the dual routing paths but did not trace
   the actual attribute access patterns.
2. The dual-schema divergence (Finding #1A) was not visible from the original
   audit's single-file perspective. It required cross-referencing two files to
   discover that Sprint 64.3 fixed one schema copy but not the other.
3. The diagnostic regex interception (Finding #16) is a cross-cutting UI bug
   that no sprint explicitly addressed but can silently suppress user-facing
   LLM responses.

**The single change that would have the highest impact:** Fixing the CriticResult
dataclass mismatch (Finding #2 / M2). It is a one-line-per-attribute fix that
would re-enable the entire coherence critique pipeline.
