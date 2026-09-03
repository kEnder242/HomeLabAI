import asyncio
import json
import logging
import os
import socket
import urllib.request
from typing import Dict, Any, List, Optional

SOCKET_TIMEOUT_S = 0.2
API_PROBE_TIMEOUT_S = 1.7  # [FEAT-531] 2x Rule for Cold Probe (2 * 0.85s)
KENDER_HOST = "192.168.1.26"
KENDER_PORT = 11434

def _load_engine_seats() -> List[Dict[str, Any]]:
    """[FEAT-531] Load declarative engine seats from config/infrastructure.json."""
    config_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = json.load(f)
                if "seats" in data:
                    return data["seats"]
    except Exception as e:
        logging.warning(f"[SPECULATIVE] Failed to load seats from infrastructure.json: {e}")
    
    # Fallback default seats
    return [
        {
            "id": "M5_AIR",
            "name": "M5_AIR",
            "host": "192.168.1.46",
            "port": 8000,
            "protocol": "OPENAI",
            "probe_path": "/v1/chat/completions",
            "probe_payload": {"model": "mlx-community--Qwen3.8-27B-4bit", "messages": [{"role": "user", "content": "."}], "max_tokens": 1},
            "t_warmed": 0.09,
            "t_cold": 0.85
        },
        {
            "id": "KENDER",
            "name": "KENDER",
            "host": "192.168.1.26",
            "port": 11434,
            "protocol": "OLLAMA",
            "probe_path": "/api/tags",
            "probe_payload": None,
            "t_warmed": 0.12,
            "t_cold": 1.2
        },
        {
            "id": "LOCAL",
            "name": "LOCAL",
            "host": "127.0.0.1",
            "port": 8088,
            "protocol": "VLLM",
            "probe_path": "/v1/models",
            "probe_payload": None,
            "t_warmed": 0.045,
            "t_cold": 0.05
        }
    ]

def _probe_tcp(host: str, port: int, timeout: float = SOCKET_TIMEOUT_S) -> bool:
    """Return True if a TCP connect succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False

def _probe_http(url: str, payload: Optional[dict] = None, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
    """Return True if HTTP endpoint returns 200 within *timeout* seconds."""
    try:
        if payload:
            data_bytes = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data_bytes,
                headers={"User-Agent": "AcmeLab/5.0", "Content-Type": "application/json"},
                method="POST"
            )
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "AcmeLab/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False

def _probe_seat(seat: Dict[str, Any]) -> bool:
    """[FEAT-531] Generic declarative seat health probe."""
    host = seat.get("host", "127.0.0.1")
    port = seat.get("port", 80)
    if not _probe_tcp(host, port, timeout=SOCKET_TIMEOUT_S):
        return False
    
    probe_path = seat.get("probe_path", "/v1/models")
    url = f"http://{host}:{port}{probe_path}"
    payload = seat.get("probe_payload")
    # 2x Rule: Probe timeout is 2 * t_cold
    t_probe = 2.0 * seat.get("t_cold", 0.85)
    return _probe_http(url, payload=payload, timeout=t_probe)

def resolve_active_deep_thought_target(seats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    [FEAT-531] Declarative Multi-Seat Engine Resolver:
    Iterates through configured engine seats and selects the first active remote engine.
    If all remote seats fail, falls back to LOCAL vLLM.
    """
    if seats is None:
        seats = _load_engine_seats()
    
    for seat in seats:
        if seat.get("id") == "LOCAL":
            continue
        if _probe_seat(seat):
            return seat
            
    # Default fallback to LOCAL seat
    local_seat = next((s for s in seats if s.get("id") == "LOCAL"), {
        "id": "LOCAL",
        "name": "LOCAL",
        "host": "127.0.0.1",
        "port": 8088,
        "protocol": "VLLM",
        "t_warmed": 0.045,
        "t_cold": 0.05
    })
    return local_seat


