"""Unit tests for the Universal Epistemic 5‑Question Battery.

Verifies:
* 0% score variance across repeated evaluation runs (determinism).
* Exact rank calculation (Rank = 1 + sum(True assertions)).
* Individual check correctness for known inputs.
"""

import pytest

from src.curator.scan_curator import (
    evaluate_gem_quality,
    has_exact_identifiers,
    has_reproduction_recipe,
    isolates_cause_and_effect,
    is_actionable_bkm,
    has_zero_conversational_fluff,
    _compute_rank,
)


# ──────────────────────────────────────────────────────────────────────────────
# Determinism: 0% score variance across repeated runs
# ──────────────────────────────────────────────────────────────────────────────
class TestDeterminism:
    """Evaluate the same text N times and assert identical results every run."""

    @pytest.mark.parametrize("text", [
        # Empty / minimal
        "",
        # Pure fluff (no checks pass)
        "Hello! I think maybe this could help. Hope this helps! Let me know.",
        # Technical with all 5 checks passing
        (
            "Run: sudo modprobe mce_policy && dmesg | grep -i mce\n"
            "Because the MSR 0x610 register is misconfigured, "
            "the PCIe AER 0x10 error counter triggers a machine check. "
            "Resolution procedure:\n"
            "1. Edit /etc/modprobe.d/mce.conf\n"
            "2. Set mce_policy=strict\n"
            "3. Reboot"
        ),
        # Partial match – only some checks
        (
            "The port 8088 timeout is caused by a NIC firmware bug. "
            "Run `ethtool -S eth0 | grep errors` to diagnose."
        ),
    ])
    def test_zero_variance_over_100_runs(self, text: str) -> None:
        """Run evaluate_gem_quality 100 times; rank must never change."""
        results = [evaluate_gem_quality(text) for _ in range(100)]
        ranks = [r["rank"] for r in results]
        assert len(set(ranks)) == 1, (
            f"Score variance detected! Got {len(set(ranks))} distinct "
            f"ranks across 100 runs: {sorted(set(ranks))}"
        )

    def test_checks_dict_stable(self) -> None:
        """The checks dictionary values must be identical across runs."""
        text = "Run `dmesg | grep mce` because MSR 0x610 is bad. 1. Edit config."
        results = [evaluate_gem_quality(text) for _ in range(50)]
        for r in results:
            assert r["checks"] == results[0]["checks"], (
                "Checks dict varied across runs — non‑deterministic!"
            )


# ──────────────────────────────────────────────────────────────────────────────
# Rank calculation correctness
# ──────────────────────────────────────────────────────────────────────────────
class TestRankCalculation:
    """Verify Rank = 1 + sum(True booleans), range [1, 5]."""

    def test_all_false(self) -> None:
        checks = {
            "has_exact_identifiers": False,
            "has_reproduction_recipe": False,
            "isolates_cause_and_effect": False,
            "is_actionable_bkm": False,
            "has_zero_conversational_fluff": False,
        }
        assert _compute_rank(checks) == 1

    def test_all_true(self) -> None:
        checks = {
            "has_exact_identifiers": True,
            "has_reproduction_recipe": True,
            "isolates_cause_and_effect": True,
            "is_actionable_bkm": True,
            "has_zero_conversational_fluff": True,
        }
        assert _compute_rank(checks) == 5

    def test_two_true(self) -> None:
        checks = {
            "has_exact_identifiers": True,
            "has_reproduction_recipe": False,
            "isolates_cause_and_effect": True,
            "is_actionable_bkm": False,
            "has_zero_conversational_fluff": False,
        }
        assert _compute_rank(checks) == 3

    def test_rank_range_always_valid(self) -> None:
        """Every boolean combination yields a rank in [1, 5]."""
        import itertools
        for combo in itertools.product([True, False], repeat=5):
            checks = dict(zip(
                ["has_exact_identifiers", "has_reproduction_recipe",
                 "isolates_cause_and_effect", "is_actionable_bkm",
                 "has_zero_conversational_fluff"],
                combo,
            ))
            rank = _compute_rank(checks)
            assert 1 <= rank <= 5, f"Rank {rank} out of range for {combo}"


