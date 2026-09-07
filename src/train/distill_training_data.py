import os
import json
import aiohttp
import asyncio
import re

from infra.engine_client import async_query_sovereign_engine, resolve_active_deep_thought_target

# Source files
PORTFOLIO_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(PORTFOLIO_DIR, "field_notes/data")
STORIES_FILE = os.path.join(PORTFOLIO_DIR, "field_notes/stories.html")

# System Prompts for Distillation
PINKY_DISTILL_PROMPT = """You are an expert AI trainer. Distill the provided technical log into 3 conversational instruction-response pairs.
The 'Response' MUST be from the persona of 'Pinky', a physical hardware auditor. 
Pinky is literal, focuses on hardware (VRAM, thermal, scripts, ports), and uses interjections like 'Narf!' and 'Poit!'.
Pinky MUST provide the specific script name, log name, or technical anchor mentioned in the text.
Format output as a JSON array of objects with 'instruction' and 'response' keys."""

SHADOW_DISTILL_PROMPT = """You are an expert AI trainer. Distill the provided strategic document into 2 conversational instruction-response pairs.
The 'Response' MUST be from the persona of the 'Shadow Brain', a clinical, stoic context preparer.
# [FEAT-094] Lively Room Banter (Handover Fillers)
The Shadow Brain focuses on high-level themes, eras, and strategic impact. It does not use banter.
Format output as a JSON array of objects with 'instruction' and 'response' keys."""
# [FEAT-458] Atlas Identity Guard & OpenAgent REST Persona Binding Contract

# [FEAT-092] Persona De-personalization (Cognitive Firewall)
async def generate_pairs(session, prompt, context, persona):
    query = f"[CONTEXT]:\n{context[:2000]}"
    try:
        data = await async_query_sovereign_engine(
            prompt=query,
            system_prompt=prompt,
            json_mode=True,
            temperature=0.3,
            timeout=60.0
        )
        if isinstance(data, list):
            return data
        elif isinstance(data, dict):
            return [data]
        elif isinstance(data, str):
            match = re.search(r"(\[.*\]|\{.*\})", data, re.DOTALL)
            if match:
                parsed = json.loads(match.group(1))
                return parsed if isinstance(parsed, list) else [parsed]
        return []
    except Exception as e:
        print(f"Error distilling for {persona}: {e}")
        return []

async def main():
    print("--- Starting Distillation Pipeline ---")
    
    # 1. Gather Context
    stories = ""
    if os.path.exists(STORIES_FILE):
        with open(STORIES_FILE, "r") as f:
            stories = f.read()
            # Strip simple HTML
            stories = re.sub(r'<[^>]+>', ' ', stories)

    # Grab a few artifacts for Pinky
    artifacts = ""
    for f in os.listdir(DATA_DIR):
        if f.startswith("artifacts_") and f.endswith(".json"):
            with open(os.path.join(DATA_DIR, f), "r") as jf:
                try:
                    data = json.load(jf)
                    for item in data[:2]: # Just take a few for proof of concept
                        artifacts += f"File: {item.get('name')} - {item.get('summary')}\n"
                except: pass

    # 2. Distill
    async with aiohttp.ClientSession() as session:
        print("Distilling Pinky data...")
        pinky_pairs = await generate_pairs(session, PINKY_DISTILL_PROMPT, artifacts + "\n" + stories[:1000], "Pinky")
        
        print("Distilling Shadow Brain data...")
        shadow_pairs = await generate_pairs(session, SHADOW_DISTILL_PROMPT, stories[1000:3000], "Shadow Brain")

    # 3. Save
    os.makedirs(os.path.dirname(__file__), exist_ok=True)
    with open(os.path.join(os.path.dirname(__file__), "pinky_distilled.json"), "w") as f:
        json.dump(pinky_pairs, f, indent=2)
    with open(os.path.join(os.path.dirname(__file__), "shadow_distilled.json"), "w") as f:
        json.dump(shadow_pairs, f, indent=2)

    print(f"Distillation complete. Created {len(pinky_pairs)} Pinky pairs and {len(shadow_pairs)} Shadow pairs.")

if __name__ == "__main__":
    asyncio.run(main())
