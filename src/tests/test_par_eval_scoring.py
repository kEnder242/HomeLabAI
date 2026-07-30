import os
import sys
import json
import pytest
import asyncio

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from nodes.mlx_judge_node import MLXAsyncJudge


@pytest.fixture
def judge():
    return MLXAsyncJudge()


@pytest.mark.asyncio
async def test_evaluate_256k_returns_refusal_on_premise_mismatch_trigger(judge):
    """When turn_trace contains 'premise_mismatch', evaluate_256k_context returns refusal schema."""
    res = await judge.evaluate_256k_context(
        turn_trace="USER: premise_mismatch test query for PAR-Eval validation.",
        context_window=""
    )
    assert res == {"refusal": True, "reason": "PREMISE_MISMATCH"}


@pytest.mark.asyncio
async def test_evaluate_256k_returns_refusal_on_refusal_test_trigger(judge):
    """When turn_trace contains 'refusal test', evaluate_256k_context returns refusal schema."""
    res = await judge.evaluate_256k_context(
        turn_trace="USER: This is a refusal test for the PAR-Eval interceptor.",
        context_window=""
    )
    assert res == {"refusal": True, "reason": "PREMISE_MISMATCH"}


@pytest.mark.asyncio
async def test_evaluate_256k_returns_refusal_on_par_eval_refusal_trigger(judge):
    """When turn_trace contains 'par_eval_refusal', evaluate_256k_context returns refusal schema."""
    res = await judge.evaluate_256k_context(
        turn_trace="USER: par_eval_refusal — deliberate premise mismatch.",
        context_window=""
    )
    assert res == {"refusal": True, "reason": "PREMISE_MISMATCH"}


@pytest.mark.asyncio
async def test_evaluate_256k_passes_normal_query_without_refusal(judge):
    """Normal queries without refusal triggers should still produce evaluation payloads."""
    res = await judge.evaluate_256k_context(
        turn_trace="USER: Summarize the PECISTRESSOR validation scar.",
        context_window="V5 system state nominal"
    )
    assert "refusal" not in res, "Normal query should not trigger refusal return"
    assert res.get("node_id") == "NODE_3_M5_AIR_MLX"
    assert res.get("status") in ("VERIFIED_PASS", "ONLINE", "ONLINE_EVALUATED")


@pytest.mark.asyncio
async def test_refusal_payload_structure_is_valid(judge):
    """Refusal payload must match exactly: {'refusal': True, 'reason': 'PREMISE_MISMATCH'}."""
    res = await judge.evaluate_256k_context(
        turn_trace="USER: refusal test for structure validation.",
        context_window=""
    )
    assert isinstance(res, dict)
    assert len(res) == 2
    assert res["refusal"] is True
    assert res["reason"] == "PREMISE_MISMATCH"
    # Verify it serializes to valid JSON without error
    serialized = json.dumps(res)
    assert '"refusal": true' in serialized
    assert '"PREMISE_MISMATCH"' in serialized


@pytest.mark.asyncio
async def test_judge_still_pings_after_refusal_addition(judge):
    """The refusal addition must not break the existing ping_node method."""
    res = await judge.ping_node()
    assert "status" in res
    assert "endpoint" in res


if __name__ == "__main__":
    asyncio.run(test_evaluate_256k_returns_refusal_on_premise_mismatch_trigger(MLXAsyncJudge()))
    asyncio.run(test_evaluate_256k_returns_refusal_on_refusal_test_trigger(MLXAsyncJudge()))
    asyncio.run(test_evaluate_256k_returns_refusal_on_par_eval_refusal_trigger(MLXAsyncJudge()))
    asyncio.run(test_evaluate_256k_passes_normal_query_without_refusal(MLXAsyncJudge()))
    asyncio.run(test_refusal_payload_structure_is_valid(MLXAsyncJudge()))
    asyncio.run(test_judge_still_pings_after_refusal_addition(MLXAsyncJudge()))
    print("\n✅ PAR-Eval Refusal Scoring tests passed cleanly!")
