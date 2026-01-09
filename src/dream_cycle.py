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
                
                # 1. Recall: Get raw logs
                logging.info("📥 Recalling raw memories from the stream...")
                result = await archive.call_tool("get_stream_dump", arguments={})
                
                # FastMCP/MCP return results in content[0].text or as a JSON string
                # Since we return a dict, we need to handle the structure
                import json
                try:
                    data = json.loads(result.content[0].text)
                except:
                    logging.error("Failed to parse stream dump.")
                    return

                docs = data.get("documents", [])
                ids = data.get("ids", [])

                if not docs:
                    logging.info("💤 No raw memories to process. Returning to sleep.")
                    return

                logging.info(f"🧠 Found {len(docs)} memories. Asking the Brain to synthesize...")

                # 2. Synthesis: Brain processes the logs
                narrative_input = "\n---\n".join(docs)
                brain_prompt = (
                    "Synthesize the following chaotic stream of conversation logs into a concise, "
                    "high-level narrative of Jason's goals, progress, and struggles. "
                    "Identify key technical insights or decisions made."
                )
                
                brain_res = await brain.call_tool("deep_think", arguments={
                    "query": brain_prompt,
                    "context": narrative_input
                })
                summary = brain_res.content[0].text
                
                logging.info("✨ Synthesis complete.")
                # logging.info(f"Dream Summary: {summary[:200]}...")

                # 3. Consolidation: Save to Wisdom and Clear Stream
                logging.info("💾 Storing wisdom and purging the stream...")
                await archive.call_tool("dream", arguments={
                    "summary": summary,
                    "sources": ids
                })

                logging.info("✅ Dream Cycle Finished successfully.")

    except Exception as e:
        logging.error(f"❌ Dream Cycle Crashed: {e}")

if __name__ == "__main__":
    asyncio.run(run_dream_cycle())