class SpeculativeTriageRelay:
    """
    [SPR-67_0 / FEAT-500] Speculative Triage Relay with Dynamic Deep Thought Multi-Seat Resolution.
    Races Sovereign Deep Thought (M5 Air / Kender) and Local vLLM for the fastest triage JSON.
    [FEAT-486 / FEAT-500] A Dual-Check Gate probes M5 Air first, then Kender:
    If a remote Deep Thought target is reachable, a 10.0s patient warmup runway is granted.
    If remote seats are unreachable, the head-start window is skipped with zero delay
    and local vLLM is dispatched immediately.
    """
    def __init__(self, broadcast_callback, deep_thought_fn=None, vllm_fn=None, t_warmed=0.09,
                 kender_fn=None, socket_timeout=SOCKET_TIMEOUT_S, api_timeout=API_PROBE_TIMEOUT_S):
        self.broadcast = broadcast_callback
        self.deep_thought_fn = deep_thought_fn or kender_fn
        self.kender_fn = self.deep_thought_fn # backward compatibility
        self.vllm_fn = vllm_fn
        self.t_warmed = t_warmed
        # [FEAT-531] 2x Rule for Warmed Speculative Head-Start Window (2 * 0.09s = 0.18s)
        self.head_start_window = 2 * t_warmed
        self.socket_timeout = socket_timeout
        self.api_timeout = api_timeout

    async def relay(self, query, context, triage_schema, request_id="default"):
        """
        Execute the speculative relay.
        Returns (triage_dict, winner_name) or (None, None).
        """
        # [FEAT-531] Declarative Multi-Seat Resolution
        active_target = resolve_active_deep_thought_target()
        target_name = active_target["name"]
        t_warmed_seat = active_target.get("t_warmed", self.t_warmed)
        self.head_start_window = 2 * t_warmed_seat
        logging.info(f"[FEAT-531] Initiating Speculative Relay (Target: {target_name}, Head-start: {self.head_start_window:.3f}s)")

        if target_name == "LOCAL":
            logging.info("[FEAT-531] Remote Deep Thought seats unreachable. Fast dual-check gate: dispatching local vLLM with zero delay.")
            result = await self._run_vllm(query, context, triage_schema, request_id)
            if self._is_valid_triage(result):
                return result, "vllm"
            return None, None

        logging.info(f"[FEAT-500] Deep Thought target resolved: {target_name} ({active_target['host']}:{active_target['port']})")

        # 1. Launch Deep Thought
        dt_task = asyncio.create_task(self._run_deep_thought(query, context, triage_schema, request_id))
        
        # 2. Wait for head-start window
        done, pending = await asyncio.wait(
            [dt_task],
            timeout=self.head_start_window
        )
        
        # 3. If Deep Thought finishes in head-start, it wins
        if done:
            try:
                result = done.pop().result()
                if self._is_valid_triage(result):
                    logging.info(f"[SPR-67_0] Deep Thought ({target_name}) won (Head-start completion)")
                    return result, "deep_thought"
            except Exception as e:
                logging.warning(f"[SPR-67_0] Deep Thought failed in head-start: {e}")
        
        # 4. Deep Thought slow: Launch local vLLM
        logging.info(f"[SPR-67_0] Deep Thought ({target_name}) slow. Launching local vLLM candidate...")
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"[SPECULATIVE] Deep Thought ({target_name}) slow. Launching local vLLM candidate...",
            "brain_source": "System"
        })
        
        vllm_task = asyncio.create_task(self._run_vllm(query, context, triage_schema, request_id))
        
        # 5. Race the remaining tasks
        runners = [dt_task, vllm_task]
        while runners:
            done, runners = await asyncio.wait(runners, return_when=asyncio.FIRST_COMPLETED)
            
            for task in done:
                try:
                    result = task.result()
                    if self._is_valid_triage(result):
                        # Cancel the other runner
                        for r in runners:
                            if not r.done():
                                r.cancel()
                        
                        winner = "vllm" if task is vllm_task else "deep_thought"
                        logging.info(f"[SPR-67_0] {winner.upper()} won (Speculative race)")
                        return result, winner
                except Exception as e:
                    logging.warning(f"[SPR-67_0] Runner failed: {e}")
                    continue
                    
        return None, None

    async def _run_deep_thought(self, query, context, triage_schema, request_id):
        if self.deep_thought_fn:
            return await self.deep_thought_fn(query, context, triage_schema, request_id)
        return None

    async def _run_kender(self, query, context, triage_schema, request_id):
        return await self._run_deep_thought(query, context, triage_schema, request_id)

    async def _run_vllm(self, query, context, triage_schema, request_id):
        return await self.vllm_fn(query, context, triage_schema, request_id)

    def _is_valid_triage(self, result):
        if not isinstance(result, dict):
            return False
        # [FEAT-518] Reject transient warming objects
        situation_str = str(result.get("situation", "")).lower()
        hint_str = str(result.get("hints", "")).lower()
        if "warming" in situation_str or "warming" in hint_str:
            return False
        # Check for essential triage fields
        required_fields = ["vibe", "addressed_to", "importance"]
        return all(field in result for field in required_fields)

    @staticmethod
    def get_console_metadata(winner):
        """
        Return channel/source metadata based on winner.
        """
        if winner in ["kender", "deep_thought", "m5_air"]:
            return {
                "channel": "insight",
                "source": "Deep Thought (Triage)",
                "console": "Right"
            }
        else: # vllm
            return {
                "channel": "chat",
                "source": "Lab (Triage)",
                "console": "Left"
            }
