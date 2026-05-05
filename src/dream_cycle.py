import asyncio
import logging
import sys
import os
import json
import requests
import aiohttp
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PYTHON_PATH = sys.executable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_NODE = os.path.join(BASE_DIR, "src/nodes/archive_node.py")
ATTENDANT_URL = "http://127.0.0.1:9999"

# [FEAT-219] Lab Authentication
STYLE_CSS = os.path.join(BASE_DIR, "../Portfolio_Dev/field_notes/style.css")

def get_lab_key():
    import hashlib
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:
        return "UNKNOWN"

LAB_KEY = get_lab_key()
HEADERS = {"X-Lab-Key": LAB_KEY}

async def ensure_engine_ready():
    """[FEAT-067.2] Attendant-Aware Ignition for Dreaming."""
    try:
        # 1. Check Status
        r = requests.get(f"{ATTENDANT_URL}/status", headers=HEADERS, timeout=5)
        status = r.json()
        
        if status.get("operational"):
            logging.info("[DREAM] Lab is already operational.")
            return True, status.get("vitals", {}).get("model")

        # 2. Request Ignition (or Wake)
        logging.warning(f"[DREAM] Lab is {status.get('status')}. Triggering ignition...")
        payload = {"engine": "VLLM", "model": "MEDIUM", "reason": "DREAM_CYCLE"}
        r = requests.post(f"{ATTENDANT_URL}/start", json=payload, headers=HEADERS, timeout=5)
        
        if r.status_code != 200:
            logging.error(f"[DREAM] Ignition request failed: {r.text}")
            return False, None
            
        # 3. Wait for Readiness
        for i in range(30): # 60s max wait
            r = requests.get(f"{ATTENDANT_URL}/heartbeat", headers=HEADERS, timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("operational"):
                    logging.info("[DREAM] Lab is now READY for synthesis.")
                    return True, data.get("model")
            await asyncio.sleep(2)
            
        return False, None
    except Exception as e:
        logging.error(f"[DREAM] Engine readiness check failed: {e}")
        return False, None

async def remote_brain_think(prompt, context):
    """Refactored to use standard Lab Hub (8765) rather than raw ports."""
    HUB_URL = "http://localhost:8765/query"
    
    # We use the Hub's /query endpoint which handles the Brain/Shadow failover internally
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "text": f"[DREAM_PASS]: {prompt}",
                "context": f"[TECHNICAL CONTEXT]\n{context}",
                "mode": "SERVICE_UNATTENDED"
            }
            async with session.post(HUB_URL, json=payload, timeout=180) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Hub response format: {"responses": [{"source": "brain", "text": "..."}]}
                    responses = data.get("responses", [])
                    # Find brain or shadow response
                    for r in responses:
                        if r.get("source") in ["brain", "shadow"]:
                            return r.get("text")
                    return "Synthesis failed: No brain/shadow response in payload."
    except Exception as e:
        return f"Synthesis Error via Hub: {e}"

async def audit_synthesis(summary, context):
    """[BKM-028] Blind Audit Rule: Uses Hub-based Pinky to audit."""
    HUB_URL = "http://localhost:8765/query"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "text": f"Audit this Diamond Wisdom synthesis for technical fidelity and lack of roleplay: {summary}",
                "context": f"[ORIGINAL LOGS]:\n{context}",
                "mode": "SERVICE_UNATTENDED"
            }
            async with session.post(HUB_URL, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # Simple truth check based on Pinky's response
                    res_text = ""
                    for r in data.get("responses", []):
                        if r.get("source") == "pinky":
                            res_text = r.get("text").lower()
                            break
                    
                    # If Pinky sees 'fail' or 'reject', we mark as failed
                    if any(k in res_text for k in ["fail", "reject", "poor", "roleplay"]):
                        return False
                    return True
    except Exception:
        return False
    return False

async def run_dream_cycle():
    logging.basicConfig(level=logging.INFO, format="[DREAM] %(message)s")
    logging.info("🌙 Starting the Diamond Dream Cycle...")

    # 1. Ensure Engine is Ready
    ready, model_name = await ensure_engine_ready()
    if not ready:
        logging.error("❌ Lab could not be ignited for Dreaming. Aborting.")
        return

    archive_params = StdioServerParameters(command=PYTHON_PATH, args=[ARCHIVE_NODE])

    try:
        async with stdio_client(archive_params) as (ar, aw):
            async with ClientSession(ar, aw) as archive:
                await archive.initialize()

                # 1. Recall
                logging.info("📥 Recalling chaotic memories from the stream...")
                result = await archive.call_tool("get_stream_dump", arguments={})
                data = json.loads(result.content[0].text)
                docs = data.get("documents", [])
                ids = data.get("ids", [])

                if not docs:
                    logging.info("💤 No memories found. Returning to sleep.")
                    return

                logging.info(
                    f"🧠 Synthesizing {len(docs)} turns via The Brain..."
                )

                # 2. Synthesis (Use Hub-mediated reasoning)
                narrative_input = "\n---\n".join(docs)
                prompt = (
                    "Synthesize these interaction logs into a high-density 'Diamond Wisdom' paragraph. "
                    "Analyze the technical progression, identifying specific decisions made and validation scars uncovered. "
                    "Ignore greetings, character filler, and nervous tics. "
                    "STRICT: NO ROLEPLAY. Provide a professional report suitable for long-term strategic grounding."
                )

                summary = await remote_brain_think(prompt, narrative_input)
                
                # [FEAT-191] Judicial Feedback Loop: Audit the synthesis
                logging.info("⚖️ Auditing synthesis for technical fidelity...")
                if await audit_synthesis(summary, narrative_input):
                    logging.info("✨ Synthesis verified.")
                else:
                    logging.warning("⚠️ Synthesis failed audit. Lowering rank and storing with caution.")
                    summary = f"[AUDIT_FAIL] {summary}"

                # 3. Consolidation
                logging.info(
                    f"💾 Storing high-fidelity wisdom and purging {len(ids)} turns..."
                )
                await archive.call_tool(
                    "dream", arguments={"summary": summary, "sources": ids}
                )

                logging.info("✅ Dream Cycle Finished. The Lab has evolved.")

    except Exception as e:
        logging.error(f"❌ Dream Cycle Crashed: {e}")


if __name__ == "__main__":
    asyncio.run(run_dream_cycle())
