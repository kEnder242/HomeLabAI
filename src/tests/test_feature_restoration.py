import pytest
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from nodes.loader import BicameralNode

@pytest.mark.asyncio
async def test_identity_grounding_injection():
    node = BicameralNode("pinky", "test prompt")
    # Mock infra to ensure predictable output
    node.infra = {
        "hosts": {
            "localhost": {"ip_hint": "127.0.0.1"},
            "KENDER": {"ip_hint": "192.168.1.26"}
        }
    }
    
    prompt = node.unify_prompt("test query")
    
    assert "[PHYSICAL_LAB_MAP]" in prompt
    assert "RTX 2080 Ti" in prompt
    assert "RTX 4090" in prompt
    assert "Current Identity: PINKY" in prompt

def test_tool_schema_restoration():
    node = BicameralNode("brain", "test prompt")
    schemas = node.get_tool_schemas()
    
    tool_names = [s["function"]["name"] for s in schemas]
    assert "scribble_note" in tool_names
    assert "bounce_node" in tool_names
    assert "reply_to_user" in tool_names
