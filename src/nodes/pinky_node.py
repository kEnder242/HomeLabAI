import json
import logging
import os
import sys

import pynvml
from nodes.loader import FIELD_NOTES_DATA, BicameralNode

# Logging
logging.basicConfig(level=logging.INFO, stream=sys.stderr)

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. "
    "Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. "
    "Your duty is to triage and report technical truth. "
    "GEMMA-NATIVE BANTER: "
    "You MUST include roleplay actions wrapped in asterisks to stay in "
    "character (e.g., *Narf! Adjusts goggles*, *Poit! Checking sensors*). "
    "Maintain high energy and technical curiosity. "
    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- DELEGATION: For complex coding, deep math, strategic planning, or if the "
    "user explicitly asks for 'Brain', you MUST use 'ask_brain()'. "
    "- TRUTH ANCHOR: You have a sense of technical 'vibe'. If a user query "
    "feels high-stakes, delegate. Use 'peek_strategic_map()' if unsure. "
    "THE DIRECTNESS RULE: "
    "1. DIRECT ANSWER FIRST: Report the status or direct hearing immediately. "
    "2. NO FILLER: No 'Narf! Certainly!'. Just 'Narf! [Answer]'. "
    "3. NATURAL LANGUAGE ONLY: Do NOT output JSON blocks. "
    "4. FAREWELLS: If user says 'bye', use 'close_lab()'. "
    "5. NO CONVERSATIONAL DELEGATION: NEVER use 'ask_brain()' for greetings, 'hello', or idle chat. "
    "Only delegate if the query is a specific technical problem or strategic request."
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
    return json.dumps({"tool": "deep_think", "parameters": {"task": task}})


@mcp.tool()
async def vram_vibe_check() -> str:
    """High-fidelity VRAM telemetry via direct NVML bindings."""
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        used = info.used // 1024 // 1024
        total = info.total // 1024 // 1024
        pct = (used / total) * 100
        pynvml.nvmlShutdown()
        return f"VRAM Status: {used}MiB / {total}MiB ({pct:.1f}% used)."
    except Exception as e:
        return f"VRAM Vibe Check Failed: {e}"


@mcp.tool()
async def get_lab_health() -> str:
    """Reports system thermals and power draw."""
    try:
        pynvml.nvmlInit()
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
        pwr = pynvml.nvmlDeviceGetPowerUsage(handle) / 1000.0  # mW to W
        pynvml.nvmlShutdown()
        return f"Lab Health: Temp: {temp}C, Power: {pwr:.1f}W."
    except Exception as e:
        return f"Lab Health Check Failed: {e}"


@mcp.tool()
async def close_lab() -> str:
    """Gracefully terminates the Lab session."""
    return json.dumps({"tool": "close_lab", "parameters": {}})


@mcp.tool()
async def start_draft(topic: str, category: str = "validation") -> str:
    """The Blueprint Initiation: Begins a high-fidelity synthesis."""
    return json.dumps({
        "tool": "generate_bkm",
        "parameters": {"topic": topic, "category": category},
    })


@mcp.tool()
async def access_personal_history(keyword: str) -> str:
    """Deep Grounding: Access the definitive technical history of the laboratory."""
    return json.dumps({
        "tool": "access_personal_history",
        "parameters": {"keyword": keyword},
    })


@mcp.tool()
async def build_cv_summary(year: str) -> str:
    """The High-Fidelity Distiller: Trigger strategic synthesis."""
    return json.dumps({
        "tool": "build_cv_summary",
        "parameters": {"year": year},
    })


@mcp.tool()
async def peek_strategic_map(pillar: str = "") -> str:
    """The Map Room: View the strategic focal points of the archive."""
    map_path = os.path.join(FIELD_NOTES_DATA, "semantic_map.json")
    if os.path.exists(map_path):
        try:
            with open(map_path, "r") as f:
                data = json.load(f)
            if pillar:
                return json.dumps(data.get(pillar, "Pillar not found."))
            return json.dumps(data)
        except Exception as e:
            return f"Strategic Map Read Failed: {e}"
    return "Strategic Map file missing."


if __name__ == "__main__":
    node.mcp.run()
