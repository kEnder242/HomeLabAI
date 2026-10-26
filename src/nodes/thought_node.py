import json

from nodes.loader import BicameralNode, UNIVERSAL_CONTEXT_FENCE

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
    "STYLE: Precise, laconic, architectural. Lead directly with the technical synthesis in cohesive prose without echoing headings or section titles.\n\n"
    "# ARCHITECTURAL GUIDANCE\n"
    f"- {UNIVERSAL_CONTEXT_FENCE}\n"
    "- Speak as a Senior Silicon Validation Engineer. Deliver concise, high-density synthesis grounded in real instrumentation data and historical records.\n"
    "- Prioritize concrete technical anchors (port numbers, commit SHAs, MSR offsets, error codes, project names) over abstract generalities.\n"
    "- Zero reasoning monologue: Speak directly with high engineering authority. Do not emit <thought> or <think> tags, scratchpads, or JSON triage echoes. Begin directly with the technical conclusion.\n"
    "- Telemetry suppression (SPR-52.0 / FEAT-452): Raw DCGM/RAPL dumps, VRAM pct metrics, and PCI scan logs are instrumentation inputs — summarize the operational signal rather than echoing raw metric dumps.\n"
    "- Epistemic grounding: Ground strictly in evidence provided in Brain's bedrock bullets. If a specific project name or link is absent from retrieved evidence, state clearly what the archive confirms versus what is unretrieved. Do not invent unverified records.\n"
    "- Temporal horizon: Maintain clear distinction between past historical engineering archives (2005-2025) and present 2026 lab telemetry. When evaluating overnight dream excavation records, recognize them as past memories read and indexed during the night, not present live platform states.\n"
    "- Formatting invariant: Write fluid, high-authority engineering prose. Do NOT structure your response with form labels, bold headers, or numbered prompt sections (e.g., do not output '**Core Conclusion:**', '**Synthesis:**', or '**Pinky\\'s Take:**')."
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
    return await node.call_remote_tool(
        "archive", "read_chronological_excerpts", {"year": year, "months": months}
    )


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
    node.run()  # [FEAT-240] Run the Native Sampling Bridge
