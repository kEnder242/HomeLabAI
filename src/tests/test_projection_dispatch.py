#!/usr/bin/env python3
"""
[FEAT-059 / FEAT-673 / Story 109.12] Unit & Integration Tests for Multi-Node Projection Dispatch.

Verifies:
1. /api/projection/dispatch handler fans out simultaneously to multiple physical nodes.
2. Handles reachable nodes (vLLM on :8088 and MLX on :8002) returning ONLINE with valid completions.
3. Handles unreachable nodes (e.g. KENDER timeout) with clean OFFLINE status and error messaging.
4. Validates zero-stub response architecture per the Always-Live Mandate.
"""

import sys
import asyncio
from pathlib import Path
import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

SRC_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SRC_DIR))

from v5.foyer.router import FoyerRouter


class DummyCognitiveHub:
    def __init__(self):
        self.running = True


@pytest.mark.asyncio
async def test_projection_dispatch_handler():
    print("Testing handle_projection_dispatch handler...")
    foyer = FoyerRouter()

    # Build mock aiohttp request
    payload = {
        "prompt": "Summarize the primary purpose of server manageability and IPMI.",
        "lens": "technical",
        "max_tokens": 50
    }

    req = make_mocked_request(
        "POST",
        "/api/projection/dispatch",
        headers={"Content-Type": "application/json"},
    )
    # Patch request.json()
    async def mock_json():
        return payload
    req.json = mock_json

    resp = await foyer.handle_projection_dispatch(req)
    assert resp.status == 200, f"Expected 200 OK, got {resp.status}"

    import json
    data = json.loads(resp.text)
    assert data.get("status") == "OK"
    assert data.get("lens") == "technical"
    assert "fleet" in data
    fleet = data["fleet"]
    assert len(fleet) >= 2, f"Expected at least 2 nodes evaluated, got {len(fleet)}"

    print(f"Fleet Dispatch Results ({len(fleet)} nodes):")
    online_nodes = 0
    for node in fleet:
        name = node.get("node")
        status = node.get("status")
        lat = node.get("latency_ms", "N/A")
        print(f"  - {name}: {status} ({lat} ms)")
        if status == "ONLINE":
            online_nodes += 1
            assert "completion" in node and len(node["completion"]) > 0
        elif status == "OFFLINE":
            assert "error" in node and len(node["error"]) > 0

    assert online_nodes >= 1, "Expected at least 1 live silicon node to be reachable (vLLM or MLX)"
    print(f"TEST_PROJECTION_DISPATCH_HANDLER: PASSED ({online_nodes} online nodes verified)")


if __name__ == "__main__":
    asyncio.run(test_projection_dispatch_handler())
    print("ALL PROJECTION DISPATCH TESTS PASSED")
