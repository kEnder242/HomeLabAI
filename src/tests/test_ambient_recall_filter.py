"""Unit test verifying Story 101.3: Ambient Recall ICM Session Memory Lifecycle & Git Validity Filter."""

import os
import sqlite3
import pytest
from curator.ambient_recall import get_recent_memories


def test_get_recent_memories_filters_stale_commit_diffs(tmp_path, monkeypatch):
    test_db = tmp_path / "memories.db"
    conn = sqlite3.connect(test_db)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            topic TEXT,
            summary TEXT,
            created_at TEXT
        );
        """
    )
    # 1. Stale commit comparison (historical commits not matching current HEAD)
    cursor.execute(
        "INSERT INTO memories VALUES ('1', 'delegation_feedback', 'Story 100.11: daemon serves stale bytecode (Local HEAD a6567a8 vs served fc867e7)', '2026-10-08T08:27:43+00:00')"
    )
    # 2. Raw traceback noise
    cursor.execute(
        "INSERT INTO memories VALUES ('2', 'context-Dev_Lab', 'HomeLabAI/src/tests/__pycache__/test_two_mice_single_execution.py', '2026-10-08T08:18:47+00:00')"
    )
    # 3. Clean architectural decision / status
    cursor.execute(
        "INSERT INTO memories VALUES ('3', 'context-Dev_Lab', '**[STATUS]:** SUCCESS — all 3 blueprint edits applied, verified, checkpointed.', '2026-10-08T08:25:32+00:00')"
    )
    # 4. Valid sprint decision
    cursor.execute(
        "INSERT INTO memories VALUES ('4', 'delegation_feedback', 'Story 100.10: Defeature CASUAL Vibe via Prompt Comment & Align 9-Vibe Taxonomy', '2026-10-08T08:05:37+00:00')"
    )
    conn.commit()
    conn.close()

    # Point ambient_recall to our mock DB
    monkeypatch.setattr(os.path, "expanduser", lambda path: str(test_db) if "memories.db" in path else os.path.expanduser(path))

    results = get_recent_memories(limit=4)

    # Invariant: Stale commit reference and raw path were filtered out
    summaries = [m["summary"] for m in results]
    assert not any("a6567a8" in s for s in summaries)
    assert not any("HomeLabAI/src/" in s for s in summaries)

    # Clean records remain
    assert any("SUCCESS" in s for s in summaries)
    assert any("CASUAL" in s for s in summaries)
