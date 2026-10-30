import asyncio
import os
import sys

import pytest

# Ensure HomeLabAI/src is on sys.path
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)
from nodes.mlx_judge_node import judge_driver


@pytest.mark.asyncio
async def test_mlx_judge_driver_ping():
    """Verify that MLXAsyncJudge returns a valid liveness payload."""
    res = await judge_driver.ping_node()
    assert "status" in res
    assert "endpoint" in res


@pytest.mark.asyncio
async def test_mlx_judge_256k_evaluation():
    """Verify that MLXAsyncJudge evaluates turn trace and returns structured sanity payload."""
    turn_trace = "USER: Tell me about 2018 Optane AEP work.\nPINKY: Egad Brain! AEP persistent memory!"
    context_window = "2018 Datacenter PAE Intel Federal 100-node cluster debug BIOS microcode Optane AEP"

    res = await judge_driver.evaluate_256k_context(turn_trace, context_window)
    assert res["node_id"] == "NODE_3_M5_AIR_MLX"
    assert res["status"] in ["VERIFIED_PASS", "ONLINE", "ONLINE_EVALUATED", "STANDBY_STUB"]
    assert res["context_eval_length"] == len(turn_trace) + len(context_window)
    assert "route_feedback" in res


@pytest.mark.asyncio
async def test_mlx_judge_refusal_and_critique_parsing(monkeypatch):
    """[BKM-062 / FEAT-443] Test that non-JSON / refusal defaults to 0.00 (kills 0.95 green lie),
    and valid critique-first JSON parses cleanly."""
    from unittest.mock import AsyncMock, MagicMock
    import aiohttp

    # Case 1: Model refusal "I'm an AI assistant, not a persona."
    fake_refusal_resp = MagicMock()
    fake_refusal_resp.status = 200
    fake_refusal_resp.json = AsyncMock(return_value={
        "choices": [{"message": {"content": "I'm an AI assistant, not a persona."}}]
    })

    fake_session = MagicMock()
    fake_session.__aenter__ = AsyncMock(return_value=fake_session)
    fake_session.__aexit__ = AsyncMock(return_value=None)
    fake_post_ctx = MagicMock()
    fake_post_ctx.__aenter__ = AsyncMock(return_value=fake_refusal_resp)
    fake_post_ctx.__aexit__ = AsyncMock(return_value=None)
    fake_session.post = MagicMock(return_value=fake_post_ctx)

    monkeypatch.setattr(aiohttp, "ClientSession", lambda *args, **kwargs: fake_session)

    res_refusal = await judge_driver.evaluate_256k_context("trace", "context")
    assert res_refusal["status"] == "UNPARSED_REFUSAL"
    assert res_refusal["score"] == 0.0
    assert res_refusal["score_source"] == "ERROR_FALLBACK"

    # Case 2: Critique-first structured JSON
    fake_json_resp = MagicMock()
    fake_json_resp.status = 200
    fake_json_resp.json = AsyncMock(return_value={
        "choices": [{"message": {"content": '{"critique": "Factually accurate historical trace.", "score": 4.5, "retort": "Verified."}'}}]
    })
    fake_post_ctx2 = MagicMock()
    fake_post_ctx2.__aenter__ = AsyncMock(return_value=fake_json_resp)
    fake_post_ctx2.__aexit__ = AsyncMock(return_value=None)
    fake_session.post = MagicMock(return_value=fake_post_ctx2)

    res_valid = await judge_driver.evaluate_256k_context("trace", "context")
    assert res_valid["status"] == "ONLINE_EVALUATED"
    assert res_valid["score"] == 0.9  # 4.5 / 5.0
    assert res_valid["score_source"] == "ONLINE_LLM_JUDGE"
    assert "Factually accurate" in res_valid["critique"]


if __name__ == "__main__":
    asyncio.run(test_mlx_judge_driver_ping())
    asyncio.run(test_mlx_judge_256k_evaluation())
    print("✅ All M5 Air MLX Judge Node tests passed cleanly!")
