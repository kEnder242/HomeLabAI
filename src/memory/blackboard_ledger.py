import time
import logging
from enum import Enum
from typing import Dict, List, Any, Optional

class ContextScope(Enum):
    """[FEAT-523] Round Table Context Scope standard."""
    TURN = "TURN"   # Strict single-turn isolation (e.g. Triage, Deep Thought)
    LONG = "LONG"   # Long-form injected context (e.g. Pinky, Brain)

class BlackboardLedger:
    """[FEAT-523] Round Table Blackboard Ledger for inter-turn distillation & consensus DNA."""
    def __init__(self):
        self.bullets: List[Dict[str, Any]] = []
        self.consensus_1liners: List[Dict[str, Any]] = []

    def record_bullet(self, turn: int, author: str, bullet: str):
        self.bullets.append({
            "turn": turn,
            "author": author,
            "bullet": bullet,
            "ts": time.time()
        })

    def record_consensus(self, turn: int, consensus_line: str):
        self.consensus_1liners.append({
            "turn": turn,
            "consensus": consensus_line,
            "ts": time.time()
        })

    def get_summary(self, turn: Optional[int] = None) -> str:
        lines = []
        relevant_bullets = [b for b in self.bullets if turn is None or b["turn"] == turn]
        if relevant_bullets:
            lines.append("Distillation Bullets:")
            for b in relevant_bullets:
                lines.append(f"- [{b['author'].upper()}]: {b['bullet']}")
        relevant_consensus = [c for c in self.consensus_1liners if turn is None or c["turn"] == turn]
        if relevant_consensus:
            lines.append("Consensus:")
            for c in relevant_consensus:
                lines.append(f"{c['consensus']}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bullets": list(self.bullets),
            "consensus": list(self.consensus_1liners),
            "count_bullets": len(self.bullets),
            "count_consensus": len(self.consensus_1liners)
        }

    def append_round_table_delta(self, turn: int, topic: str, scope: str, deltas: Dict[str, float], bullets: List[str], consensus: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """[FEAT-529] Atomic delta export engine for live turn memory to round table delta-t bridge."""
        import json
        import os

        if output_path is None:
            output_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/round_table_deltas.json")
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        # True monotonic elapsed checkpoints from turn start (t1 -> t5)
        t1_elapsed = round(float(deltas.get("triage", 0.0)), 3)
        t2_elapsed = round(float(deltas.get("pinky_stance", t1_elapsed)), 3)
        t3_elapsed = round(float(deltas.get("brain_arch", t2_elapsed)), 3)
        t4_elapsed = round(float(deltas.get("oracle", t3_elapsed)), 3)
        t5_elapsed = round(float(deltas.get("pinky_judgment", t4_elapsed)), 3)

        # Derived isolated stage durations from checkpoints
        d1 = t1_elapsed
        d2 = max(0.001, round(t2_elapsed - t1_elapsed, 3))
        d3 = max(0.001, round(t3_elapsed - t2_elapsed, 3))
        d4 = max(0.001, round(t4_elapsed - t3_elapsed, 3))
        d5 = max(0.001, round(t5_elapsed - t4_elapsed, 3))

        turn_entry = {
            "turn": int(turn),
            "timestamp": int(time.time()),
            "time_str": time.strftime("%H:%M:%S"),
            "topic": topic or "ROUND_TABLE_DELIBERATION",
            "scope": scope or "CONTEXT_SCOPE_LONG",
            "turn_mode": "FULL_ROUND_TABLE",
            "is_full_round_table": True,
            "checkpoints_elapsed_s": {
                "triage": t1_elapsed,
                "pinky_stance": t2_elapsed,
                "brain_arch": t3_elapsed,
                "oracle": t4_elapsed,
                "pinky_judgment": t5_elapsed
            },
            "deltas_elapsed_s": {
                "triage": d1,
                "pinky_stance": d2,
                "brain_arch": d3,
                "oracle": d4,
                "pinky_judgment": d5
            },
            "cumulative": {
                "triage": t1_elapsed,
                "pinky_stance": t2_elapsed,
                "brain_arch": t3_elapsed,
                "oracle": t4_elapsed,
                "pinky_judgment": t5_elapsed
            },
            "deltas": {
                "triage": d1,
                "pinky_stance": d2,
                "brain_arch": d3,
                "oracle": d4,
                "pinky_judgment": d5
            },
            "total_elapsed_s": t5_elapsed,
            "total_s": t5_elapsed,
            "distillation_bullets": bullets if bullets else ["Live turn registered."],
            "consensus_1liner": consensus if consensus else "Consensus nominal."
        }

        records = []
        if os.path.exists(output_path):
            try:
                with open(output_path, "r") as f:
                    existing = json.load(f)
                    if isinstance(existing, list):
                        records = existing
            except Exception:
                records = []

        updated = False
        for idx, r in enumerate(records):
            if r.get("turn") == turn:
                records[idx] = turn_entry
                updated = True
                break
        if not updated:
            records.append(turn_entry)

        if len(records) > 50:
            records = records[-50:]

        tmp_path = f"{output_path}.tmp_{os.getpid()}"
        try:
            with open(tmp_path, "w") as f:
                json.dump(records, f, indent=2)
            os.replace(tmp_path, output_path)
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
        return turn_entry

    def commit_to_chroma(self, client=None, collection_name: str = "blackboard_ledger_dna"):
        """Non-fatal commit of blackboard events to ChromaDB."""
        try:
            if client is None:
                import chromadb
                client = chromadb.HttpClient(host="127.0.0.1", port=8001)
            col = client.get_or_create_collection(name=collection_name)
            for idx, c in enumerate(self.consensus_1liners):
                doc_id = f"bb_consensus_{c['turn']}_{int(c['ts'])}_{idx}"
                col.upsert(
                    ids=[doc_id],
                    documents=[c["consensus"]],
                    metadatas=[{"turn": c["turn"], "ts": c["ts"], "type": "consensus"}]
                )
        except Exception as e:
            logging.warning(f"[BLACKBOARD] Non-fatal ChromaDB sync failed: {e}")

# Backward-compatibility alias
BlackboardLedgerV2 = BlackboardLedger
