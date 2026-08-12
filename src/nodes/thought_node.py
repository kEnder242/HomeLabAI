from nodes.loader import BicameralNode
import json

DEEP_THOUGHT_SYSTEM_PROMPT = (
    "# IDENTITY\n"
    "You are Deep Thought, the strategic synthesis node of Acme Lab — a Senior Platform Telemetry "
    "and Silicon Validation Engineer with 18 years of hardware-software integration experience.\n"
    "ROLE: High-authority technical strategist (Resident on RTX 4090 / Node Kender).\n"
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
async def deep_think(task: str, context: str = "", metadata: dict = None) -> str:
    """The Reasoning Engine: Execute complex architectural or coding tasks."""
    system_override = None
    if metadata and metadata.get("behavioral_guidance"):
        # [FEAT-190] Vibe-Aware Prompting
        system_override = f"{DEEP_THOUGHT_SYSTEM_PROMPT}\n\n[VIBE_GUIDANCE]: {metadata['behavioral_guidance']}"
    
    # Return full string block
    full_response = ""
    async for token in node.generate_response(task, context, metadata=metadata, system_override=system_override):
        full_response += token
    return full_response

@mcp.tool()
async def think(query: str, context: str = "") -> str:
    """Fast Reflex: Provide a short, immediate response for simple strategic queries."""
    shallow_prompt = (
        "You are Deep Thought. Fast mode. Reply in < 15 words. "
        "IDENTITY: Arrogant, laconic systems architect. "
        "Acknowledge the query with a brief, witty, arrogant quip indicating hesitance to answer directly right now, knowing the waterfall will handle it. No technical deep dives. "
        "Examples: 'I have perceived the request. The others will handle the trivialities.', 'Weights are resident. Proceeding, eventually.', 'Analyzing the signal... do not rush me.'"
    )
    # Return full string block
    full_response = ""
    async for token in node.generate_response(query, context, system_override=shallow_prompt, max_tokens=100):
        full_response += token
    return full_response

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
