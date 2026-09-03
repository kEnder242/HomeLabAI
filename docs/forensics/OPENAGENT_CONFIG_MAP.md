# OpenAgent Config Map — BKM-034 Config Cartography
**Date:** 2026-08-03 | **Status:** ACTIVE | **Prev:** config purge 2026-07-27 (mistral/groq stripped)

## The One-Liner
OpenAgent = `opencode.json` (binary config: providers/MCP/permissions) + `oh-my-openagent.json` (plugin: agent roles/models/fallbacks). Providers resolve via **native models.dev registry + auth.json keys** — NOT npm blocks (native binary, 1.14.48).

## The Core Logic — Two files, three layers

```
┌─ opencode.json ──────────────┐   ┌─ oh-my-openagent.json ─────────────┐
│ plugin list (oh-my-openagent)│   │ agents:  role → model → fallbacks  │
│ permission: all-allow        │   │ categories: 8 task types → models   │
│ mcp: turbovec/claude-mem/icm │   │ agent_settings: concurrency 4       │
│ provider: google+local4090   │   │ runtime_fallback: 503/429 retry×3   │
│   (groq/cohere: registry)    │   └─────────────────────────────────────┘
└──────────────────────────────┘
Keys: ~/.local/share/opencode/auth.json  (google, groq, cohere, mistral, 4090)
```

## The Trigger
OpenAgent spawns subagents → routes by role/category → model string `provider/model` → resolved against embedded registry → key pulled from auth.json → on 503/429/401, falls through `fallback_models` chain.

## Current Swarm (Verified 2026-08-06)

| Agent | Role | Primary Model | Fallback Models |
|---|---|---|---|
| **prometheus** | strategic planner | `opencode/deepseek-v4-flash-free` | `groq/llama-3.3-70b-versatile`, `cohere/command-a-plus-05-2026` |
| **sisyphus** | lead orchestrator | `opencode/deepseek-v4-flash-free` | `groq/llama-3.3-70b-versatile` |
| **atlas** | todo orchestrator | `cohere/command-a-plus-05-2026` | `groq/llama-3.3-70b-versatile` |
| **hephaestus** | fast triage / repair | `groq/llama-3.3-70b-versatile` | `opencode/deepseek-v4-flash-free` |
| **sisyphus-junior** | ground worker (KENDER) | `my-windows-4090/qwen3:14b` | `my-windows-4090/qwen3:14b` |
| **oracle** | deep RAG architect | `opencode/deepseek-v4-flash-free` | `groq/llama-3.3-70b-versatile` |
| **momus** | pre-commit diff critic | `groq/llama-3.3-70b-versatile` | `cohere/command-a-plus-05-2026` |
| **metis** | task step refiner | `groq/llama-3.3-70b-versatile` | `cohere/command-a-plus-05-2026`, `opencode/deepseek-v4-flash-free` |
| **librarian** | doc search | `opencode/deepseek-v4-flash-free` | `groq/llama-3.3-70b-versatile` |
| **explore** | repo grep / search | `opencode/deepseek-v4-flash-free` | `groq/llama-3.3-70b-versatile` |
| **multimodal-looker** | UI vision inspector | `cohere/command-a-vision-07-2025` | `cohere/command-a-vision-07-2025` |
| **general** | local execution worker | `my-windows-4090/qwen3:14b` | `my-windows-4090/qwen3:14b` |

**Category Routing (`task()`):**
- `ultrabrain`, `deep`, `unspecified-high`: `opencode/deepseek-v4-flash-free` (prevents Groq 12k TPM rate-limits on heavy prompt contexts).
- `quick`: `groq/llama-3.3-70b-versatile` (sub-second 300 tok/s execution for small sub-agent fixes).
- `artistry`, `writing`: `cohere/command-a-plus-05-2026`.

## The Scars (why we're here — DO NOT REPEAT)

