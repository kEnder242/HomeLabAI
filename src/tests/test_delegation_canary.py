"""
[FEAT-513 / SPR-69.4] Bicameral Local Delegation Canary
A stub-and-fill target for certifying Atlas (4090) -> Sisyphus-Junior (M5 Air) delegation.
"""
import pytest


def compute_xor_checksum(values: list[int]) -> int:
    """
    Compute the cumulative bitwise XOR of all integers in values.
    Returns 0 if values is empty.
    """
    acc = 0
    for v in values:
        acc ^= v
    return acc


def test_xor_checksum_empty():
    assert compute_xor_checksum([]) == 0


def test_xor_checksum_single():
    assert compute_xor_checksum([42]) == 42


def test_xor_checksum_multiple():
    # 1 ^ 2 ^ 3 ^ 4 = (1 ^ 2) ^ 3 ^ 4 = 3 ^ 3 ^ 4 = 0 ^ 4 = 4
    assert compute_xor_checksum([1, 2, 3, 4]) == 4
    # 10 ^ 20 ^ 30 = 30 ^ 30 = 0
    assert compute_xor_checksum([10, 20, 30]) == 0
