import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def list_pinky_tools():
    s_path = "/home/jallred/Dev_Lab/HomeLabAI/src/nodes/pinky_node.py"
    env = {"PYTHONPATH": "/home/jallred/Dev_Lab/HomeLabAI/src"}
    params = StdioServerParameters(
        command="/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3",
        args=[s_path, "--role", "PINKY"],
        env=env
    )
    print("Connecting to Pinky Node...")
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            print(f"Found {len(tools.tools)} tools:")
            for t in tools.tools:
                print(f" - {t.name}: {t.description}")

if __name__ == "__main__":
    asyncio.run(list_pinky_tools())
