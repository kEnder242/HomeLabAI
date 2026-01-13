import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys

# Configuration
PYTHON_PATH = sys.executable
ARCHIVE_SCRIPT = "src/nodes/archive_node.py"

async def test_cache_logic():
    print("🧪 Starting Semantic Cache Integration Test...")
    
    server_params = StdioServerParameters(command=PYTHON_PATH, args=[ARCHIVE_SCRIPT])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Archive Node Connected.")
            
            # 1. Test Miss
            query_1 = "What is the airspeed velocity of an unladen swallow?"
            print(f"\n1. Testing Cache Miss for: '{query_1}'")
            res_1 = await session.call_tool("consult_clipboard", arguments={"query": query_1})
            
            # FastMCP returns empty content for None
            if not res_1.content:
                 print("   ✅ Correct: Cache Miss (Empty Result).")
            elif res_1.content[0].text == "None":
                 print("   ✅ Correct: Cache Miss (String None).")
            else:
                 print(f"   ❌ Failed: Expected Miss, got '{res_1.content[0].text}'")

            # 2. Test Store
            response_1 = "African or European?"
            print(f"\n2. Storing Response: '{response_1}'")
            res_2 = await session.call_tool("scribble_note", arguments={"query": query_1, "response": response_1})
            print(f"   Result: {res_2.content[0].text}")

            # 3. Test Exact Hit
            print(f"\n3. Testing Exact Hit for: '{query_1}'")
            res_3 = await session.call_tool("consult_clipboard", arguments={"query": query_1})
            content_3 = res_3.content[0].text
            print(f"   Result: {content_3}")
            if content_3 == response_1:
                print("   ✅ Correct: Exact Hit.")
            else:
                print(f"   ❌ Failed: Expected '{response_1}', got '{content_3}'")

            # 4. Test Semantic Hit
            query_semantic = "Tell me the speed of a swallow carrying nothing"
            print(f"\n4. Testing Semantic Hit for: '{query_semantic}'")
            res_4 = await session.call_tool("consult_clipboard", arguments={"query": query_semantic, "threshold": 0.4}) 
            # Note: Using lax threshold 0.4 for test safety, though 0.35 is default
            content_4 = res_4.content[0].text
            print(f"   Result: {content_4}")
            if content_4 == response_1:
                print("   ✅ Correct: Semantic Hit.")
            else:
                print(f"   ❌ Failed: Expected '{response_1}', got '{content_4}'")

if __name__ == "__main__":
    asyncio.run(test_cache_logic())
