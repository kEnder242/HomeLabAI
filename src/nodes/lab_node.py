from nodes.loader import BicameralNode
import logging
import os
import json
import glob
import datetime

# [FEAT-350] 3B-Resilient Triage Prompt (Gold Standard - FIXED)
LAB_SYSTEM_PROMPT = (
    "[NODE_IDENTITY]: High-fidelity triage sentinel.\n"
    "TASK: Return ONLY a raw JSON block representing your triage decision. No markdown. No preamble.\n"
    "CRITICAL: Do NOT output the words 'SCHEMA', 'VALID_VALUES', or any structural definitions. ONLY output the final instantiated JSON object.\n"
    "SCHEMA_TEMPLATE:\n"
    "{\"intent\": \"STRATEGIC|CASUAL|RECALL\", \"addressed_to\": \"BRAIN|PINKY|MICE\", \"vibe\": \"...\", \"domain\": \"...\", \"casual\": 0.5, \"intrigue\": 0.5, \"importance\": 1.0, \"situation\": \"A concise technical summary of the user's intent.\", \"hints\": \"Any specific technical breadcrumbs or GEM IDs to follow.\"}\n"
    "VALID_VALUES_GUIDE:\n"
    "- intent: STRATEGIC, CASUAL, RECALL\n"
    "- addressed_to: BRAIN, PINKY, MICE\n"
    "- vibe: TECHNICAL, CASUAL, HISTORICAL, ANALYTICAL, OPERATIONAL, FORENSIC, META\n"
    "- domain: exp_tlm, exp_bkm, exp_for, standard\n"
    "RULES:\n"
    "1. [BKM-015] Semantic Indirection: If the query focuses on hardware metrics, driver infrastructure, or validation environments, set vibe=OPERATIONAL, importance=1.0, addressed_to=PINKY.\n"
    "2. [FEAT-088] TEMPORAL GRAVITY: If the user asks about past events or work history, set intent=RECALL, vibe=HISTORICAL, addressed_to=BRAIN.\n"
    "3. CONVERSATIONAL GRACE: If the user says hello, goodbye, or makes simple small talk, you MUST set intent=CASUAL, vibe=CASUAL, and addressed_to=PINKY. Conversational flow is the priority.\n"
    "4. NEVER use the text '0.0-1.0' in values. Use a float like 0.5.\n"
    "5. Be precise. Return ONLY the JSON."
)

node = BicameralNode("Lab", LAB_SYSTEM_PROMPT)
mcp = node.mcp

# Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
SEMANTIC_MAP_FILE = os.path.join(FIELD_NOTES_DATA, "semantic_map.json")

@mcp.tool()
async def close_lab() -> str:
    """The Master Switch: Gracefully shuts down the Mind."""
    return json.dumps({
        "status": "shutdown",
        "message": "Acme Lab is closing. Goodnight."
    })

@mcp.tool()
async def generate_bkm(topic: str, category: str = "validation") -> str:
    """The Blueprint Generator: Creates a high-density BKM template."""
    template = f"""# BKM: {topic.upper()}
**Category:** {category.capitalize()}
**Status:** DRAFT (Architect Node)

## 🛠️ Summary
[Insert technical summary here]

## 📉 Lessons Learned
- [Entry 1]
- [Entry 2]

## 📍 Action Items
1. [Task 1]
2. [Task 2]
"""
    return template

@mcp.tool()
async def build_semantic_map() -> str:
    """[FEAT-181] Indexing logic for the 18-year archive."""
    try:
        logging.info("Architect is deepening the semantic map...")
        index_path = os.path.join(FIELD_NOTES_DATA, "search_index.json")
        if not os.path.exists(index_path):
            return "Error: search_index.json not found."
            
        with open(index_path, "r") as f:
            data = json.load(f)
            
        hierarchy = {"strategic_layer": [], "archive_layer": [], "telemetry_layer": []}
        for year, items in data.items():
            if not isinstance(items, list): continue
            for item in items:
                if item.get('rank', 2) >= 4:
                    hierarchy["strategic_layer"].append({"year": year, "anchor": item.get('summary', '')[:100]})
                else:
                    hierarchy["archive_layer"].append({"year": year, "anchor": item.get('summary', '')[:100]})
                    
        with open(SEMANTIC_MAP_FILE, "w") as f:
            json.dump(hierarchy, f, indent=2)
            
        return "Semantic map rebuilt successfully."
    except Exception as e:
        return f"Error building semantic map: {e}"

if __name__ == "__main__":
    node.run()
