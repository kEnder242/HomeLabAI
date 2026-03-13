import asyncio
import logging
import sys
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Configuration
PYTHON_PATH = sys.executable
BASE_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)  # Root of HomeLabAI
ARCHIVE_NODE = os.path.join(BASE_DIR, "src/nodes/archive_node.py")
BRAIN_URL = os.environ.get("BRAIN_URL", "http://192.168.1.26:11434/api/generate")
PINKY_URL = "http://localhost:11434/api/generate"


async def remote_brain_think(prompt, context):
    """Fallback for remote synthesis if Brain node is not local. Now with Pinky-Fallback."""
    import aiohttp

    # Check Brain Health first (Windows 4090)
    use_pinky = False
    try:
        async with aiohttp.ClientSession() as session:
            async with session.head(BRAIN_URL, timeout=2) as resp:
                if resp.status != 200:
                    use_pinky = True
    except Exception:
        use_pinky = True

    target_url = PINKY_URL if use_pinky else BRAIN_URL
    model = "llama-3.2-3b-awq" if use_pinky else "llama3:latest"

    if use_pinky:
        logging.warning(
            "⚠️ Brain (4090) is offline. Falling back to Pinky (2080 Ti) for Dreaming."
        )

    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": model,
                "prompt": f"[TECHNICAL CONTEXT]\n{context}\n\n[TASK]: {prompt}",
                "stream": False,
                "options": {"num_predict": 1024, "temperature": 0.3},
            }
            async with session.post(target_url, json=payload, timeout=60) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("response", "Synthesis failed.")
    except Exception as e:
        return f"Remote Brain Error: {e}"


async def audit_synthesis(summary, context):
    """
    [FEAT-191] Judicial Feedback Loop: Uses peer-node auditing
    to verify 'Diamond Wisdom' quality before storage.
    """
    from infra.cognitive_audit import CognitiveAudit
    
    # We use a mock node wrapper for the auditor to call the remote brain
    class AuditorProxy:
        async def call_tool(self, name, params):
            # The Auditor library expects a node.call_tool interface
            # We wrap remote_brain_think to satisfy this
            res = await remote_brain_think(params["task"], "AUDIT_MODE")
            class MockRes:
                def __init__(self, t): self.content = [type('obj', (object,), {'text': t})]
            return MockRes(res)

    auditor = CognitiveAudit(AuditorProxy())
    constraints = "Technical precision, no roleplay, no conversational filler, high-density synthesis."
    
    is_valid = await auditor.audit_technical_truth(
        query="Verify the quality of this Diamond Wisdom synthesis.",
        response=summary,
        constraints=constraints
    )
    return is_valid

async def run_dream_cycle():
    logging.basicConfig(level=logging.INFO, format="[DREAM] %(message)s")
    logging.info("🌙 Starting the Diamond Dream Cycle...")

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
                    f"🧠 Synthesizing {len(docs)} turns via The Brain (4090)..."
                )

                # 2. Synthesis (Use Remote 4090)
                narrative_input = "\n---\n".join(docs)
                prompt = (
                    "Synthesize these interaction logs into a high-density 'Diamond Wisdom' paragraph. "
                    "Analyze the technical progression, identifying specific decisions made and validation scars uncovered. "
                    "Ignore greetings, character filler, and nervous tics. "
                    "STRICT: NO ROLEPLAY. Do not use 'Narf', 'Poit', or character personality traits. "
                    "Provide a professional report suitable for long-term strategic grounding."
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
