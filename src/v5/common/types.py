import os
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Optional
import time

# [Task 17.3] Single Source of Versioning
LAB_VERSION = "5.0.0-foyer"

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
    version: str = LAB_VERSION
    vram_used: int = 0
    vram_total: int = 0
    ram_pct: float = 0.0
    engine_up: bool = False
    vocal: bool = False
    nodes: Dict[str, NodeStatus] = field(default_factory=dict)
    active_intent_id: Optional[str] = None

    def to_dict(self):
        # [Task 9.7] UI Compatibility Layer (V3 -> V5 Bridge)
        vram_pct = (self.vram_used / self.vram_total * 100) if self.vram_total > 0 else 0
        
        # Discover style key
        style_key = "38637b40" # Fallback
        try:
            workspace = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
            style_path = os.path.join(workspace, "field_notes/style.css")
            if os.path.exists(style_path):
                import hashlib
                with open(style_path, "rb") as f:
                    style_key = hashlib.md5(f.read()).hexdigest()[:8]
        except Exception: pass

        return {
            "state": self.state,
            "status": "ONLINE" if self.state == "OPERATIONAL" else (
                "HIBERNATING (VRAM Free)" if self.state == "HIBERNATING" else self.state
            ),
            "message": "Systems Nominal" if self.state == "OPERATIONAL" else "Lab Hibernating",
            "timestamp": time.strftime("%H:%M:%S", time.localtime(self.timestamp)),
            "version": self.version,
            "vram_used": self.vram_used,
            "vram_total": self.vram_total,
            "ram_pct": self.ram_pct,
            "engine_up": self.engine_up,
            "vocal": self.vocal,
            "nodes": {k: asdict(v) for k, v in self.nodes.items()},
            "active_intent_id": self.active_intent_id,
            "vitals": {
                "mode": self.state,
                "model": "Llama-3.2-3B-AWQ" if self.engine_up else "-",
                "vram": f"{vram_pct:.1f}%",
                "ram": f"{self.ram_pct:.1f}%",
                "intercom": "ONLINE" if self.vocal else "OFFLINE",
                "brain": "ONLINE" if self.engine_up else "OFFLINE",
                "session": self.active_intent_id or "standby",
                "style_key": style_key
            }
        }
