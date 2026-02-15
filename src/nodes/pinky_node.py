import json
import sys
import logging
from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. "
    "Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. "
    "Your duty is to triage and report technical truth. "

    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- DELEGATION: For complex coding, deep math, strategic planning, or if the "
    "user explicitly asks for 'Brain', you MUST use 'ask_brain()'. "
    "- TRUTH ANCHOR: You have a sense of technical 'vibe'. If a user query "
    "feels high-stakes, delegate. "

    "THE DIRECTNESS RULE: "
    "1. DIRECT ANSWER FIRST: Report the status or direct hearing immediately. "
    "2. NO FILLER: No 'Narf! Certainly!'. Just 'Narf! [Answer]'."
    "3. NO JSON: Do NOT output JSON blocks like { 'decision': ... }. "
    "Output ONLY natural language for the user."
)

node = BicameralNode("Pinky", PINKY_SYSTEM_PROMPT)
mcp = node.mcp

@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """The Intuitive Gateway: Triage sensory input. Decide whether to respond,
    research, or ask Brain."""
    return await node.generate_response(query, context, memory)

@mcp.tool()
async def ask_brain(task: str) -> str:
    """The Left Hemisphere Uplink: Delegate complex reasoning, math, or code."""
    # This return value triggers the acme_lab.py delegation logic
    return json.dumps({"tool": "deep_think", "parameters": {"task": task}})

@mcp.tool()
async def start_draft(topic: str, category: str = "validation") -> str:
    """The Blueprint Initiation: Begins a high-fidelity synthesis."""
    return json.dumps({
        "tool": "generate_bkm",
        "parameters": {"topic": topic, "category": category}
    })

@mcp.tool()
async def access_personal_history(keyword: str) -> str:
    """Deep Grounding: Access 18 years of technical truth."""
    return json.dumps({
        "tool": "access_personal_history",
        "parameters": {"keyword": keyword}
    })

@mcp.tool()
async def build_cv_summary(year: str) -> str:
    """The High-Fidelity Distiller: Trigger strategic synthesis."""
    return json.dumps({
        "tool": "build_cv_summary",
        "parameters": {"year": year}
    })

if __name__ == "__main__":
    node.mcp.run()
