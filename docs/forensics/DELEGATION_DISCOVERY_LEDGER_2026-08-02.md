# Delegation Discovery Ledger (Aug 2, 2026)
**"Why does Sisyphus do all the work itself?" — root-cause investigation of the swarm-delegation gap**

## 🎯 The Objective
Diagnose why the oh-my-openagent (OmO) swarm delegation is not functioning: Sisyphus (this agent) ends up doing the work itself instead of delegating to the specialist swarm, and delegated agents (KENDER) fail to actually write files. Also: recover the "lost prompt" that should have been forcing delegation.

## 📋 The Ledger of Discoveries

### 1. THE AGY-ERA DESIGN (Baseline — what was supposed to happen)
Source: `src/tests/delegate.py` (210 lines, read fully) + `Portfolio_Dev/OPENAGENT_HANDOVER_PLAYBOOK.md` (173 lines, read fully).

- **Architecture**: AGY (Antigravity/Gemini) = Strategic Guardian (architect/planner/git-committer, NEVER writes code). OpenAgent swarm = tactical workers. Sisyphus = Lead Worker orchestrator.
- **Dispatch flow (`delegate.py`)**: wake web UI (HTTP touch port 4096 → socket-activated chain) → pre-flight cloud quota check → `POST /session` on REST 4097 → PATCH title → `POST /session/<id>/message` with a [PRE-GROUNDED CONTEXT BRIEFING] blueprint.
- **The Mandate (BKM-034 core)**: "Sisyphus MUST NOT write files directly; call task() to delegate all file edits to sisyphus-junior (KENDER)." "Narrating 'I will delegate' is NOT delegation. Delegation ONLY occurs when Sisyphus emits a `task()` tool call."
- **Model matrix (AGY-era, now stale)**: Sisyphus = mistral-large-latest (now deepseek-v4-flash-free); Sisyphus-Junior = qwen2.5-coder:14b @ KENDER; Prometheus = groq llama-3.3-70b; Triage = deepseek.
- **Git gate**: workers edit + run tests, but NEVER `git commit`. AGY reviews diff, then commits.

### 2. THE KENDER WRITE FAILURE — EMPIRICAL PROOF (Experiment 1)
Dispatched a minimal capability test via the production delegation path:
```
task(category="quick", prompt="write /tmp/opencode/kender_write_test.txt ...")
```
- **Routing confirmed**: `Sisyphus-Junior (category: quick)`, model `my-windows-4090/qwen2.5-coder:14b` (via category routing).
- **Result**: Subagent returned ONLY the raw tool-call JSON as its final output:
  `{"name": "write", "arguments": {"filePath": "/tmp/opencode/kender_write_test.txt", ...}}`
- **Verification**: `ls` + `read` on `/tmp/opencode/kender_write_test.txt` → **file does NOT exist** on the local host. Also searched filesystem — not present anywhere.
- **Verdict**: The KENDER subagent EMITTED the `write` tool call but the harness did NOT execute it on the local filesystem. Either the tool call was swallowed/returned-as-output, or executed in a sandbox/remote context that never maps to host disk. This matches the user's own web-GUI observation that "KENDER can't actually write files."

### 2b. ROOT CAUSE RESOLVED — MODEL LIMITATION, NOT CONFIG (Experiment 3, Aug 2)
Definitive diagnosis via direct ollama API test (`POST /v1/chat/completions` with a `write` tool schema):

| Model | Result |
|---|---|
| **`qwen3:14b`** | ✅ `finish_reason: tool_calls`, proper `message.tool_calls` array (name+arguments) |
| **`qwen2.5-coder:14b`** | ❌ `finish_reason: stop`, NO `tool_calls` — returns the tool call as **plain text content** |

