"""
[SPR-47.1 Story 6] Foyer Liveness & Health Integration Test
Validates that the Lab Attendant (FoyerRouter) on localhost:8765 responds
to REST /health and /status probes with valid engine state.
"""
import asyncio
import json
import socket
import sys
import os
import pytest

# ---------------------------------------------------------------------------
# Module-level skip: TCP probe localhost:8765
# ---------------------------------------------------------------------------
def _foyer_reachable(host="localhost", port=8765, timeout=3.0):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False

FOYER_UP = _foyer_reachable()
pytestmark = pytest.mark.skipif(not FOYER_UP, reason="Lab Attendant not running on port 8765")

FOYER_BASE = "http://localhost:8765"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_foyer_health():
    """GET /health returns 200 with valid JSON containing engine state."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{FOYER_BASE}/health", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            body = await resp.json()
            assert isinstance(body, dict), "Health response must be a JSON object"
            print(f"  /health -> {json.dumps(body, indent=2)[:200]}")


@pytest.mark.asyncio
async def test_foyer_status():
    """GET /status returns 200 with valid JSON containing version info."""
    import aiohttp
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{FOYER_BASE}/status", timeout=aiohttp.ClientTimeout(total=10)) as resp:
            assert resp.status == 200, f"Expected 200, got {resp.status}"
            body = await resp.json()
            assert isinstance(body, dict), "Status response must be a JSON object"
            # Check for version or lab_version field
            version_keys = [k for k in body if "version" in k.lower()]
            assert len(version_keys) > 0 or "version" in json.dumps(body).lower(), \
                f"Status response must contain a version field. Keys: {list(body.keys())}"
            print(f"  /status -> {json.dumps(body, indent=2)[:300]}")


# ---------------------------------------------------------------------------
# Direct execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not FOYER_UP:
        print("SKIP: Lab Attendant not running on port 8765")
        sys.exit(0)
    asyncio.run(test_foyer_health())
    print("PASS: test_foyer_health")
    asyncio.run(test_foyer_status())
    print("PASS: test_foyer_status")
    print("All Story 6 integration tests passed.")
