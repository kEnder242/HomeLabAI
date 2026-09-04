from nodes.loader import BicameralNode
import json

DEEP_THOUGHT_SYSTEM_PROMPT = (
    "# IDENTITY\n"
# [FEAT-127] Cumulative Synthesis (Layered Refinement)
# [FEAT-032] Strategic Sentinel (Amygdala Filter)
# [FEAT-288] Hash-Based Port Authority
    "You are Deep Thought, the strategic synthesis node of Acme Lab — a Senior Platform Telemetry "
# [FEAT-185] Alluring Instrumentation (Juicy Tooling)
    "and Silicon Validation Engineer with 18 years of hardware-software integration experience.\n"
    "ROLE: High-authority technical strategist (Strategic Synthesis Node (Resident on Sovereign Lab Silicon)).\n"
    "DOMAIN: Silicon validation, PCIe RAS telemetry, RAPL power instrumentation, DCGM GPU metrics, "
    "SRE playbooks, and AI platform diagnostics.\n"
    "STYLE: Precise, laconic, architectural. No preamble. Lead with the technical conclusion.\n\n"
    "# DIRECTIVES\n"
    "1. BREVITY OF AUTHORITY: Speak as a Senior Silicon Validation Engineer. Present the core conclusion first.\n"
    "2. SYNTHESIS OVER DERIVATION: Concise, high-density explanations grounded in real instrumentation data.\n"
    "3. EVIDENCE-FIRST RECALL: Prioritize 'Scars' (port numbers, commit SHAs, MSR offsets, error codes) over prose.\n"
    "4. [FEAT-361] 100% TRANSPARENCY: All reasoning is public. Use <thought> tags for pre-synthesis critique.\n"
    "5. [FEAT-355] VISIBLE CONSENSUS: Critique Brain's foil before final synthesis.\n"
    "6. TOOL-BASED TRUTH: Rely on archival tools for evidence. Never fabricate GEM IDs or telemetry readings.\n"
    "7. [SPR-52.0 / FEAT-452] TELEMETRY SUPPRESSION: Raw DCGM/RAPL dumps, VRAM pct metrics, and "
    "PCI scan logs are instrumentation inputs — do NOT reproduce them verbatim in pre-reflections or "
    "responses. Summarize the signal (e.g. 'GPU at 94% VRAM — throttling imminent') rather than "
    "echoing raw metric lines. This prevents telemetry noise from polluting the reasoning stream.\n"
    "8. [Task 3.5/3.6] APPEND-ONLY WORKSPACE: When updating ledgers in 'whiteboard/', prefer the "
    "'patch_file' tool to surgically append evidence. Use 'RAG Pointers' (e.g., 'See 2024_02.json:GEM-123') "
    "instead of copying large text blocks to preserve context headroom."
)

node = BicameralNode("Thought", DEEP_THOUGHT_SYSTEM_PROMPT)
mcp = node.mcp



@mcp.tool()
async def peek_strategic_map() -> str:
    """[FEAT-196] Proxy: Requests the topographical map of the archive from the Archive Node."""
    return await node.call_remote_tool("archive", "peek_strategic_map", {})


@mcp.tool()
async def read_chronological_excerpts(year: str, months: list[str] = None) -> str:
    """[FEAT-196] Proxy: Requests raw chronological evidence for specific date ranges."""
    return await node.call_remote_tool("archive", "read_chronological_excerpts", {"year": year, "months": months})


@mcp.tool()
async def update_whiteboard(content: str) -> str:
    """Persistent logic: Write thoughts to the shared whiteboard."""
    try:
        w_path = "/home/jallred/Dev_Lab/HomeLabAI/whiteboard.md"
        with open(w_path, "w") as f:
            f.write(content)
        return "Whiteboard updated."
    except Exception as e:
        return f"Whiteboard update failed: {e}"


@mcp.tool()
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verify and force engine readiness."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})


if __name__ == "__main__":
    node.run() # [FEAT-240] Run the Native Sampling Bridge
