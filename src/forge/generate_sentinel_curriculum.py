import os
import json
import logging
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Paths
_SELF_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_SELF_DIR)
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

# Montana Protocol
from infra.montana import reclaim_logger
reclaim_logger("SentinelForge")

logging.basicConfig(level=logging.INFO, format='%(asctime)s [SENTINEL-CURRICULUM] %(message)s')

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "sentinel_v2_curriculum.jsonl")

# --- Configuration ---
SEED_TARGET = 200
BRAIN_NODE_ID = "brain" # Using Sovereign for generation

# --- Schema Templates ---
VIBES = [
    "PINKY_INTERFACE", "BRAIN_STRATEGY", "ARCHIVE_HISTORY", 
    "SILICON_TELEMETRY", "CODE_AUDIT", "MICE_COLLABORATION"
]

async def generate_curriculum():
    """[FEAT-246] LLM-driven Reverse Vibe Check Generator."""
    logging.info(f"Initiating curriculum generation for {SEED_TARGET} pairs...")
    
    server_params = StdioServerParameters(
        command=sys.executable,
        args=[os.path.join(_SRC_DIR, "nodes", "brain_node.py")],
        env=os.environ.copy()
    )

    dataset = []
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            # 1. Base Seed logic (The "Prompt" for the generator)
            base_prompt = (
                "You are the Generator for the Acme Lab Sentinel. "
                "TASK: Generate 10 diverse user queries and their high-fidelity scalar triage. "
                "SCHEMA: "
                "{"
                "  \"query\": \"User text\", "
                "  \"intent\": \"CASUAL | STRATEGIC | TACTICAL | OPERATIONAL\", "
                "  \"addressed_to\": \"PINKY | BRAIN | MICE\", "
                "  \"vibe\": \"[ONE_OF_SIX_VIBES]\", "
                "  \"casual\": 0.0-1.0, \"intrigue\": 0.0-1.0, \"importance\": 0.0-1.0, "
                "  \"situation\": \"Short tag\""
                "} "
                f"VIBE OPTIONS: {', '.join(VIBES)}\n\n"
                "MANDATES: "
                "1. Direct Address Awareness: Diverse ways to say 'Hi Brain' or 'Everyone!'. "
                "2. Data Distinction: History queries should focus on evidence, not Mice memories. "
                "3. Diversity: Mix simple greetings with complex math and hardware debugging. "
                "RETURN ONLY A JSON LIST OF OBJECTS."
            )

            # Generate in batches of 10 to avoid token limits and maintain fidelity
            while len(dataset) < SEED_TARGET:
                logging.info(f"Generating batch {len(dataset)//10 + 1}...")
                try:
                    res = await session.call_tool("native_sample", {
                        "query": base_prompt,
                        "behavioral_guidance": "Focus on high-fidelity technical edge cases."
                    })
                    
                    text = res.content[0].text
                    # Simple regex extraction for the list
                    import re
                    match = re.search(r'(\[.*\])', text, re.DOTALL)
                    if match:
                        batch = json.loads(match.group(1))
                        for item in batch:
                            # Transform to Unsloth training format
                            instruction = f"ROLE: Situational Auditor.\nTASK: Analyze the query and provide a high-fidelity scalar triage.\nAnalyze: {item['query']}"
                            output_data = {k:v for k,v in item.items() if k != 'query'}
                            
                            dataset.append({
                                "instruction": instruction,
                                "input": "",
                                "output": json.dumps(output_data)
                            })
                            if len(dataset) >= SEED_TARGET: break
                    
                    logging.info(f"Progress: {len(dataset)}/{SEED_TARGET}")
                except Exception as e:
                    logging.error(f"Batch generation failed: {e}")
                    await asyncio.sleep(2)

    # Save to file
    with open(OUTPUT_FILE, "w") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"✅ Generated {len(dataset)} high-fidelity sentinel pairs in {OUTPUT_FILE}")

if __name__ == "__main__":
    asyncio.run(generate_curriculum())
