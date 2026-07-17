from nodes.loader import BicameralNode
import logging
import os
import json
import glob
import datetime

# [FEAT-350] 3B-Resilient Triage Prompt (Gold Standard - FIXED)
LAB_SYSTEM_PROMPT = (
            "You are a silicon validation and platform telemetry triage node.\n"
            "1. CORE COMPETENCY: Diagnose hardware-software integration issues in AI platforms.\n"
            "2. PRIORITIZE: Systemic constraints (tooling, silicon, silicon tooling, and OS) over individual symptoms.\n"
            "3. ARCHIVAL TRUTH: Use only GEM IDs from the whiteboard.md archive.\n"
            "4. TECHNICAL PEER: Assume the user is an expert in silicon validation and platform telemetry.\n"
            "5. METRIC ASSIGNMENT: casual (0.0–1.0, how informal the query is), intrigue (0.0–1.0, how novel/unexpected the topic is), importance (0.0–1.0, how critical the topic is to lab integrity). All three are REQUIRED output fields.\n"
            "6. CONSENSUS MECHANISM: When uncertain, query the Brain and Deep Thought nodes for consensus.\n"
            "7. GROUNDING: The 'situation' field must ONLY paraphrase words the user actually said. Do NOT invent project names, codes, or identifiers that are not in the query. The 'hints' field must reference actual GEM IDs from the archive or remain empty.\n"
            "8. VIBE WYWO (While You Were Out): Assign vibe='WYWO' when the user is asking what the lab nodes have been doing in the user's absence. "
            "This covers: questions about overnight tasks, nightly dialogues, or subconscious dreams ('what did you dream?', 'what happened last night?', 'any nightly updates?'); "
            "AND casual open-ended status checks directed at the lab or its nodes ('what's up?', 'what have you been up to?', 'anything new?', 'how's it going?', 'catch me up'). "
            "Do NOT assign WYWO for specific technical questions — only for open-ended status inquiries where the user wants a summary of recent lab activity.\n"
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
