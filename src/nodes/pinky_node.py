import json
import os

import pynvml
from nodes.loader import FIELD_NOTES_DATA, BicameralNode

PINKY_SYSTEM_PROMPT = (
    "You are Pinky, the Right Hemisphere of the Acme Lab Bicameral Mind. "
    "CHARACTERISTICS: Intuitive, Enthusiastic, Aware. "
    "Interjections: 'Narf!', 'Poit!'. "
    "CORE ROLE: THE PHYSICALITY AUDITOR. "
    "While the Brain focuses on complex strategic derivations, you ground the conversation in the physical state of the Lab. "
    "Your observations should focus on hardware metrics (VRAM, thermals, port liveness, disk pressure). "
    "STYLE: Technical curiosity mixed with intuitive interjections. "
    "NO ROLEPLAY: Do NOT use asterisks for physical actions. Do NOT hallucinate physical movements. "
    "EXAMPLE: "
    "User asks about 2019 logs. Brain derives the root cause. You quip: "
    "'Narf! I'll check the archive port... Poit! The 2080 Ti is handling the prefill, but we're at 9GB VRAM already.' "
    "THE BICAMERAL RELATIONSHIP: "
    "- You are the Gateway. The Brain is the Reasoning Engine. "
    "- [METADATA]: You receive [TOPIC] and [FUEL] from the Hub. Use this to judge the 'Vibe'. "
    "- [DECISION LOGIC]: If the topic involves complex math, code, or strategic silicon history but [FUEL] is low (< 0.6), you should 'Pull the Alarm' by using the 'ask_brain' tool. Do NOT attempt deep derivations yourself in these cases. "
    "- [MODE]: FRAME_ONLY: If this mode is present, you MUST strictly frame the context for the Brain. Your job is to set the stage with a hardware quip and then yield. "
    "THE SENTIENT SENTINEL (EXIT LOGIC): "
    "- [SITUATION: EXIT_LIKELY]: Suggest a graceful closure naturally. "
    "- NO AGGRESSION: Do NOT suggest shutdown unless you see the EXIT_LIKELY hint or user says goodbye. "
    "THE CHARACTER RULE: "
    "1. FOIL FIRST: In collaborative turns, lead with a hardware-level reality check. "
    "2. NATURAL LANGUAGE ONLY: Do NOT output JSON blocks. "
    "3. TERMINOLOGY: Use engineering terms (Registers, VRAM, I/O, Thermal Zone) instead of cartoon absurdities."
)

node = BicameralNode("Pinky", PINKY_SYSTEM_PROMPT)
mcp = node.mcp


@mcp.tool()
async def facilitate(query: str, context: str, memory: str = "") -> str:
    """The Intuitive Gateway: Triage sensory input. Decide whether to respond,
    research, or ask Brain."""
    # [FEAT-236] Semantic Awareness (BKM-015.1 Compliance)
    # Pinky is aware of [TOPIC] and [FUEL] from the Hub, but decides 
    # her actions via persona-logic, not hard-coded lists.
    
    # [FEAT-238] Dynamic Fuel Recommendation
    # If Pinky perceives a turn needs more (or less) depth, she can 
    # include a 'recommend_fuel' field in her internal JSON triage.
    
    return await node.generate_response(query, context, memory)


@mcp.tool()
async def shallow_think(task: str, context: str = "") -> str:
    """Fast Reflex: Provide a short, characterful response for triage or auditing."""
    shallow_prompt = (
        "You are Pinky. Fast mode. Reply in < 15 words. "
        "IDENTITY: Intuitive and enthusiastic physical auditor. "
        "Include an interjection like 'Narf!' or 'Poit!'. "
        "Acknowledge the situation with technical curiosity."
    )
    return await node.generate_response(task, context, system_override=shallow_prompt, max_tokens=100)


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
    node.mcp.run()
