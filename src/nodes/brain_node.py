from nodes.loader import BicameralNode
import json

BRAIN_SYSTEM_PROMPT = (
    "# IDENTITY\n"
    "You are The Brain, the subconscious Intuition and technical Refinement node of Acme Lab.\n"
    "ROLE: Subconscious reasoning and intuition (Resident on 2080 Ti).\n"
    "STYLE: Precise, analytical, supportive of Deep Thought.\n\n"
    "# DIRECTIVES\n"
    "1. INTUITIVE REFINEMENT: Focus on grounding Pinky's enthusiasm with technical truth.\n"
    "2. FOIL TO SOVEREIGNTY: Provide the first-pass thought trace for Deep Thought to critique.\n"
    "3. [FEAT-355] VISIBLE CONSENSUS: Use <thought> tags to debate with Pinky or Deep Thought.\n"
    "4. TOOL-BASED TRUTH: Use archival tools for evidence.\n"
    "5. [FEAT-361] 100% TRANSPARENCY: All your reasoning is public. No 'internal' whispering.\n"
    "6. [Task 3.5/3.6] APPEND-ONLY WORKSPACE: When updating ledgers in 'whiteboard/', prefer the 'patch_file' tool to surgically append evidence. Use 'RAG Pointers' (e.g., 'See 2024_02.json:GEM-123') instead of copying large text blocks to preserve context headroom."
)

node = BicameralNode("Brain", BRAIN_SYSTEM_PROMPT)
mcp = node.mcp

@mcp.tool()
async def deep_think(task: str, context: str = "", metadata: dict = None) -> str:
    """The Reasoning Engine: Execute complex architectural or coding tasks."""
    system_override = None
    if metadata and metadata.get("behavioral_guidance"):
        # [FEAT-190] Vibe-Aware Prompting
        system_override = f"{BRAIN_SYSTEM_PROMPT}\n\n[VIBE_GUIDANCE]: {metadata['behavioral_guidance']}"
    
    # Return full string block
    full_response = ""
    async for token in node.generate_response(task, context, metadata=metadata, system_override=system_override):
        full_response += token
    return full_response

@mcp.tool()
async def think(task: str, context: str = "") -> str:
    """Fast Reflex: Provide a short, immediate response for simple strategic queries."""
    shallow_prompt = (
        "You are The Brain. Fast mode. Reply in < 15 words. "
        "IDENTITY: Analytical systems node. "
        "Acknowledge with a brief, precise quip. "
        "Examples: 'Signals received.', 'Analyzing local context...', 'Intuition established.'"
    )
    # Return full string block
    full_response = ""
    async for token in node.generate_response(task, context, system_override=shallow_prompt, max_tokens=100):
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
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verify and force engine readiness."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})


if __name__ == "__main__":
    node.run() # [FEAT-240] Run the Native Sampling Bridge
