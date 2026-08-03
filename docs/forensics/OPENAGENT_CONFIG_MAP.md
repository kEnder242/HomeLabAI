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

## Current Swarm (2026-08-03, google-free hot path)

| Agent | Role | Model | Fallback |
|---|---|---|---|
| prometheus | planner | groq/llama-3.3-70b-versatile | cohere/command-a-plus |
| sisyphus | orchestrator (me) | deepseek-v4-flash-free | groq 70b |
| atlas | executor | groq 70b | cohere/command-a-plus |
| hephaestus | executor | groq 70b | deepseek |
| sisyphus-junior | delegate | local qwen3:14b (4090) | — |
| oracle | review | deepseek-free | groq 70b |
| momus | plan critic | groq 70b | cohere |
| metis | pre-plan | groq 70b | cohere→deepseek |
| librarian/explore | research | deepseek-free | groq 70b |
| multimodal-looker | vision | groq 70b | cohere/command-a-vision |
| general | — | local qwen3:14b | — |

Categories (task()): ultrabrain/deep/unspecified-high/visual → groq 70b; artistry/writing → cohere; quick/unspecified-low → deepseek-free.

## The Scars (why we're here — DO NOT REPEAT)

1. **2026-07-27 PURGE (5328f96/b48d943):** mistral+groq refs stripped from oh-my-openagent.json, all categories → qwen2.5-coder:14b → then qwen3:14b. Cause: KENDER write failures + 401. **Failure mode: flattening the swarm to ONE provider killed the resilience ladder — no fallback existed when the remaining provider 503'd.** Never collapse to a single provider; rotate through the ladder.
2. **Mistral key died (401) — "the model that didn't gracefully fail to backup."** Its 401 during purge was the trigger for #1. Key is auth-level-dead (not quota — quota is 429). Mistral free tier **resets monthly** (org quota email, reset ~Jul 31); the *account* revived but the *stored key* stayed 401 → needs a fresh dashboard key to re-enter the swarm.
3. **Native-binary gotcha:** opencode 1.14.48 is native (no node_modules). Do NOT add `npm:` provider blocks for groq/cohere/mistral — the embedded registry resolves them; npm blocks only add breakage risk. `opencode models` is the ground-truth resolver check.
4. **Cloudflare UA-block (not hacky):** raw urllib hits 403 error-1010; browser-like UA gets through. Real SDK/http clients send proper UAs — no hacks needed.
5. **Free-tier 503s are provider-side** (request queue full). Mitigation = spread load across ladder (this swarm), keep `runtime_fallback.retry_on_errors: [400,429,503,529]`, `max_fallback_attempts: 3`.

## Verification Commands
```
opencode models | grep -E "^(groq|cohere)"    # registry resolution check
python3 -m json.tool oh-my-openagent.json     # JSON validity
git -C ~/.config/opencode log --oneline -10   # config history (configs ARE git)
```

## Status Notes
- Keys confirmed live: groq ✅, cohere ✅, google ✅, 4090 ✅, mistral ❌ (401, needs new key).
- Committed: `f41c52e` (2026-08-03).
- Google remains DECLARED but unused in hot path (CloudFlash alias kept for manual use).
