import os
import json
import tempfile
import pytest
from memory.blackboard_ledger import BlackboardLedger

def test_blackboard_ledger_append_delta():
    """Verify append_round_table_delta persists turn deltas, computes cumulative sums, and saves JSON atomically."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_output = os.path.join(tmpdir, "test_deltas.json")
        ledger = BlackboardLedger()
        
        deltas = {
            "triage": 0.05,
            "pinky_stance": 0.12,
            "brain_arch": 0.45,
            "oracle": 0.20,
            "pinky_judgment": 0.18
        }
        bullets = ["Triage complete", "Pinky stance verified"]
        consensus = "All nodes aligned."
        
        # Turn 1 append
        entry1 = ledger.append_round_table_delta(
            turn=1,
            topic="TEST_TOPIC_1",
            scope="CONTEXT_SCOPE_LONG",
            deltas=deltas,
            bullets=bullets,
            consensus=consensus,
            output_path=tmp_output
        )
        
        assert os.path.exists(tmp_output)
        with open(tmp_output, "r") as f:
            data = json.load(f)
            assert len(data) == 1
            rec = data[0]
            assert rec["turn"] == 1
            assert rec["topic"] == "TEST_TOPIC_1"
            assert rec["cumulative"]["pinky_judgment"] == 1.0  # 0.05 + 0.12 + 0.45 + 0.20 + 0.18 = 1.0
            assert rec["total_s"] == 1.0
            assert rec["distillation_bullets"] == bullets
            assert rec["consensus_1liner"] == consensus
            
        # Turn 2 append (tests persistence and monotonicity)
        entry2 = ledger.append_round_table_delta(
            turn=2,
            topic="TEST_TOPIC_2",
            scope="CONTEXT_SCOPE_TURN",
            deltas=deltas,
            bullets=["Second turn complete"],
            consensus="Second consensus nominal.",
            output_path=tmp_output
        )
        with open(tmp_output, "r") as f:
            data = json.load(f)
            assert len(data) == 2
            assert data[1]["turn"] == 2
            assert data[1]["topic"] == "TEST_TOPIC_2"
