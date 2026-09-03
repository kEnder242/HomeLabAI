"""
[FEAT-529] Safe-Patch Harness Target File.
This file serves as a canonical fixture for verifying that delegated subagents
can invoke surgical patch tools (clara-dna_safe_patch) without destructive clobbers.
"""


def compute_telemetry_metrics(tokens: int, duration_s: float) -> dict[str, float]:
    """Compute basic throughput and rate metrics."""
    if duration_s <= 0:
        return {"throughput_tok_s": 0.0, "duration_s": 0.0}
    return {
        "throughput_tok_s": round(tokens / duration_s, 2),
        "duration_s": round(duration_s, 3),
    }


def format_node_badge(node_name: str, tier: str = "local") -> str:
    """Format node tier badge string."""
    prefix = "[LOCAL]" if tier == "local" else "[CLOUD]"
    return f"{prefix} {node_name.upper()}"

def calculate_energy_efficiency(tokens: int, duration_s: float, watts: float) -> float:
    """Calculate energy efficiency as tokens/(duration*watts)."""
    if duration_s > 0 and watts > 0:
        return round((tokens / duration_s) / watts, 2)
    return 0.0
