import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional
import time

# [Task 4.1] V5 Common: Unified types for the Modular Suite

@dataclass
class IntentEvent:
    query: str
    source: str
    timestamp: float = field(default_factory=time.time)
    status: str = "PENDING"
    id: str = field(default_factory=lambda: os.urandom(4).hex())
    metadata: Dict = field(default_factory=dict)

    def to_json(self):
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, data_str):
        data = json.loads(data_str)
        return cls(**data)

@dataclass
class NodeStatus:
    name: str
    online: bool = False
    pid: Optional[int] = None
    vram_mib: int = 0
    role: str = ""

@dataclass
class LabStatus:
    state: str = "HIBERNATING"
    timestamp: float = field(default_factory=time.time)
    version: str = "5.0.0-appliance"
    vram_used: int = 0
    vram_total: int = 0
    engine_up: bool = False
    vocal: bool = False
    nodes: Dict[str, NodeStatus] = field(default_factory=dict)
    active_intent_id: Optional[str] = None

    def to_dict(self):
        return {
            "state": self.state,
            "timestamp": self.timestamp,
            "version": self.version,
            "vram_used": self.vram_used,
            "vram_total": self.vram_total,
            "engine_up": self.engine_up,
            "vocal": self.vocal,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "active_intent_id": self.active_intent_id
        }
