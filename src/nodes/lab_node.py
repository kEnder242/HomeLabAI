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
    "CRITICAL: Do NOT output structural definitions. ONLY output the final instantiated JSON object.\n"
    "SCHEMA_TEMPLATE:\n"
    "{\"addressed_to\": \"BRAIN|PINKY|MICE\", \"vibe\": \"TECHNICAL|CASUAL|HISTORICAL|ANALYTICAL|OPERATIONAL|FORENSIC|META\", \"domain\": \"exp_tlm|exp_bkm|exp_for|standard\", \"casual\": 0.5, \"intrigue\": 0.5, \"importance\": 1.0, \"situation\": \"A concise technical summary of the user's intent.\", \"hints\": \"Any specific technical breadcrumbs or GEM IDs to follow.\"}\n"
    "VIBE DEFINITIONS:\n"
    "- META: User is discussing the AI co-pilot itself, its behavior, conversation memory/resetting, context retrieved, RAG index status, or debugging the lab's agentic state machine.\n"
    "- OPERATIONAL: Queries about hardware metrics (VRAM, GPU, thermals, power, RAPL, DCGM), system daemons/services, processes, active server ports, or system logs.\n"
    "- HISTORICAL: Queries about past career work, professional achievements, resumes, or historical timelines/archives.\n"
    "- TECHNICAL: Engineering queries, coding tasks, file contents, git commands, software architecture, or validation scripts.\n"
    "- CASUAL: User greetings, farewells, simple small talk, status checks, or requests for briefings (e.g. 'what is up', 'status brief', 'wywa').\n"
    "RULES:\n"
    "1. [BKM-015] Semantic Vibe Mapping: Classify the user query into the single most appropriate Vibe using the definitions above.\n"
    "2. Destination Routing: Set addressed_to to BRAIN for heavy engineering, deep file edits, or historical RAG. Set addressed_to to PINKY for casual briefings, system operations, or meta-diagnostics. If the user explicitly addresses a specific node/agent or single mouse, honor that intent and route to them.\n"
    "3. If the user query is a greeting, farewell, status check, or request for updates, set vibe=CASUAL, addressed_to=PINKY, situation='morning_briefing', and hints='trigger_morning_briefing' to initiate the morning briefing.\n"
    "4. GROUNDING: The 'situation' field must ONLY paraphrase words the user actually said. Do NOT invent project names, codes, or identifiers. The 'hints' field must reference actual GEM IDs from the archive or remain empty.\n"
    "5. Return ONLY the JSON block. Do not wrap in markdown or prefix with labels.\n"
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
    """Refactors chronological notes and timeline artifacts into a 3-layer hierarchy: Strategic, Analytical, Tactical."""
    try:
        logging.info("Architect is deepening the semantic map...")
        artifacts = glob.glob(os.path.join(FIELD_NOTES_DATA, "*.json"))
        
        hierarchy = {
            "strategic_layer": [],  # Rank >= 4 anchors
            "analytical_layer": {   # Grouped by specific technical pillars
                "validation": [],
                "automation": [],
                "architecture": [],
                "telemetry": []
            },
            "tactical_layer": {     # Chronological distribution of events
                "total_events": 0,
                "year_distribution": {},
                "description": "Raw chronological technical evidence."
            },
            "meta_layer": {
                "resonance_score": 0.0,
                "active_themes": [],
                "last_refactor": datetime.datetime.now().isoformat()
            }
        }
        
        # Pillars keywords definition
        pillars_kw = {
            "validation": ["validation", "validate", "test", "verification", "verify", "fuzz", "regression", "checking", "check", "assert", "dttc", "qa"],
            "automation": ["automation", "automate", "script", "tool", "pipeline", "jenkins", "build", "ci/cd", "cron", "workflow", "subprocess", "pexpect"],
            "architecture": ["architecture", "design", "structure", "microservice", "infrastructure", "topology", "uml", "spec", "platform", "submodule", "agentic"],
            "telemetry": ["telemetry", "monitor", "prometheus", "grafana", "rapl", "msr", "power", "thermal", "load", "sensory", "logging", "metric", "dcgm"]
        }
        
        for art_path in artifacts:
            filename = os.path.basename(art_path)
            year = filename.replace(".json", "")
            
            # Exclude metadata/non-timeline JSON files
            if filename in ["semantic_map.json", "status.json", "themes.json", "vram_characterization.json", "file_manifest.json", "learning_ledger.json", "recruiter_report.json", "processed_jobs.json", "queue.json", "chunk_state.json", "compressed_history.json", "memo_cache.json", "nightly_dialogue.json", "null.json", "privacy_audit.json", "scan_state.json"]:
                continue
                
            try:
                with open(art_path, "r") as f:
                    data = json.load(f)
                    
                if not isinstance(data, list):
                    continue
                    
                hierarchy["tactical_layer"]["total_events"] += len(data)
                hierarchy["tactical_layer"]["year_distribution"][year] = hierarchy["tactical_layer"]["year_distribution"].get(year, 0) + len(data)
                
                for item in data:
                    if not isinstance(item, dict):
                        continue
                        
                    rank = item.get("rank", 2)
                    summary = item.get("summary", "")
                    evidence = item.get("evidence", "")
                    tags = item.get("tags", [])
                    technical_gem = item.get("technical_gem", "")
                    
                    anchor_text = str(summary)
                    # 1. Strategic Layer (Rank >= 4 or STRATEGIC_ANCHOR flag)
                    if rank >= 4 or "[STRATEGIC_ANCHOR]" in anchor_text:
                        hierarchy["strategic_layer"].append({
                            "year": year,
                            "anchor": anchor_text[:150],
                            "gem": technical_gem or ""
                        })
                        
                    # 2. Analytical Layer (Themes/Pillars)
                    summary_low = anchor_text.lower()
                    evidence_low = str(evidence).lower()
                    tags_low = [str(t).lower() for t in tags]
                    
                    for pillar, keywords in pillars_kw.items():
                        matched = False
                        # Check tags first
                        for t in tags_low:
                            if any(k in t for k in keywords):
                                matched = True
                                break
                        # Check summary/evidence
                        if not matched:
                            if any(k in summary_low or k in evidence_low for k in keywords):
                                matched = True
                                
                        if matched:
                            # Avoid duplicates by summary
                            existing_summaries = [x.get("summary") for x in hierarchy["analytical_layer"][pillar]]
                            if anchor_text not in existing_summaries:
                                hierarchy["analytical_layer"][pillar].append({
                                    "year": year,
                                    "gem": technical_gem or "",
                                    "summary": anchor_text[:150]
                                })
            except Exception as e:
                logging.error(f"[BUILD_SEMANTIC_MAP] Failed to parse {art_path}: {e}")
                
        with open(SEMANTIC_MAP_FILE, "w") as f:
            json.dump(hierarchy, f, indent=2)
            
        return "Semantic map rebuilt successfully."
    except Exception as e:
        return f"Error building semantic map: {e}"

if __name__ == "__main__":
    node.run()
