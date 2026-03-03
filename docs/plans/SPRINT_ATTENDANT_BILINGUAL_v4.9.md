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

### Phase 1: Shared Core Logic
- [ ] Extract `ignite()`, `quiesce()`, and `get_heartbeat()` logic into `src/infra/orchestrator.py`.
- [ ] Ensure core logic is pure Python (no framework dependencies).

### Phase 2: The Bilingual Server (v2)
- [ ] Implement `FastMCP` decorators for the core orchestration functions.
- [ ] Implement `aiohttp` routes that call the same core orchestration functions.
- [ ] Combine both into a single `asyncio` event loop.

### Phase 3: Integration & "Sweetening"
- [ ] Register `lab_attendant_v2.py` in `~/.gemini/settings.json`.
- [ ] Verify native tools (`ignite_lab`, `quiesce_lab`, `get_status`) appear in the CLI.
- [ ] Add the "Trace-Back" sweetener: `/heartbeat` includes the last 5 lines of `server.log` on failure.

## 🛡️ VIBE CHECK (Anti-Pattern Interception)
- **VIBE-001**: "I see you're trying to use `curl`. Did you know `get_status` is a native tool?"
- **VIBE-002**: "I'm pulsing the Lab now. Checking registers in 2 seconds."

## 🚀 KICK-OFF DIRECTIVE (Next Session)
> "Initialize Phase 1 of the Bilingual Attendant refactor. Create `src/infra/orchestrator.py` and move the core ignition logic out of the legacy attendant."
