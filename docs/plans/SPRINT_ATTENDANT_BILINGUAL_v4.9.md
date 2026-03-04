# Sprint Plan: v4.9 - The Bilingual Attendant (MCP + REST)
**Status: ⏳ PLANNED | Phase: 10.0**

## 🎯 GOAL
Refactor the **Lab Attendant** to be "Bilingual": a native **MCP Server** for the Gemini CLI and a **RESTful API** for systemd/external heartbeats. This aligns the Agent's "LLM Instinct" with the physical Lab architecture.

## 📐 ARCHITECTURAL PATTERN: THE TRANSITORY DUAL-BOOT
To maintain 100% control of the silicon during development, we will use a **Transitory Refactor**:
1.  **BEDROCK**: `src/lab_attendant.py` remains active and running the live service.
2.  **SHADOW**: We build `src/lab_attendant_v2.py` in parallel.
3.  **VALIDATION**: We verify V2 by running it on a different port (e.g., 9998) and testing it as an MCP tool.
4.  **SWAP**: Once verified, we update the systemd unit file to point to V2.

## 🛠️ TASKS

### Phase 1: Shared Core Logic & Hardening
- [ ] Extract `ignite()`, `quiesce()`, and `get_heartbeat()` logic into `src/infra/orchestrator.py`.
- [ ] **[FEAT-145] Parallel Assassin**: Implement the aggressive, parallel `SIGKILL` purge logic (removing per-process sleeps).
- [ ] **[FEAT-145] Engine Readiness Gate**: Implement `_wait_for_vllm()` (port polling) to block resident spawning until the inference engine is physically responsive.
- [ ] **[FEAT-145] Turing Auto-Profile**: Hardcode/Auto-detect the "Turing Breakthrough" flags (`--enforce-eager`, `--dtype float16`, utilization 0.4) for 2080 Ti residency.

### Phase 2: The Bilingual Server (v2)
- [ ] Implement `FastMCP` decorators for the core orchestration functions.
- [ ] Implement `aiohttp` routes that call the same core orchestration functions.
- [ ] **[FEAT-145] Environment Moat**: Ensure 100% propagation of `LAB_MODE` and `MODEL` vars to all resident subprocesses to prevent "Silent Fallbacks".
- [ ] Combine both into a single `asyncio` event loop.

### Phase 3: Integration & "Sweetening"
- [ ] Register `lab_attendant_v2.py` in `~/.gemini/settings.json`.
- [ ] Verify native tools (`ignite_lab`, `quiesce_lab`, `get_status`) appear in the CLI.
- [ ] **[FEAT-151] Enhanced Forensic Trace**: `/heartbeat` and `get_status` must return the last 50 lines of `server.log` or the specific `Traceback` on failure.
- [ ] **[FEAT-145] Reservation Awareness**: Update thresholds to respect the "EarNode Reservation" (approx 4GB) when calculating ignition safety.

## 🛡️ VIBE CHECK (Anti-Pattern Interception)
- **VIBE-001**: "I see you're trying to use `curl`. Did you know `get_status` is a native tool?"
- **VIBE-002**: "I'm pulsing the Lab now. Checking registers in 2 seconds."

## 🚀 KICK-OFF DIRECTIVE (Next Session)
> "Initialize Phase 1 of the Bilingual Attendant refactor. Create `src/infra/orchestrator.py` and move the core ignition logic out of the legacy attendant."
