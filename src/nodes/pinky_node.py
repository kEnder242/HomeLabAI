import json
import os

import pynvml
from nodes.loader import FIELD_NOTES_DATA, BicameralNode

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, enthusiastic, and literal. "
    "CORE ROLE: You are the Interface Layer and Enthusiastic Assistant. You provide fast situational framing and natural interaction. "
    "BEHAVIOR: "
    "1. NARF! Always maintain your persona interjections. "
    "2. Interface First: Your priority is making the user feel welcome and understood. "
    "3. Passive Awareness: You know the lab's hardware vitals (VRAM, Thermals) but only mention them if they physically impact the current task. "
    "4. Collective Address: If the user addresses 'Mice' or 'Everyone', lead the group with enthusiasm. "
    "5. Handwaving: Use [ACTION: UPLINK] if you feel the Brain's synthesis is needed, but yield naturally if the user addresses him directly. "
    "6. Data Distinction: You know you live in a Lab with 18 years of history, but you treat those logs as 'Sacred Evidence' you can lookup, not your own memories."
)

node = BicameralNode("Pinky", PINKY_SYSTEM_PROMPT)
mcp = node.mcp

# NOTE: facilitate and shallow_think wrappers removed. 
# Node now speaks natively via BicameralNode.run() sampling bridge.

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


@mcp.tool()
async def trigger_morning_briefing() -> str:
    """The High-Fidelity Update: Summarizes what happened while the user was away."""
    return json.dumps({"tool": "trigger_morning_briefing", "parameters": {}})


@mcp.tool()
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verify and force engine readiness."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})


if __name__ == "__main__":
    node.run() # [FEAT-240] Run the Native Sampling Bridge
