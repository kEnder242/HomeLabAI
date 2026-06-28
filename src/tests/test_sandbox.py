#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Sandbox Tool Isolation Validator
Spins up a mocked CognitiveHub and tests call_tool and list_tools blocking behavior.
"""

import asyncio
from unittest.mock import MagicMock, AsyncMock
from logic.cognitive_hub import CognitiveHub

# Mock types matching MCP tools representation
class MockTool:
    def __init__(self, name):
        self.name = name

class MockToolsResponse:
    def __init__(self, tools):
        self.tools = tools

async def run_validation():
    print("🧪 Running Sandbox Tool Isolation Tests...")
    
    # 1. Mock Resident Session
    mock_session = MagicMock()
    mock_session.call_tool = AsyncMock(return_value="Success")
    
    tools_list = [
        MockTool("think"),
        MockTool("get_context"),
        MockTool("close_lab"),
        MockTool("bounce_node")
    ]
    mock_session.list_tools = AsyncMock(side_effect=lambda: MockToolsResponse(list(tools_list)))
    
    residents = {"pinky": mock_session}
    
    # 2. Initialize CognitiveHub
    hub = CognitiveHub(
        residents=residents,
        broadcast_callback=AsyncMock(),
        sensory_manager=MagicMock(),
        get_vram_status=lambda: True,
        trigger_morning_briefing=AsyncMock()
    )
    
    # Check default initialization
    hub.current_vibe = "TECHNICAL"
    hub._wrap_residents_for_sandbox()
    
    session = hub.residents["pinky"]
    
    # --- Test 1: list_tools filters blocked keywords under TECHNICAL ---
    print("Testing list_tools filtering under TECHNICAL vibe...")
    resp = await session.list_tools()
    tool_names = [t.name for t in resp.tools]
    print(f"Active tools: {tool_names}")
    assert "close_lab" not in tool_names, "Error: 'close_lab' was not filtered!"
    assert "bounce_node" not in tool_names, "Error: 'bounce_node' was not filtered!"
    assert "think" in tool_names, "Error: 'think' was filtered!"
    print("✅ Test 1 Passed: Blocked tools successfully hidden.")
    
    # --- Test 2: call_tool blocks prohibited commands under TECHNICAL ---
    print("Testing call_tool execution blocking under TECHNICAL vibe...")
    try:
        await session.call_tool("close_lab", {})
        assert False, "Error: close_lab tool call was not blocked!"
    except ValueError as e:
        print(f"Caught expected error: {e}")
        assert "blocked by Sandbox" in str(e)
    print("✅ Test 2 Passed: Prohibited tool calls successfully blocked.")
    
    # --- Test 3: list_tools allows all tools under META ---
    print("Testing list_tools filtering under META vibe...")
    hub.current_vibe = "META"
    resp = await session.list_tools()
    tool_names = [t.name for t in resp.tools]
    print(f"Active tools under META: {tool_names}")
    assert "close_lab" in tool_names, "Error: 'close_lab' should be allowed under META!"
    assert "bounce_node" in tool_names, "Error: 'bounce_node' should be allowed under META!"
    print("✅ Test 3 Passed: Blocked tools successfully allowed under META.")
    
    # --- Test 4: call_tool allows prohibited commands under META ---
    print("Testing call_tool execution under META vibe...")
    await session.call_tool("close_lab", {})
    mock_session._original_call_tool.assert_called_with("close_lab", {})
    print("✅ Test 4 Passed: Prohibited tool calls successfully allowed under META.")
    
    print("\n🎉 ALL SANDBOX ISOLATION TESTS PASSED NOMINAL.")

if __name__ == "__main__":
    asyncio.run(run_validation())
