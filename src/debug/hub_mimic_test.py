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

async def run_hub_mimic_test():
    print("--- 🩺 HUB MIMIC TRIAGE TEST ---")
    
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
    
    query = "[ME] Status of the lab?"
    
    # Mimic _process_node_stream logic
    print(f"[2] Calling 'think' tool (internal=True)...")
    
    # Since we can't easily run the full MCP server + client in this script without complex setup,
    # we will just call the tool method directly if we can find it.
    
    # The 'think' tool is registered via @self.mcp.tool()
    # Let's find it in node.mcp._tools
    think_tool = node.mcp._tools["think"]
    
    # Call it
    full_response = await think_tool.func(
        query=query, 
        context="[RTX 2080 Ti]: ONLINE",
        tools=[],
        behavioral_guidance="You are a triage sentinel.",
        internal=True,
        response_format=triage_schema
    )
    
    print("\n--- [TOOL RESPONSE] ---")
    print(full_response)
    
    try:
        data = json.loads(full_response)
        print("\n✅ VALID JSON")
    except Exception as e:
        print(f"\n❌ INVALID JSON: {e}")

if __name__ == "__main__":
    asyncio.run(run_hub_mimic_test())
