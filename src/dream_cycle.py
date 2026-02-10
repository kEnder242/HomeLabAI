import asyncio
import logging
import sys
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PYTHON_PATH = sys.executable
BRAIN_URL = os.environ.get("BRAIN_URL", "http://192.168.1.15:11434/api/generate") # Default to internal lab IP

async def remote_brain_think(prompt, context):
    """Fallback for remote synthesis if Brain node is not local."""
    import aiohttp
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "llama3:latest",
                "prompt": f"{context}\n\n[TASK]: {prompt}",
                "stream": False,
                "options": {"num_predict": 1024, "temperature": 0.3}
            }
            async with session.post(BRAIN_URL, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "Synthesis failed.")
    except Exception as e:
        return f"Remote Brain Error: {e}"

async def run_dream_cycle():
    logging.basicConfig(level=logging.INFO, format='[DREAM] %(message)s')
    logging.info("🌙 Starting the Diamond Dream Cycle...")

    archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
    
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

                logging.info(f"🧠 Synthesizing {len(docs)} turns via The Brain...")

                # 2. Synthesis (Use Remote 4090 if possible)
                narrative_input = "\n---\n".join(docs)
                prompt = (
                    "Synthesize these interaction logs into a high-density 'Diamond Wisdom' paragraph. "
                    "Focus on technical decisions and validation scars. Ignore filler."
                )
                
                summary = await remote_brain_think(prompt, narrative_input)
                logging.info("✨ Synthesis complete.")

                # 3. Consolidation
                logging.info("💾 Storing wisdom and purging stream...")
                await archive.call_tool("dream", arguments={"summary": summary, "sources": ids})

                logging.info("✅ Dream Cycle Finished. The Lab has evolved.")

    except Exception as e:
        logging.error(f"❌ Dream Cycle Crashed: {e}")

if __name__ == "__main__":
    asyncio.run(run_dream_cycle())