# ──────────────────────────────────────────────────────────────────────────────
# Individual check correctness
# ──────────────────────────────────────────────────────────────────────────────
class TestIndividualChecks:
    """Positive and negative cases for each of the 5 boolean assertions."""

    # --- has_exact_identifiers ---
    def test_identifier_msr(self) -> None:
        assert has_exact_identifiers("MSR 0x610 is misconfigured") is True

    def test_identifier_port(self) -> None:
        assert has_exact_identifiers("Connection on port 8088") is True

    def test_identifier_pcie_aer(self) -> None:
        assert has_exact_identifiers("PCIe AER 0x10 error") is True

    def test_identifier_errno(self) -> None:
        assert has_exact_identifiers("errno 2") is True

    def test_identifier_absent(self) -> None:
        assert has_exact_identifiers("The system crashed") is False

    # --- has_reproduction_recipe ---
    def test_recipe_fenced_block(self) -> None:
        assert has_reproduction_recipe("```\nls -la\n```") is True

    def test_recipe_backtick_one_liner(self) -> None:
        assert has_reproduction_recipe("Run `dmesg | grep mce`") is True

    def test_recipe_shell_keyword(self) -> None:
        assert has_reproduction_recipe("sudo apt-get update") is True

    def test_recipe_absent(self) -> None:
        assert has_reproduction_recipe("Just restart the machine") is False

    # --- isolates_cause_and_effect ---
    def test_cae_because(self) -> None:
        assert isolates_cause_and_effect("System froze because RAM is bad") is True

    def test_cae_root_cause(self) -> None:
        assert isolates_cause_and_effect("The root cause is a driver bug") is True

    def test_cae_absent(self) -> None:
        assert isolates_cause_and_effect("System froze. Restart it.") is False

    # --- is_actionable_bkm ---
    def test_bkm_numbered_steps(self) -> None:
        text = "Fix:\n1. Edit config\n2. Restart service"
        assert is_actionable_bkm(text) is True

    def test_bkm_imperative(self) -> None:
        assert is_actionable_bkm("Run the following command") is True

    def test_bkm_absent(self) -> None:
        assert is_actionable_bkm("Maybe try reinstalling it") is False

    # --- has_zero_conversational_fluff ---
    def test_fluff_hello(self) -> None:
        assert has_zero_conversational_fluff("Hello! How are you?") is False

    def test_fluff_hedging(self) -> None:
        assert has_zero_conversational_fluff("I think maybe it could be RAM") is False

    def test_fluff_none(self) -> None:
        assert has_zero_conversational_fluff(
            "MSR 0x610 triggers MCE. Run dmesg | grep mce to verify."
        ) is True


# ──────────────────────────────────────────────────────────────────────────────
# Integration: evaluate_gem_quality end‑to‑end
# ──────────────────────────────────────────────────────────────────────────────
class TestIntegration:
    """Full battery evaluation on curated sample texts."""

    def test_perfect_score(self) -> None:
        """All 5 checks pass → rank 5."""
        text = (
            "Run: sudo modprobe mce_policy && dmesg | grep -i mce\n"
            "Because the MSR 0x610 register is misconfigured, "
            "the PCIe AER 0x10 error counter triggers a machine check. "
            "Resolution procedure:\n"
            "1. Edit /etc/modprobe.d/mce.conf\n"
            "2. Set mce_policy=strict\n"
            "3. Reboot"
        )
        result = evaluate_gem_quality(text)
        assert result["rank"] == 5
        assert all(result["checks"].values())

    def test_zero_score(self) -> None:
        """Only fluff → rank 1."""
        text = "Hello! I think maybe this could help. Hope this helps! Let me know."
        result = evaluate_gem_quality(text)
        assert result["rank"] == 1
        assert result["checks"]["has_exact_identifiers"] is False
        assert result["checks"]["has_reproduction_recipe"] is False
        assert result["checks"]["isolates_cause_and_effect"] is False
        assert result["checks"]["is_actionable_bkm"] is False
        assert result["checks"]["has_zero_conversational_fluff"] is False

    def test_mid_score(self) -> None:
        """Some checks pass → rank between 2 and 4."""
        text = (
            "The port 8088 timeout is caused by a NIC firmware bug. "
            "Run `ethtool -S eth0 | grep errors` to diagnose."
        )
        result = evaluate_gem_quality(text)
        # port ✓, recipe ✓, cause ✓, bkm ✗, fluff-free ✓ → 4 passes → rank 5
        assert result["rank"] == 5
        assert result["checks"]["has_exact_identifiers"] is True
        assert result["checks"]["has_reproduction_recipe"] is True
        assert result["checks"]["isolates_cause_and_effect"] is True
        assert result["checks"]["is_actionable_bkm"] is False

    def test_result_structure(self) -> None:
        """Verify the exact JSON structure returned."""
        result = evaluate_gem_quality("test")
        assert isinstance(result, dict)
        assert "rank" in result
        assert "checks" in result
        assert isinstance(result["rank"], int)
        assert isinstance(result["checks"], dict)
        assert len(result["checks"]) == 5
