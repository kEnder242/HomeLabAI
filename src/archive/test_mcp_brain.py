import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def test_brain():
    python_path = "/home/jallred/VoiceGateway/.venv/bin/python"
    server_params = StdioServerParameters(
        command=python_path,
        args=["src/brain_mcp_server.py"],
    )

    print("Connecting to Brain MCP...")
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("Connected. Calling tool 'deep_think'...")
            result = await session.call_tool("deep_think", arguments={"query": "Write a short poem about a cat."})
            print("\nResponse:")
            print(result.content[0].text)

if __name__ == "__main__":
    asyncio.run(test_brain())

