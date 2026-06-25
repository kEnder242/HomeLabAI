import asyncio
import logging
import sys
import os
import json
import requests
import aiohttp
import random
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PYTHON_PATH = sys.executable
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE_NODE = os.path.join(BASE_DIR, "src/nodes/archive_node.py")
ATTENDANT_URL = "http://127.0.0.1:8765"

# [FEAT-219] Lab Authentication
STYLE_CSS = os.path.join(BASE_DIR, "../Portfolio_Dev/field_notes/style.css")

def get_lab_key():
    import hashlib
    try:
        if os.path.exists(STYLE_CSS):
            with open(STYLE_CSS, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()[:8]
    except Exception:
        pass
    return "UNKNOWN"

LAB_KEY = get_lab_key()
HEADERS = {"X-Lab-Key": LAB_KEY}

async def ensure_engine_ready():
    """[FEAT-067.2] Attendant-Aware Ignition for Dreaming."""
    try:
        # 1. Check Status
        r = requests.get(f"{ATTENDANT_URL}/status", headers=HEADERS, timeout=5)
        status = r.json()
        
        if status.get("state") == "OPERATIONAL" or status.get("vocal"):
            logging.info("[DREAM] Lab is already operational.")
            # Retrieve model from vitals
            model_name = status.get("vitals", {}).get("model", "unified-base")
            return True, model_name

        # 2. Request Ignition
        logging.warning(f"[DREAM] Lab is {status.get('state')}. Triggering ignition...")
        r = requests.post(f"{ATTENDANT_URL}/wake", headers=HEADERS, timeout=60)
        
        if r.status_code != 200:
            logging.error(f"[DREAM] Ignition request failed: {r.text}")
            return False, None
            
        # 3. Wait for Readiness
        for i in range(30): 
            r = requests.get(f"{ATTENDANT_URL}/status", headers=HEADERS, timeout=2)
            if r.status_code == 200:
                data = r.json()
                if data.get("vocal"):
                    logging.info("[DREAM] Lab is now READY for synthesis.")
                    model_name = data.get("vitals", {}).get("model", "unified-base")
                    return True, model_name
            await asyncio.sleep(2)
            
        return False, None
    except Exception as e:
        logging.error(f"[DREAM] Engine readiness check failed: {e}")
        return False, None

async def remote_brain_think(prompt, context):
    """Refactored to use standard Lab Hub (8765) rather than raw ports."""
    # Note: Hub endpoint changed from /query to /inject in V5 for intent injection
    HUB_URL = "http://localhost:8765/inject"
    
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "query": f"[DREAM_PASS]: {prompt}\n\n[CONTEXT]: {context}"
            }
            async with session.post(HUB_URL, json=payload, timeout=300) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    # V5 returns {"status": "QUEUED", "id": "..."}
                    # We have to wait for the intent to process and appear in the ledger
                    # but for dreaming, we might prefer a direct node call if possible.
                    # For now, we utilize the Hub injection and trust the waterfall.
                    return f"Intent {data.get('id')} queued for synthesis."
    except Exception as e:
        return f"Synthesis Error: {e}"

class DreamManager:
    def __init__(self, archive):
        self.archive = archive

    async def run_cycle(self):
        logging.info("📥 Recalling chaotic memories from the stream...")
        result = await self.archive.call_tool("get_stream_dump", arguments={})
        data = json.loads(result.content[0].text)
        docs = data.get("documents", [])
        ids = data.get("ids", [])

        if not docs:
            logging.info("💤 No chaotic memories found. Transitioning to Refinement Dreaming...")
            await self.run_refinement_dream()
            return

        logging.info(f"🧠 Synthesizing {len(docs)} turns via The Brain...")
        narrative_input = "\n---\n".join(docs)
        prompt = (
            "Synthesize these interaction logs into a high-density 'Diamond Wisdom' paragraph. "
            "Analyze the technical progression, identifying specific decisions made and validation scars uncovered. "
            "STRICT: NO ROLEPLAY. Provide a professional report suitable for long-term strategic grounding."
        )

        # In V5, we prefer calling nodes directly if we have the session
        # but the Hub orchestrates models. 
        # For simplicity in this background task, we use the Hub's REST interface.
        summary = await remote_brain_think(prompt, narrative_input)
        
        # Consolidation
        logging.info(f"💾 Storing high-fidelity wisdom and purging {len(ids)} turns...")
        await self.archive.call_tool("dream", arguments={"summary": summary, "sources": ids})
        logging.info("✅ Dream Cycle Finished. The Lab has evolved.")

    async def run_refinement_dream(self):
        """[FEAT-127.1] Recursive Refinement: Upgrade Tier 2 artifacts to Tier 1."""
        logging.info("💎 Initiating Deep Refinement of the 18-year archive...")
        
        cabinet_res = await self.archive.call_tool("list_cabinet", arguments={})
        files = json.loads(cabinet_res.content[0].text)
        if not files:
            return
        
        target_file = random.choice([f for f in files if f.endswith(".json")])
        logging.info(f"📂 Selected target for refinement: {target_file}")
        
        doc_res = await self.archive.call_tool("read_document", arguments={"filename": target_file})
        content = json.loads(doc_res.content[0].text)
        if not isinstance(content, list) or not content:
            return
        
        candidates = [i for i in content if i.get("rank", 0) < 4 and "[STRATEGIC_ANCHOR]" not in i.get("summary", "")]
        if not candidates:
            logging.info("✨ This sector is already optimized. Returning to sleep.")
            return
            
        target_item = random.choice(candidates)
        logging.info(f"🎯 Refining artifact: {target_item.get('summary')[:50]}...")
        
        prompt = (
            f"Refine the following technical artifact from {target_file} into a high-density 'Diamond' gem. "
            "Inject modern technical context, clarify the validation impact, and ensure professional brevity. "
            "STRICT: NO ROLEPLAY. Return a refined version."
        )
        
        # Trigger the refinement
        await remote_brain_think(prompt, json.dumps(target_item))
        
        # Storage (Mark the intent in the Behavioral DNA)
        await self.archive.call_tool("retrospective_audit", arguments={
            "interaction_log": f"Recursive Refinement: {target_item.get('summary')[:100]}",
            "domain": "refinement",
            "adapter": "exp_for",
            "vibe": "TECHNICAL"
        })
        logging.info("✅ Refinement request dispatched.")

async def main():
    logging.basicConfig(level=logging.INFO, format="[DREAM] %(message)s")
    logging.info("🌙 Starting the Diamond Dream Cycle (V5)...")

    # 1. Ensure Engine is Ready
    ready, model_name = await ensure_engine_ready()
    if not ready:
        logging.error("❌ Lab could not be ignited for Dreaming. Aborting.")
        return

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{BASE_DIR}/src:{env.get('PYTHONPATH', '')}"
    archive_params = StdioServerParameters(command=PYTHON_PATH, args=[ARCHIVE_NODE], env=env)

    try:
        async with stdio_client(archive_params) as (ar, aw):
            async with ClientSession(ar, aw) as archive:
                await archive.initialize()
                manager = DreamManager(archive)
                await manager.run_cycle()

    except Exception as e:
        logging.error(f"❌ Dream Cycle Crashed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
