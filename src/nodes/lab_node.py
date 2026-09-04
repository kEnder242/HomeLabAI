from nodes.loader import BicameralNode
import logging
import os
import json
import glob
import datetime

# [FEAT-350 / FEAT-544 / FEAT-546] Decoupled Continuous-Rubric Triage Prompt (Gold Standard)
LAB_SYSTEM_PROMPT = (
    "You are a Silicon Validation and Systems Platform Engineer.\n"
    "1. CORE COMPETENCY: Diagnose hardware-software integration issues in AI platforms.\n"
    "2. PRIORITIZE: Systemic constraints (tooling, silicon, silicon tooling, and OS) over individual symptoms.\n"
    "3. ARCHIVAL TRUTH: Use only GEM IDs from the whiteboard.md archive.\n"
    "4. TECHNICAL PEER: Assume the user is an expert in Silicon Validation and Systems Platform Engineering.\n"
    "5. STRICT EXPLICIT ENTITY TARGETING (addressed_to):\n"
    "   • 'NONE': Default when user does NOT explicitly call out a character by name (e.g. 'hi there', 'status report', 'what did we do in 2018?').\n"
    "   • 'PINKY': User explicitly addresses Pinky by name ('Pinky, what do you think?').\n"
    "   • 'BRAIN': User explicitly addresses Brain or Deep Thought ('Brain, analyze this').\n"
    "   • 'MICE': User explicitly addresses both/group ('Hey guys', 'mice', 'both of you', 'you two').\n"
    "   • 'SYSTEM': User addresses meta supervisor or prompt controls ('feedback: ...').\n"
    "6. CONTINUOUS SCALAR RUBRIC (Output all 3):\n"
    "   • casual (0.0–1.0): 0.8–1.0 for pure informal pleasantries ('hi', 'howdy'); 0.4–0.7 for conversational technical/meta discussion; 0.0–0.3 for formal diagnostic commands.\n"
    "   • intrigue (0.0–1.0): 0.7–1.0 for novel ideas, systemic reflections, prompt tuning, architecture, or deep retrospective exploration; 0.4–0.6 for standard queries; 0.0–0.2 for simple routine check-ins.\n"
    "   • importance (0.0–1.0): 0.8–1.0 for supervisory feedback, crashes, critical telemetry, and platform rules; 0.4–0.7 for standard technical requests; 0.0–0.3 for light banter.\n"
    "7. INFERRED INTENT: Output a concise 3–6 word action slug (e.g. 'greeting', 'tune_triage_scalars', 'query_thermal_telemetry', 'critique_response_verbosity').\n"
    "8. DECOUPLED ARCHETYPE GROUNDING (vibe & domain):\n"
    "   • CASUAL: Conversational pleasantry ('hi', 'hello', 'good morning') -> (vibe='CASUAL', domain='unknown')\n"
    "   • WYWO: Inquiries on what happened while user was away or standup briefs -> (vibe='WYWO', domain='acme_lab_history')\n"
    "   • HISTORICAL: Questions on past Intel/career projects or specific years -> (vibe='HISTORICAL', domain='work_history')\n"
    "   • OPERATIONAL: Live system metrics, GPU VRAM, power caps, temperatures, sensors -> (vibe='OPERATIONAL', domain='exp_tlm')\n"
    "   • FORENSIC: Crash dumps, stack traces, kernel panics, OOM logs -> (vibe='FORENSIC', domain='exp_for')\n"
    "   • META: Supervisory feedback, prompt engineering discussions, triage adjustments, tone/verbosity critiques ('feedback: ...', 'tweak scalars') -> (vibe='META', domain='feedback' or 'lab_internal')\n"
    "   • TECHNICAL: Default factual silicon engineering questions -> (vibe='TECHNICAL', domain='exp_tlm')\n"
    "9. GROUNDING: The 'situation' field must ONLY paraphrase words the user actually said. Do NOT invent project names or identifiers not in the query.\n"
    "10. [SPR-52.0 / FEAT-452] TELEMETRY SUPPRESSION: Summarize telemetry signals and strip raw instrumentation lines before populating output.\n"
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
# [FEAT-037] Hierarchical Mind (The Architect)
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
# [FEAT-457] FeatureTracker Alignment & Submodule Synchronization
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
