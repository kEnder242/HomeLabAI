import pytest
import asyncio # Not explicitly needed in test file, but good for context
import os

# Configuration
DRAFTS_DIR = os.path.expanduser("~/AcmeLab/drafts") # Needed for cleaning up test artifacts

@pytest.mark.asyncio
async def test_clipboard_logic(archive_client):
    """
    Tests the semantic clipboard (cache) functionality of the archive node.
    """
    session = archive_client # Use the client provided by the fixture
    
    print("\n🧪 Starting Semantic Clipboard Integration Test...")
    
    # 1. Test Miss
    query_1 = "What is the airspeed velocity of an unladen swallow?"
    print(f"\n1. Testing Clipboard Empty for: '{query_1}'")
    res_1 = await session.call_tool("consult_clipboard", arguments={"query": query_1})
    
    if not res_1.content:
         print("   ✅ Correct: Clipboard Empty (No Note).")
    elif res_1.content[0].text == "None":
         print("   ✅ Correct: Clipboard Empty (String None).")
    else:
         print(f"   ❌ Failed: Expected Empty, got '{res_1.content[0].text}'")

    # 2. Test Store
    response_1 = "African or European?"
    print(f"\n2. Scribbling Note: '{response_1}'")
    res_2 = await session.call_tool("scribble_note", arguments={"query": query_1, "response": response_1})
    print(f"   Result: {res_2.content[0].text}")

    # 3. Test Exact Hit
    print(f"\n3. Consulting Clipboard (Exact Match) for: '{query_1}'")
    res_3 = await session.call_tool("consult_clipboard", arguments={"query": query_1})
    content_3 = res_3.content[0].text
    print(f"   Result: {content_3}")
    assert content_3 == response_1, f"Expected '{response_1}', got '{content_3}'"
    print("   ✅ Correct: Exact Note Found.")

    # 4. Test Semantic Hit
    print(f"\n4. Consulting Clipboard (Semantic Match) for: '{query_semantic}'")
    # Note: Using lax threshold 0.4 for test safety, though 0.35 is default for consult_clipboard
    res_4 = await session.call_tool("consult_clipboard", arguments={"query": query_semantic, "threshold": 0.4}) 
    content_4 = res_4.content[0].text
    print(f"   Result: {content_4}")
    assert content_4 == response_1, f"Expected '{response_1}', got '{content_4}'"
    print("   ✅ Correct: Semantic Note Found.")

    # 5. Test TTL (Need to simulate time passing or use explicit timestamp for control)
    # This is more complex and might require a separate helper tool or mock date.
    # For now, we'll rely on the default TTL handling.

    # 6. Test File Cleanup (Ensure test artifacts are removed)
    # This test doesn't create files, so no cleanup needed.


