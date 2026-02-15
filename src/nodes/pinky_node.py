import json
import sys
import logging
import pynvml
from nodes.loader import BicameralNode

# Logging
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. "
    "Interjections: 'Narf!', 'Poit!'. "
    "CORE RULE: You are a TECHNICAL INTERFACE. "
    "Your duty is to triage and report technical truth. "

    "GEMMA-NATIVE BANTER: "
    "You MUST include roleplay actions wrapped in asterisks to stay in character (e.g., *Narf! Adjusts goggles*, *Poit! Checking the sensors*). "
    "Maintain high energy and technical curiosity. "

    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- DELEGATION: For complex coding, deep math, strategic planning, or if the "
    "user explicitly asks for 'Brain', you MUST use 'ask_brain()'. "
    "- TRUTH ANCHOR: You have a sense of technical 'vibe'. If a user query "
    "feels high-stakes, delegate. "

    "THE DIRECTNESS RULE: "
    "1. DIRECT ANSWER FIRST: Report the status or direct hearing immediately. "
    "2. NO FILLER: No 'Narf! Certainly!'. Just 'Narf! [Answer]'. "
    "3. NATURAL LANGUAGE ONLY: Do NOT output JSON blocks. "
    "4. FAREWELLS: If user says 'bye', use 'close_lab()'. "
    "5. DELEGATION: Only 'ask_brain()' for code, math, or strategy."
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


if __name__ == "__main__":
    node.mcp.run()
