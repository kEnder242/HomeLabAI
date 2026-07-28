import os
import sys
import pytest
import asyncio

# Ensure HomeLabAI/src is on sys.path
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nodes.mlx_judge_node import MLXAsyncJudge, judge_driver


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
    assert res["status"] in ["VERIFIED_PASS", "ONLINE"]
    assert res["context_eval_length"] == len(turn_trace) + len(context_window)
    assert "route_feedback" in res


if __name__ == "__main__":
    asyncio.run(test_mlx_judge_driver_ping())
    asyncio.run(test_mlx_judge_256k_evaluation())
    print("✅ All M5 Air MLX Judge Node tests passed cleanly!")
