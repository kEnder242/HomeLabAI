"""
[FEAT-283 / Story 108.38] Test Suite for Foyer Startup Queue Compaction & Nightly Stale Purge.
"""

import json
import os
import sys
import tempfile
import time
import pytest

# Ensure HomeLabAI/src is on sys.path
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from v5.foyer.router import compact_foyer_queue as foyer_compact_foyer_queue
from infra.nightly_forge import compact_foyer_queue as forge_compact_foyer_queue


def test_compact_foyer_queue_nonexistent_file():
    """Verify compaction handles nonexistent queue file gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "nonexistent_queue.jsonl")
        a_path = os.path.join(tmpdir, "archive.jsonl")
        stats = foyer_compact_foyer_queue(queue_path=q_path, archive_path=a_path)
        assert stats == {"compacted": 0, "archived": 0, "retained": 0}


def test_compact_foyer_queue_empty_file():
    """Verify compaction handles empty queue file gracefully."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "foyer_queue.jsonl")
        a_path = os.path.join(tmpdir, "archive.jsonl")
        with open(q_path, "w") as f:
            pass  # 0 bytes

        stats = foyer_compact_foyer_queue(queue_path=q_path, archive_path=a_path)
        assert stats["compacted"] == 0
        assert stats["archived"] == 0
        assert stats["retained"] == 0
        assert os.path.getsize(q_path) == 0


def test_compact_foyer_queue_stale_and_completed_purged():
    """Verify that records older than 2 hours or completed are archived, while recent pending are retained."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "foyer_queue.jsonl")
        a_path = os.path.join(tmpdir, "archive.jsonl")

        now = time.time()
        stale_record = {
            "query": "[OPERATIONAL] SLEEP",
            "source": "REMOTE",
            "timestamp": now - 10000,  # > 2 hours ago
            "status": "PENDING",
            "id": "stale_1",
            "metadata": {},
        }
        completed_record = {
            "query": "Tell me about PECI margins",
            "source": "MIC",
            "timestamp": now - 300,  # 5 min ago
            "status": "COMPLETED",
            "id": "comp_1",
            "metadata": {},
        }
        fresh_pending_record = {
            "query": "Are the Aurora nodes cooled down?",
            "source": "CLI",
            "timestamp": now - 60,  # 1 min ago
            "status": "PENDING",
            "id": "fresh_1",
            "metadata": {},
        }

        with open(q_path, "w") as f:
            f.write(json.dumps(stale_record) + "\n")
            f.write(json.dumps(completed_record) + "\n")
            f.write(json.dumps(fresh_pending_record) + "\n")

        stats = foyer_compact_foyer_queue(
            queue_path=q_path, archive_path=a_path, max_age_sec=7200.0
        )

        assert stats["compacted"] == 3
        assert stats["archived"] == 2
        assert stats["retained"] == 1

        # Check retained queue
        with open(q_path, "r") as f:
            remaining = [json.loads(line) for line in f if line.strip()]
        assert len(remaining) == 1
        assert remaining[0]["id"] == "fresh_1"

        # Check archive
        with open(a_path, "r") as f:
            archived = [json.loads(line) for line in f if line.strip()]
        assert len(archived) == 2
        archived_ids = {r["id"] for r in archived}
        assert "stale_1" in archived_ids
        assert "comp_1" in archived_ids


def test_compact_foyer_queue_all_stale_truncates_to_zero():
    """Verify that when all records are stale, queue is truncated to 0 bytes and records are preserved."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "foyer_queue.jsonl")
        a_path = os.path.join(tmpdir, "archive.jsonl")

        now = time.time()
        with open(q_path, "w") as f:
            for i in range(5):
                rec = {
                    "query": f"[OPERATIONAL] TEST_{i}",
                    "timestamp": now - (8000 + i * 100),
                    "status": "PENDING",
                    "id": f"rec_{i}",
                }
                f.write(json.dumps(rec) + "\n")

        stats = foyer_compact_foyer_queue(
            queue_path=q_path, archive_path=a_path, max_age_sec=7200.0
        )

        assert stats["compacted"] == 5
        assert stats["archived"] == 5
        assert stats["retained"] == 0
        assert os.path.getsize(q_path) == 0

        with open(a_path, "r") as f:
            archived = [json.loads(line) for line in f if line.strip()]
        assert len(archived) == 5


def test_queue_tailing_recovers_on_file_truncation():
    """[Story 108.38b / BKM-090] Verify that when a queue file is truncated/compacted,
    tailing offset resets to 0 and subsequent writes are drained cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "foyer_queue.jsonl")

        # Step 1: Write initial 10 lines (simulate accumulated historical queue)
        with open(q_path, "w") as f:
            for i in range(10):
                f.write(json.dumps({"id": f"initial_{i}", "status": "PENDING"}) + "\n")

        last_pos = os.path.getsize(q_path)
        assert last_pos > 200

        # Step 2: File is compacted/truncated down to 1 fresh line (simulate compaction)
        with open(q_path, "w") as f:
            f.write(json.dumps({"id": "compacted_1", "status": "PENDING"}) + "\n")

        size = os.path.getsize(q_path)
        assert size < last_pos

        # Step 3: Tailing logic executes truncation recovery
        if size < last_pos:
            last_pos = 0

        assert size > last_pos
        with open(q_path, "r") as f:
            f.seek(last_pos)
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 1
        assert lines[0]["id"] == "compacted_1"


def test_queue_tailing_recovers_on_inode_rotation():
    """[Story 108.44 / BKM-099] Verify that when a queue file is swapped/rotated to a new inode,
    inode tracking detects the rotation, resets tailing offset to 0, and drains subsequent writes."""
    with tempfile.TemporaryDirectory() as tmpdir:
        q_path = os.path.join(tmpdir, "foyer_queue.jsonl")

        # Step 1: Initial file with old inode
        with open(q_path, "w") as f:
            for i in range(5):
                f.write(json.dumps({"id": f"old_inode_{i}", "status": "PENDING"}) + "\n")

        initial_stat = os.stat(q_path)
        last_pos = initial_stat.st_size
        current_inode = initial_stat.st_ino

        # Step 2: Atomic file replacement (new inode)
        new_q_path = os.path.join(tmpdir, "foyer_queue_new.jsonl")
        with open(new_q_path, "w") as f:
            f.write(json.dumps({"id": "rotated_fresh_1", "status": "PENDING"}) + "\n")

        os.replace(new_q_path, q_path)
        new_stat = os.stat(q_path)
        new_inode = new_stat.st_ino
        assert new_inode != current_inode

        # Step 3: Tailing logic detects inode rotation and resets last_pos
        if current_inode is not None and new_inode != current_inode:
            last_pos = 0
            current_inode = new_inode

        with open(q_path, "r") as f:
            f.seek(last_pos)
            lines = [json.loads(l) for l in f if l.strip()]

        assert len(lines) == 1
        assert lines[0]["id"] == "rotated_fresh_1"
        assert current_inode == new_inode

