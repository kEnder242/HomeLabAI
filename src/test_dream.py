import asyncio
import sys
import logging
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_dream():
    logging.basicConfig(level=logging.INFO)
    python_path = sys.executable
    archive_params = StdioServerParameters(command=python_path, args=["src/nodes/archive_node.py"])

    async with stdio_client(archive_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # 1. Seed the stream with dummy data
            print("🌱 Seeding Stream...")
            await session.call_tool("save_interaction", arguments={
                "user_query": "I am working on a snake game in Python.",
                "response": "Narf! I'll ask the Brain to help with the code."
            })
            await session.call_tool("save_interaction", arguments={
                "user_query": "The Brain fixed the pygame import issue.",
                "response": "Egad! The Brain is so smart!"
            })

            print("💤 Triggering Dream Cycle...")
            import subprocess
            res = subprocess.run([python_path, "src/dream_cycle.py"], capture_output=True, text=True)
            print(res.stdout)
            print(res.stderr)

            # 2. Verify Stream is purged
            print("🧐 Verifying Stream Cleanup...")
            dump = await session.call_tool("get_stream_dump", arguments={})
            print(f"Remaining IDs: {dump.content[0].text}")

if __name__ == "__main__":
    asyncio.run(test_dream())
