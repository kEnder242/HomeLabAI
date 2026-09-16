import os
import json
import logging
import socket
import urllib.request
import urllib.error
import requests
import asyncio
from typing import Dict, Any, List, Optional, Union

# [FEAT-531 / FEAT-500] Multi-Seat Sovereign Engine Infrastructure Client
SOCKET_TIMEOUT_S = 0.2
API_PROBE_TIMEOUT_S = 1.7
INFRA_CONFIG_PATH = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")

logger = logging.getLogger("engine_client")

def load_engine_seats() -> List[Dict[str, Any]]:
    """[FEAT-531] Load declarative engine seats from config/infrastructure.json."""
    try:
        if os.path.exists(INFRA_CONFIG_PATH):
            with open(INFRA_CONFIG_PATH, "r") as f:
                data = json.load(f)
                if "seats" in data and isinstance(data["seats"], list):
                    return data["seats"]
    except Exception as e:
        logger.warning(f"[ENGINE_CLIENT] Failed to load seats from infrastructure.json: {e}")
    
    # Declarative fallback ladder
    return [
        {
            "id": "M5_AIR",
            "name": "M5_AIR",
            "host": "192.168.1.46",
            "fallback_hosts": ["100.101.45.10", "jasons-macbook-air"],
            "port": 8000,
            "protocol": "OPENAI",
            "probe_path": "/v1/models",
            "probe_payload": None,
            "default_model": "mlx-community--Qwen3.5-9B-4bit",
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
            "default_model": "hf.co/unsloth/Qwen3-14B-GGUF:UD-Q4_K_XL",
            "t_warmed": 0.12,
            "t_cold": 1.2
        },
        {
            "id": "LOCAL",
            "name": "LOCAL",
            "host": "127.0.0.1",
            "port": 8088,
            "protocol": "OPENAI",
            "probe_path": "/v1/models",
            "probe_payload": None,
            "default_model": "shadow_brain_v2",
            "t_warmed": 0.045,
            "t_cold": 0.05
        }
    ]

def probe_tcp(host: str, port: int, timeout: float = SOCKET_TIMEOUT_S) -> bool:
    """[FEAT-486] 200ms non-blocking TCP socket check."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False

def probe_http(url: str, payload: Optional[dict] = None, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
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

def probe_seat(seat: Dict[str, Any]) -> bool:
    """[FEAT-531] Generic declarative seat health probe with Tailscale/multi-host fallback."""
    candidate_hosts = []
    primary_host = seat.get("host")
    if primary_host:
        candidate_hosts.append(primary_host)
    fallback_hosts = seat.get("fallback_hosts", [])
    if isinstance(fallback_hosts, list):
        for fh in fallback_hosts:
            if fh and fh not in candidate_hosts:
                candidate_hosts.append(fh)
    if not candidate_hosts:
        candidate_hosts = ["127.0.0.1"]

    port = seat.get("port", 80)
    probe_path = seat.get("probe_path", "/v1/models")
    payload = seat.get("probe_payload")
    t_probe = 2.0 * seat.get("t_cold", 0.85)

    for host in candidate_hosts:
        if probe_tcp(host, port, timeout=SOCKET_TIMEOUT_S):
            url = f"http://{host}:{port}{probe_path}"
            if probe_http(url, payload=payload, timeout=t_probe):
                seat["active_host"] = host
                return True
    return False

def resolve_active_deep_thought_target(seats: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    [FEAT-531] Declarative Multi-Seat Engine Resolver:
    Iterates through configured engine seats and selects the first active remote engine.
    If all remote seats fail, falls back to LOCAL vLLM.
    """
    if seats is None:
        seats = load_engine_seats()
    
    for seat in seats:
        if seat.get("id") == "LOCAL":
            continue
        if probe_seat(seat):
            return seat
            
    # Default fallback to LOCAL seat
    local_seat = next((s for s in seats if s.get("id") == "LOCAL"), {
        "id": "LOCAL",
        "name": "LOCAL",
        "host": "127.0.0.1",
        "port": 8088,
        "protocol": "OPENAI",
        "default_model": "shadow_brain_v2",
        "t_warmed": 0.045,
        "t_cold": 0.05
    })
    return local_seat

def query_sovereign_engine(
    prompt: str,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.2,
    timeout: float = 60.0,
    seats: Optional[List[Dict[str, Any]]] = None
) -> Optional[Union[dict, str]]:
    """
    [FEAT-500/531] Synchronous Multi-Seat Sovereign Engine Query with Automatic Cascading Fallback.
    """
    if seats is None:
        seats = load_engine_seats()

    # Build candidate ladder: tested active remote seats first, then local fallback
    candidates = []
    for s in seats:
        if s.get("id") != "LOCAL" and probe_seat(s):
            candidates.append(s)
    local_seat = next((s for s in seats if s.get("id") == "LOCAL"), None)
    if local_seat:
        candidates.append(local_seat)

    if not candidates:
        logger.error("[ENGINE_CLIENT] No candidate seats available.")
        return None

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    for seat in candidates:
        seat_id = seat.get("id", "UNKNOWN")
        host = seat.get("active_host") or seat.get("host", "127.0.0.1")
        port = seat.get("port", 80)
        protocol = seat.get("protocol", "OPENAI").upper()
        model = seat.get("default_model") or (seat.get("probe_payload", {}) or {}).get("model") or "default"

        try:
            if protocol in ["OPENAI", "VLLM"]:
                url = f"http://{host}:{port}/v1/chat/completions"
                payload = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature
                }
                if json_mode:
                    payload["response_format"] = {"type": "json_object"}

                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    if json_mode:
                        try:
                            return json.loads(raw_content)
                        except Exception:
                            # Try finding JSON substring if wrapped in markdown
                            import re
                            m = re.search(r"(\{.*\}|\[.*\])", raw_content, re.DOTALL)
                            if m:
                                return json.loads(m.group(1))
                    return raw_content
                else:
                    logger.warning(f"[ENGINE_CLIENT] Seat {seat_id} returned HTTP {resp.status_code}")

            elif protocol == "OLLAMA":
                url = f"http://{host}:{port}/api/chat"
                payload = {
                    "model": model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": temperature}
                }
                if json_mode:
                    payload["format"] = "json"

                resp = requests.post(url, json=payload, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    raw_content = data.get("message", {}).get("content", "")
                    if json_mode:
                        try:
                            return json.loads(raw_content)
                        except Exception:
                            import re
                            m = re.search(r"(\{.*\}|\[.*\])", raw_content, re.DOTALL)
                            if m:
                                return json.loads(m.group(1))
                    return raw_content
                else:
                    logger.warning(f"[ENGINE_CLIENT] Seat {seat_id} returned HTTP {resp.status_code}")

        except Exception as e:
            logger.warning(f"[ENGINE_CLIENT] Query to seat {seat_id} ({host}:{port}) failed: {e}. Cascading to next candidate...")

    logger.error("[ENGINE_CLIENT] All candidate seats exhausted without a successful generation.")
    return None

async def async_query_sovereign_engine(
    prompt: str,
    system_prompt: str = "",
    json_mode: bool = False,
    temperature: float = 0.2,
    timeout: float = 60.0,
    seats: Optional[List[Dict[str, Any]]] = None
) -> Optional[Union[dict, str]]:
    """
    [FEAT-500/531] Asynchronous Multi-Seat Sovereign Engine Query with Automatic Cascading Fallback.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: query_sovereign_engine(
            prompt=prompt,
            system_prompt=system_prompt,
            json_mode=json_mode,
            temperature=temperature,
            timeout=timeout,
            seats=seats
        )
    )
