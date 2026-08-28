"""
[FEAT-486 / SPR-65 Story 1] Kender Fast Socket Gate & Triage-as-Primer Vocality Check.

Verifies that when Remote Kender is unreachable, SpeculativeTriageRelay
short-circuits the 2.5s speculative head-start window:
    - relay() returns in < 50ms (no 2.5s head-start delay),
    - local vLLM wins the race immediately (winner == "vllm"),
    - no 60s timeout hang occurs in downstream Strategic Synthesis.
"""

import asyncio
import socket
import time

from src.logic.speculative_triage import SpeculativeTriageRelay, _probe_tcp

VALID_TRIAGE = {
    "vibe": "TECHNICAL",
    "addressed_to": "BRAIN",
    "importance": 0.8,
    "domain": "standard",
}


def _get_closed_port() -> int:
    """Reserve a TCP port on localhost, then release it so connects are refused fast."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _run_relay(port: int) -> tuple:
    """Drive a SpeculativeTriageRelay whose Kender port is unreachable."""

    async def _kender_fn(query, context, schema, rid):
        # The fast gate must prevent Kender from ever being dispatched.
        raise AssertionError("Kender should not be dispatched when its port is unreachable")

    async def _vllm_fn(query, context, schema, rid):
        return dict(VALID_TRIAGE)

    relay = SpeculativeTriageRelay(
        broadcast_callback=lambda *a, **k: None,
        kender_fn=_kender_fn,
        vllm_fn=_vllm_fn,
        t_warm=1.25,
        kender_host="127.0.0.1",
        kender_port=port,
        socket_timeout=0.2,
    )
    return await relay.relay("query", "context", {}, "test_request")


def test_probe_tcp_refused_fast() -> None:
    """_probe_tcp returns False quickly for a closed local port (sub-200ms)."""
    port = _get_closed_port()
    start = time.perf_counter()
    assert _probe_tcp("127.0.0.1", port, 0.2) is False
    assert (time.perf_counter() - start) < 0.2


def test_relay_short_circuits_when_kender_unreachable() -> None:
    """relay() returns (vllm_result, 'vllm'); Kender is never dispatched."""
    port = _get_closed_port()
    result, winner = asyncio.run(_run_relay(port))
    assert winner == "vllm"
    assert result == VALID_TRIAGE


def test_relay_completes_under_50ms_when_kender_down() -> None:
    """The 2.5s head-start window is bypassed; total relay time is < 50ms."""
    port = _get_closed_port()
    start = time.perf_counter()
    result, winner = asyncio.run(_run_relay(port))
    elapsed_ms = (time.perf_counter() - start) * 1000.0
    assert winner == "vllm"
    assert result == VALID_TRIAGE
    assert elapsed_ms < 50.0, f"relay took {elapsed_ms:.1f}ms; expected < 50ms (fast socket gate)"


def test_no_60s_timeout_hang_when_kender_shadow() -> None:
    """Downstream must not block on a 60s remote timeout when Kender is SHADOW."""
    port = _get_closed_port()
    start = time.perf_counter()
    result, winner = asyncio.run(_run_relay(port))
    elapsed = time.perf_counter() - start
    assert winner == "vllm"
    assert elapsed < 30.0, f"Strategic Synthesis hung {elapsed:.1f}s"
