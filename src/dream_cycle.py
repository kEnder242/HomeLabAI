import asyncio
import logging
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PYTHON_PATH = sys.executable

async def run_dream_cycle():
    logging.basicConfig(level=logging.INFO, format='[DREAM] %(message)s')
    logging.info("🌙 Starting the Dream Cycle...")

    archive_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/archive_node.py"])
    brain_params = StdioServerParameters(command=PYTHON_PATH, args=["src/nodes/brain_node.py"])

    try:
        async with stdio_client(archive_params) as (ar, aw), \
                   stdio_client(brain_params) as (br, bw):
            
            async with ClientSession(ar, aw) as archive, \
                       ClientSession(br, bw) as brain:
                
                await archive.initialize()
                await brain.initialize()
                
                # 1. Recall: Get raw logs from the short-term stream
                logging.info("📥 Recalling raw memories from the stream...")
                result = await archive.call_tool("get_stream_dump", arguments={})
                
                import json
                try:
                    data = json.loads(result.content[0].text)
                except Exception as e:
                    logging.error(f"Failed to parse stream dump: {e}")
                    return

                docs = data.get("documents", [])
                ids = data.get("ids", [])

                if not docs:
                    logging.info("💤 No raw memories in the stream. Returning to sleep.")
                    return

                logging.info(f"🧠 Found {len(docs)} memories. Asking the Brain to synthesize Diamond Wisdom...")

                # 2. Synthesis: Brain processes the logs into a high-density narrative
                narrative_input = "\n---\n".join(docs)
                brain_prompt = (
                    "You are the Brain of the Acme Lab. Synthesize the following chaotic stream of conversation logs "
                    "into a concise, high-density 'Technical Narrative'. "
                    "Identify key technical decisions, validation scars, and strategic wins. "
                    "Ignore greetings, small talk, and repetitive 'Nervous Tics'. "
                    "Output a high-density paragraph suitable for long-term wisdom storage."
                )
                
                brain_res = await brain.call_tool("deep_think", arguments={
                    "query": brain_prompt,
                    "context": narrative_input
                })
                summary = brain_res.content[0].text
                
                logging.info("✨ Synthesis complete.")

                # 3. Consolidation: Save to Wisdom and Clear Stream
                logging.info(f"💾 Consolidating {len(ids)} memories into Wisdom and purging stream...")
                await archive.call_tool("dream", arguments={
                    "summary": summary,
                    "sources": ids
                })

                logging.info("✅ Dream Cycle Finished successfully. The Lab is now wiser.")


    except Exception as e:
        logging.error(f"❌ Dream Cycle Crashed: {e}")

if __name__ == "__main__":
    asyncio.run(run_dream_cycle())
