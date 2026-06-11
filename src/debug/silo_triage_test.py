import asyncio
import os
import sys
import json
import logging

# Setup paths for imports
SRC_DIR = os.path.join(os.getcwd(), "HomeLabAI/src")
sys.path.append(SRC_DIR)

from nodes.loader import BicameralNode
from nodes.lab_node import LAB_SYSTEM_PROMPT

async def run_silo_test():
    print("--- 🩺 SILO TRIAGE TEST ---")
    
    # 1. Initialize Lab Node
    print("[1] Initializing Lab Node...")
    node = BicameralNode("Lab", LAB_SYSTEM_PROMPT)
    
    # 2. Define Triage Schema
    triage_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "triage_result",
            "schema": {
                "type": "object",
                "properties": {
                    "intent": {"type": "string", "enum": ["STRATEGIC", "CASUAL", "RECALL"]},
                    "addressed_to": {"type": "string", "enum": ["BRAIN", "PINKY", "MICE"]},
                    "vibe": {"type": "string", "enum": ["SILICON_TELEMETRY", "ARCHIVE_HISTORY", "PINKY_INTERFACE"]},
                    "domain": {"type": "string", "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard"]},
                    "casual": {"type": "number"},
                    "intrigue": {"type": "number"},
                    "importance": {"type": "number"},
                    "situation": {"type": "string"},
                    "hints": {"type": "string"}
                },
                "required": ["intent", "addressed_to", "vibe", "domain"]
            }
        }
    }
    
    # 3. Test Query
    query = "[ME] What is the current VRAM status of the RTX 2080 Ti?"
    print(f"[2] Query: {query}")
    
    # 4. Generate Response
    print("[3] Generating with Guided Decoding...")
    full_text = ""
    async for token in node.generate_response(
        query=query,
        context="[RTX 2080 Ti]: 11GB VRAM, 2.2GB used.",
        temperature=0.0,
        response_format=triage_schema
    ):
        print(token, end="", flush=True)
        full_text += token
    
    print("\n\n--- [FINAL OUTPUT] ---")
    print(full_text)
    
    # 5. Validation
    try:
        data = json.loads(full_text)
        print("\n✅ VALID JSON DETECTED")
        print(json.dumps(data, indent=2))
    except Exception as e:
        print(f"\n❌ INVALID JSON: {e}")

if __name__ == "__main__":
    asyncio.run(run_silo_test())
