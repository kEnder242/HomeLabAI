import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import sys
import os

# Configuration
PYTHON_PATH = sys.executable
BRAIN_SCRIPT = "src/nodes/brain_node.py"
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts")

async def test_draft_agency():
    print("🧪 Starting Draft Agency Integration Test...")
    
    server_params = StdioServerParameters(command=PYTHON_PATH, args=[BRAIN_SCRIPT])
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("✅ Brain Node Connected.")
            
            # 1. Test Clean Write (with chatter)
            filename = "test_plan.md"
            chatter_content = "Certainly! Here is the plan:\n\n# The Plan\n1. Step one\n2. Step two"
            print(f"\n1. Testing Scribble Note: '{filename}'")
            res_1 = await session.call_tool("write_draft", arguments={
                "filename": filename,
                "content": chatter_content
            })
            
            print(f"   Result: {res_1.content[0].text}")
            
            # Verify file exists and is clean
            file_path = os.path.join(DRAFTS_DIR, filename)
            if os.path.exists(file_path):
                with open(file_path, "r") as f:
                    actual_content = f.read()
                print(f"   File Content:\n---\n{actual_content}\n---")
                if "Certainly!" not in actual_content and "# The Plan" in actual_content:
                    print("   ✅ Correct: Editor cleaned the content.")
                else:
                    print("   ❌ Failed: Content still contains chatter.")
            else:
                print("   ❌ Failed: File not created.")

            # 2. Test Collision
            print(f"\n2. Testing Collision (overwrite=False)")
            res_2 = await session.call_tool("write_draft", arguments={
                "filename": filename,
                "content": "New content"
            })
            print(f"   Result: {res_2.content[0].text}")
            if "already exists" in res_2.content[0].text:
                print("   ✅ Correct: Prevented accidental overwrite.")
            else:
                print("   ❌ Failed: Overwrote without permission.")

            # 3. Test Overwrite
            print(f"\n3. Testing Overwrite (overwrite=True)")
            res_3 = await session.call_tool("write_draft", arguments={
                "filename": filename,
                "content": "Revised content",
                "overwrite": True
            })
            print(f"   Result: {res_3.content[0].text}")
            with open(file_path, "r") as f:
                new_content = f.read()
            if "Revised content" in new_content:
                print("   ✅ Correct: Overwrite successful.")
            else:
                print("   ❌ Failed: Overwrite did not update file.")

if __name__ == "__main__":
    asyncio.run(test_draft_agency())
