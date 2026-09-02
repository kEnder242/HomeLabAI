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