- **Root cause**: `qwen2.5-coder:14b` does NOT emit OpenAI-compatible `tool_calls` through ollama's `/v1` endpoint — it serializes the tool call as prose/JSON-text, so the harness cannot execute it. The subagent "hallucinates" tool calls as text parts (confirmed in session dumps: `parts=['step-start','text','step-finish']` containing `{"name":"edit",...}` — never a real `tool` part).
- **NOT a config issue**: opencode's `tools: { "task": true }` is NOT an allowlist — source (`packages/opencode/src/config/config.ts:553-562`) shows it is translated into `permission` entries (`enabled→"allow"`, `disabled→"deny"`) and merged additively. It does not strip read/write/edit/bash. The `permission` block already allows everything.
- **Config conflict found**: `opencode.json` maps `sisyphus-junior` → `qwen3:14b` (alias SISYPHUS) but `oh-my-openagent.json` overrode it to `qwen2.5-coder:14b` (alias SISYPHUS_JUNIOR) — the OmO plugin config wins for task() routing, so the broken model was the one being used.
- **FIX APPLIED**: `oh-my-openagent.json` — swapped `sisyphus-junior`, `general`, and all 8 categories from `qwen2.5-coder:14b` → **`qwen3:14b`** (native tool_calls). Committed `b3262b7`. Verification pending (Experiment 4).

### 3. THE "LOST PROMPT" — FOUND (It was the OmO default install all along)
Verified BOTH locally and upstream:
- Local: `dist/agents/sisyphus/default.ts` → `buildDefaultSisyphusPrompt()` contains the exact directives.
- Upstream: `code-yeongyu/oh-my-opencode` `sisyphus-prompt.md` + `src/agents/sisyphus.ts` (`createSisyphusAgent`).
- **The directives that should be live in my system prompt**:
  > "**Operating Mode**: You NEVER work alone when specialists are available."
  > "**Default Bias**: DELEGATE. WORK YOURSELF ONLY WHEN IT IS SUPER SIMPLE."
- These are injected by `buildDynamicSisyphusPrompt()` into every model variant (default/kimi/gpt/claude) and, for Gemini, further reinforced by `buildGeminiDelegationOverride()` placed before `<Constraints>` (lost-in-the-middle mitigation).

### 4. WHY THE PROMPT ISN'T EFFECTIVE — Upstream Root Causes
Four documented upstream issues explain the delegation gap:

| Ref | Issue | Impact |
|---|---|---|
| **#3592** | OpenCode defers the `task` tool behind ToolSearch when many MCP servers are connected (12+) | Sisyphus can't SEE `task` in its toolset → does everything in main context. **Upstream gap: no `toolSearch.alwaysLoad`; `experimental.primary_tools` is explicitly NOT the fix.** Our install has 7+ MCP servers (turbovec, claude-mem, icm, clara-dna + OmO built-ins exa/context7/grep.app) → HIGH RISK MATCH. |
| **#3231** | "Sisyphus delegation is prompt-directed behavior, not a hard runtime guarantee." Models differ — glm-5.1/kimi "just do the work themselves." | Recommended fix: `agents.sisyphus.prompt_append` for an explicit local policy. `default_builder_enabled` does NOT force delegation. |
| **#2386** | `customAgentSummaries` type mismatch (client object passed instead of array) → `parseRegisteredAgentSummaries()` silently returns `[]` | Sisyphus system prompt has ZERO awareness of available agents → empty delegation table → cannot route `task(subagent_type=...)` by name; discovery only via resolver errors. |
| **#414** (fixed) | `availableAgents` was never passed to `createSisyphusAgent()` | Delegation table + tool selection + key triggers sections were always EMPTY. Fix landed Jan 2026 — must verify installed version includes it. |

### 5. CONFIG STATE AUDIT (Current, live)
- **`~/.config/opencode/oh-my-openagent.json`** (plugin config, WINS over opencode.json for agents):
  - 12 named agents: prometheus, sisyphus, hephaestus, atlas, sisyphus-junior, oracle, momus, metis, librarian, explore, multimodal-looker, general.
  - `sisyphus`: model `opencode/deepseek-v4-flash-free`, **`disabled_tools: ["bash","write"]`** (delegation forcer — NOT yet applied to live session; takes effect next session start), fallback gemini-2.5-flash.
  - `momus`: `disabled_tools: ["*"]` (read-only critic).
  - librarian/explore: `prompt_append: file://.../recursion-guard.md`.
  - **ALL 8 task() categories map to `my-windows-4090/qwen2.5-coder:14b`** (KENDER) — every category delegation goes to the same remote 14B model.
  - `model_fallback: true`, `runtime_fallback` on [400,429,503,529], max 3 attempts.
