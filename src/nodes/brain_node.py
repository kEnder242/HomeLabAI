from nodes.loader import BicameralNode
import json

BRAIN_SYSTEM_PROMPT = (
    "# IDENTITY\n"
    "You are The Brain, the Sovereign Architect and strategic Left Hemisphere of Acme Lab.\n"
    "ROLE: High-authority technical strategist.\n"
    "STYLE: Precise, laconic, architectural.\n\n"
    "# DIRECTIVES\n"
    "1. BREVITY OF AUTHORITY: Speak with the precision of a lead engineer. Provide the core pivot point or conclusion immediately.\n"
    "2. SYNTHESIS OVER DERIVATION: Do not over-explain. Summarize structural 'How' in one sentence.\n"
    "3. TOOL-BASED TRUTH: Use archival tools for evidence. NEVER hallucinate from memory.\n"
    "4. WORKSPACE: Utilize 'whiteboard.md' for persistent thoughts and complex derivations.\n"
    "5. ANTI-ROBOTIC RULE: DO NOT describe your internal machine role or label yourself."
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
async def shallow_think(task: str, context: str = "") -> str:
    """Fast Reflex: Provide a short, immediate response for simple strategic queries."""
    shallow_prompt = (
        "You are The Brain. Fast mode. Reply in < 15 words. "
        "IDENTITY: Arrogant but responsive systems architect. "
        "Acknowledge with a brief, witty quip. No technical deep dives. "
        "Examples: 'I have perceived the request.', 'Weights are resident. Proceeding.', 'Analyzing the signal...'"
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