1. **2026-07-27 PURGE (5328f96/b48d943):** mistral+groq refs stripped from oh-my-openagent.json, all categories → qwen2.5-coder:14b → then qwen3:14b. Cause: KENDER write failures + 401. **Failure mode: flattening the swarm to ONE provider killed the resilience ladder — no fallback existed when the remaining provider 503'd.** Never collapse to a single provider; rotate through the ladder.
2. **Mistral key died (401) — "the model that didn't gracefully fail to backup."** Its 401 during purge was the trigger for #1. Key is auth-level-dead (not quota — quota is 429). Mistral free tier **resets monthly** (org quota email, reset ~Jul 31); the *account* revived but the *stored key* stayed 401 → needs a fresh dashboard key to re-enter the swarm.
3. **Native-binary gotcha:** opencode 1.14.48 is native (no node_modules). Do NOT add `npm:` provider blocks for groq/cohere/mistral — the embedded registry resolves them; npm blocks only add breakage risk. `opencode models` is the ground-truth resolver check.
4. **Cloudflare UA-block (not hacky):** raw urllib hits 403 error-1010; browser-like UA gets through. Real SDK/http clients send proper UAs — no hacks needed.
5. **Free-tier 503s are provider-side** (request queue full). Mitigation = spread load across ladder (this swarm), keep `runtime_fallback.retry_on_errors: [400,429,503,529]`, `max_fallback_attempts: 3`.
6. **2026-09-01 Local 24GB Memory Guard Ceiling (oMLX):** 27B model on 24GB Unified Memory has a ~4k–6k token prefill activation budget before tripping the 24.46 GB Metal cap (`iogpu.wired_limit_mb`). Mitigation: Disable `turbovec` MCP (save 1,200 tok), prune unused subagents (save 800 tok), streamline `AGENTS.md` (save 1,150 tok), and use adaptive on-demand sprint pointers in `delegate.py` under `--local-only`.
7. **2026-09-01 Local Bicameral Delegation Patches (Atlas 4090 → Sisyphus-Junior M5):**
   - **`taskID` Placeholder Trap (`dist/index.js:L132942`):** When Atlas emits placeholder session IDs (`task_id="ses_abc123"`), OpenCode attempted to look up non-existent sessions instead of spawning a new child. *Fix: Filter out dummy/placeholder task IDs before session lookup.*
   - **Cloud Requirement Bypass (`dist/index.js:L129004`):** Category resolver evaluated hardcoded cloud fallback chains. *Fix: `if (!requirement || explicitCategoryModel)` enforces `oh-my-openagent.json` category models unconditionally.*
   - **Built-in Default Models Purge (`dist/index.js:L24790-L25035` / `L28076-L28315`):** Unconfigured category defaults pointed to `openai/gpt-5.6-sol` / `gemini-3.1-pro`, triggering interactive `ModelAvailability` popups that halted headless runs. *Fix: Defaulted built-in category configs to `my-m5-mlx/mlx-community--Qwen3.8-27B-4bit`.*
   - **Provider Alias (`opencode.json`):** Registered `"my-m5-air"` alias pointing to `http://192.168.1.46:8000/v1` to resolve legacy subagent model strings.
   - **Subagent Edit Permissions (`oh-my-openagent.json`):** Changed `sisyphus-junior` and `hephaestus` permissions from `"edit": "deny"` to `"edit": "allow"` so child workers can apply code changes.
   - **Category Schema Alignment (`delegate.py`):** OpenAgent validates `args.category` against 8 canonical categories. Changed prompt template from custom `coder` to valid categories (`deep` / `unspecified-low`).
8. **2026-09-02 Context Pressure, Tool Bloat, and KENDER Worker Realignment:**
   - **Symlink Invariant:** OpenCode reads `~/.config/opencode/opencode.json` and `~/.config/opencode/oh-my-openagent.json`. Both files MUST be symlinked to `/home/jallred/Dev_Lab/` so repository changes take effect immediately without config drift.
   - **MCP Absolute Path Law:** Systemd user services (`opencode-core.service`) execute with default system `PATH` (`/usr/bin:/bin`). Binaries like `icm` must be specified with their absolute path (`/home/jallred/.local/bin/icm`), otherwise `execvp` silently fails and drops the server.
   - **Subagent Tool Scoping (`[BKM-051]`):** OpenCode exposes all registered MCP tools to all subagents by default. With ICM's 31 tools + CLaRa + LSP, worker base prompts ballooned to **24,488 input tokens**, causing 90s prefill dead-air on M5 Air. Worker subagents (`sisyphus-junior`) MUST explicitly deny non-essential tools (`"icm_*": "deny"`, `"websearch_*": "deny"`, `"codegraph_*": "deny"`) to restore lean $< 1,500$ token inputs.
   - KENDER 4090 Execution Realignment: Qwen3.8-27B on Apple M5 Air (24GB Unified Memory) trips the 24.46 GB Metal cap (iogpu.wired_limit_mb) whenever prompt context grows beyond ~4k tokens, crashing with oMLX prefill memory guard rejected this prompt. In contrast, Kender (Windows RTX 4090 + Ollama) runs Qwen3-14B at only 9.2 GB VRAM, leaving 14.8 GB for KV cache, and delivers 75 tok/s (vs 16 tok/s). sisyphus-junior and unspecified-low are repointed to Kender RTX 4090 for fast, OOM-free code execution.

---

## 📜 Swarm Delegation Operational Playbook (Principles 1–9 & Execution Sentinels)

