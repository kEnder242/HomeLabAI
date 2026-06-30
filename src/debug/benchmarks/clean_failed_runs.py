#!/usr/bin/env python3
"""
[BKM-011] Benchmark Ledger Maintenance: Clean Failed Runs
Removes entries from benchmarks.jsonl where:
  - ttft_ms == 0.0  (engine never responded)
  - response contains [ERROR]

Uses atomic write (write to .tmp, then os.replace) to prevent
race conditions with the running Attendant server.

Usage:
  python3 clean_failed_runs.py              # dry-run (default)
  python3 clean_failed_runs.py --execute    # perform the purge
"""
import json
import os
import sys

LEDGER = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "logs", "benchmarks.jsonl"
)
LEDGER = os.path.abspath(LEDGER)


def is_failed_run(entry: dict) -> bool:
    """Returns True if this entry is a failed/error run that should be purged."""
    if entry.get("ttft_ms", -1) == 0.0 and "[ERROR]" in entry.get("response", ""):
        return True
    return False


def main():
    execute = "--execute" in sys.argv

    if not os.path.exists(LEDGER):
        print(f"[ERROR] Ledger not found: {LEDGER}")
        sys.exit(1)

    with open(LEDGER, "r") as f:
        lines = f.readlines()

    total = len(lines)
    keep = []
    purged = []

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            print(f"[WARN] Skipping malformed JSON on line {i + 1}")
            keep.append(line)
            continue

        if is_failed_run(entry):
            purged.append(entry)
        else:
            keep.append(line)

    print(f"{'=' * 60}")
    print(f"  BENCHMARK LEDGER MAINTENANCE")
    print(f"  Ledger:    {LEDGER}")
    print(f"  Total:     {total} entries")
    print(f"  Failed:    {len(purged)} entries (ttft_ms=0 + [ERROR])")
    print(f"  Retained:  {len(keep)} entries")
    print(f"  Mode:      {'EXECUTE' if execute else 'DRY-RUN'}")
    print(f"{'=' * 60}")

    if purged:
        print("\n  Purge manifest:")
        for p in purged:
            ts = p.get("timestamp", 0)
            pid = p.get("prompt_id", "?")
            score = p.get("judge_score", "?")
            resp_preview = p.get("response", "")[:60]
            print(f"    - [{pid}] score={score} | {resp_preview}...")

    if not execute:
        print(f"\n  [DRY-RUN] No changes written. Re-run with --execute to purge.")
        return

    # Atomic write: .tmp then os.replace
    tmp_path = LEDGER + ".tmp"
    with open(tmp_path, "w") as f:
        for line in keep:
            f.write(line + "\n")
    os.replace(tmp_path, LEDGER)

    print(f"\n  [DONE] Purged {len(purged)} failed entries. Ledger updated atomically.")


if __name__ == "__main__":
    main()