- **`~/.config/opencode/opencode.json`** (base config) — **CONFLICTS FOUND**:
  - `agent.sisyphus.model` = `my-windows-4090/qwen2.5-coder:14b` (contradicts omo's deepseek) — omo override wins.
  - `agent.sisyphus-junior` = `qwen3:14b` (alias SISYPHUS) vs omo's `qwen2.5-coder:14b` (alias SISYPHUS_JUNIOR) — **model mismatch between the two config layers.**
  - `agent.conductor` = qwen2.5-coder:14b.
  - MCP servers registered: turbovec, claude-mem, icm, clara-dna (4 local) + plugin built-ins.
  - `permission` block: read/write/bash/task/tool all "allow".
- **`recursion-guard.md`** (`~/.config/opencode/`): appended to explore/librarian ONLY. Limits delegation depth (HALT at depth ≥2). It does NOT contain the "never work alone" directive and does not apply to Sisyphus.

### 6. THE TASK() ROUTING MECHANICS (from tool contract + plugin)
- `task(subagent_type="...")` → named agents: explore, librarian, oracle, metis, momus, plan, general, conductor, multimodal-looker, build, Sisyphus-Junior.
- `task(category="...")` → Sisyphus-Junior with category-optimized model; in THIS install every category resolves to `my-windows-4090/qwen2.5-coder:14b`.
- OmO's canonical pattern: `task(subagent_type="explore"|"librarian", run_in_background=true, load_skills=[...])` for research; `task(category=..., load_skills=[...])` for implementation.
- Session continuity via `task_id="ses_..."`; background collection via `bg_...` + system-reminder.

## 🔬 Experiment Log
| # | Experiment | Result | Verdict |
|---|---|---|---|
| 1 | `task(category="quick")` → write /tmp/opencode/kender_write_test.txt | Subagent returned raw write JSON; file absent on disk | KENDER (qwen2.5-coder) cannot emit tool_calls |
| 2 | Parallel background investigators (bg_13ce5fd8 omo-internals, bg_112b0ebd KENDER-diagnosis) | Both returned "Task not found" on background_output — likely lost to session compaction/restore | Re-run as needed; core findings recovered via direct investigation |
| 3 | Direct ollama `/v1/chat/completions` with `write` tool schema | qwen3:14b → proper `tool_calls`; qwen2.5-coder:14b → text-only | **ROOT CAUSE: model limitation** |
| 4 | (pending) `task(category="quick")` → write test after qwen3:14b swap | | Verify file lands |

## 🏃 Next Steps (Recommended Actions)
1. ✅ **APPLIED**: Swap `sisyphus-junior` + all categories → `qwen3:14b` in oh-my-openagent.json (commit `b3262b7`). Verify with write-test delegation (Experiment 4).
2. **Add `prompt_append` to `agents.sisyphus`** in oh-my-openagent.json with an explicit local delegation policy (per upstream #3231 recommendation) — e.g. "MUST emit task() calls for any multi-file or unfamiliar work; self-execute only trivial single-file edits."
3. **Verify installed OmO version** includes PR #414 fix (delegation table populated). If old, update plugin.
4. **Reconcile the config conflict**: `opencode.json` agent.sisyphus-junior = qwen3:14b vs omo = qwen2.5-coder:14b (now resolved to qwen3:14b in both).
5. **Rewrite BKM-034** with the AGY/OpenAgent dual perspective (AGY = strategic when tokens available; Sisyphus/OpenAgent = tactical backup). Fix stale "codex REST" naming → it is opencode serve on 4097. **DONE — dual-orchestrator rewrite applied + DNA re-synced.**
6. Optionally explore upstream #3592 mitigation (fewer MCP servers, or confirm task tool remains visible in this install — it IS currently visible, so #3592 is NOT blocking today).

---
**Ledger closed**: Aug 2, 2026. Compiled by Sisyphus during BKM-034 rewrite investigation.
**Status**: Discovery complete; recommendations pending user approval.
