import os
import json
import aiohttp
import asyncio
import re

KENDER_URL = "http://192.168.1.26:11434/api/generate"
MODEL = "llama3.1:8b" # Or whichever model is loaded

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
The Shadow Brain focuses on high-level themes, eras, and strategic impact. It does not use banter.
Format output as a JSON array of objects with 'instruction' and 'response' keys."""

async def generate_pairs(session, prompt, context, persona):
    payload = {
        "model": MODEL,
        "prompt": f"{prompt}\n\n[CONTEXT]:\n{context[:2000]}", # Limit context to avoid timeout
        "stream": False,
        "options": {"temperature": 0.3}
    }
    try:
        async with session.post(KENDER_URL, json=payload, timeout=60) as resp:
            data = await resp.json()
            raw_text = data.get("response", "")
            # Try to parse JSON from the response
            match = re.search(r"(\[.*\])", raw_text, re.DOTALL)
            if match:
                return json.loads(match.group(1))
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