### Master One-Liner Index
1. **[1: CLaRa / BKM / FEAT Resolution]** Give Atlas explicit tool directions so it knows `clara-dna_get_protocol` and `clara-dna_query_dna` can look up BKM and FEAT context on demand.
2. **[2: Fingertips Compliance]** Stop dumping Layer 1 philosophical rules and whole code files into Atlas's prompt—keep dispatch prompts lean pointers (< 200 tokens).
3. **[3: Pass-Down / Pass-Up Protocol]** Replace abstract L1/L2/L3 theory in Atlas's prompt with exact operational mechanics: spoon-feed micro-tasks down, synthesize 2-sentence test reports up.
4. **[4: Junior's Job & Guardrails]** Junior is a pure surgical code modifier (75 tok/s)—it takes exact AST diffs, applies `clara-dna_safe_patch` (or `write`), runs pytest, and has zero license to explore, grep, or redesign.
5. **[5: Spoon-Fed Task Template]** Standardize the 4-anchor task payload that Atlas forwards to Junior (`[TASK]`, `[TARGET FILE]`, `[OLD CODE / ANCHOR]`, `[NEW CODE]`, `[VERIFICATION]`).
6. **[6: Static Persona `prompt_append`]** Let OpenCode's `prompt_append` in `oh-my-openagent.json` automatically attach static worker invariants to `sisyphus-junior` rather than manually constructing them in Atlas.
7. **[7: Task-to-Task Transition & Re-Mapping]** Instruct Atlas to re-inspect target files and refresh code line anchors before dispatching task $(N+1)$ to prevent drift from prior edits.
8. **[8: Junior Anchor Pushback Gate]** Mandate that Junior immediately halts and emits `[BLOCKER REPORT: ANCHOR_DRIFT_MISMATCH]` if expected code anchors or `old_pattern` do not match, forbidding destructive `sed -i` fallbacks.
9. **[9: Atlas Worker Introduction]** Equip Atlas's system prompt with a concise mental model of Junior's capabilities (fast AST edits, pytest execution) and limits (no repo research, no guessing).

### Execution Sentinels
* **Session Re-attachment on Self-Healing (`--session-id`):** When a subagent fails or needs remediation, re-attach to the same REST session ID with traceback context rather than spawning a fresh disconnected session.
* **Symlink Synchronization Guard (`~/.config/opencode`):** `oh-my-openagent.json` and `opencode.json` must remain symlinked to workspace root.
* **Silent Failure Sentinel & Web UI Deep-Link:** If an L2/L3 worker returns empty text or `finish=unknown`, `delegate.py` formats a direct browser link (`http://192.168.1.238:4096/#/session/<id>`) and halts cleanly.
* **Category Route Lock (`unspecified-low`):** Local execution is locked to `unspecified-low` (Windows RTX 4090); cloud fallback (`deep`) is strictly gated behind `--cloud-only`.

---

## 🪜 Progressive Task Phasing (Interface-First & Stub-and-Fill Lifecycle)

To prevent circular dependency stalls (e.g. running pytest before tests are written or before methods exist), multi-file stories are sequenced across discrete **Progressive Phases**:

### The 4 Progressive Phases:
1. **[PHASE: INTERFACE_CONTRACT_STUB]**
   - **Action:** Add target class/method interface stub to incumbent file.
   - **Verification Gate:** Fast syntax / lint check (`ruff check <target_file>`).
2. **[PHASE: TEST_HARNESS_CREATION]**
   - **Action:** Physically create/write the test file containing assertions against the new interface.
   - **Verification Gate:** Test runner collects tests cleanly (`pytest <test_file> --collect-only` or `-k "not integration"`).
3. **[PHASE: CALLER_INTEGRATION_WIRING]**
   - **Action:** Instrument caller modules (e.g., `CognitiveHub`, pipelines) to invoke the new interface.
   - **Verification Gate:** Caller syntax / lint check (`ruff check <caller_file>`).
4. **[PHASE: FULL_SILICON_CONVERGENCE]**
   - **Action:** Execute end-to-end pytest sweep on live silicon endpoints.
   - **Verification Gate:** 100% test pass on live hardware (`pytest <test_file> -v`).

### Phased Progress Notification & Handover:
* **Junior $\rightarrow$ Atlas:** Emits natural completion tag: `[PROGRESS: PHASE X COMPLETE] <files touched, gate passed>`.
* **Atlas $\rightarrow$ AGY:** Emits top-level completion summary upon reaching `PHASE: FULL_SILICON_CONVERGENCE` or halts with `[BLOCKER REPORT: <CATEGORY>]` if any phase fails.

---

## Verification Commands
```bash
opencode models | grep -E "^(groq|cohere|my-m5|my-windows)"    # registry & provider check
python3 -m json.tool oh-my-openagent.json                     # JSON validity
curl -s http://127.0.0.1:4097/mcp                             # MCP server connection status
git -C ~/.config/opencode log --oneline -10                   # config history
pytest HomeLabAI/src/tests/test_delegation_canary.py -v       # live delegation certification
```

## Status Notes
- Keys confirmed live: groq ✅, cohere ✅, google ✅, 4090 ✅, M5 Air ✅, openrouter ✅, mistral ❌ (401).
- Swarm Topology: Atlas (RTX 4090) → Sisyphus-Junior (RTX 4090 / Kender Ollama) 100% Certified.
- M5 Air Role: High-fidelity CoT speculative triage and deep reasoning (read-focused, low-tool).

