import asyncio
import logging
import socket
import urllib.request

# [FEAT-500] Deep Thought Sovereign Multi-Seat Endpoints (Role-Hardware Decoupled)
DEEP_THOUGHT_TARGETS = [
    {
        "name": "M5_AIR",
        "host": "192.168.1.46",
        "port": 8000,
        "protocol": "OPENAI",
        "probe_path": "/v1/models"
    },
    {
        "name": "KENDER",
        "host": "192.168.1.26",
        "port": 11434,
        "protocol": "OLLAMA",
        "probe_path": "/api/tags"
    },
    {
        "name": "LOCAL",
        "host": "127.0.0.1",
        "port": 8088,
        "protocol": "VLLM",
        "probe_path": "/v1/models"
    }
]

SOCKET_TIMEOUT_S = 0.2
API_PROBE_TIMEOUT_S = 0.6
KENDER_HOST = "192.168.1.26"
KENDER_PORT = 11434


def _probe_tcp(host: str, port: int, timeout: float = SOCKET_TIMEOUT_S) -> bool:
    """Return True if a TCP connect succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _probe_http(url: str, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
    """Return True if HTTP endpoint returns 200 within *timeout* seconds."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "AcmeLab/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def _probe_ollama(host: str = "192.168.1.26", port: int = 11434, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
    """Legacy compatibility wrapper for Kender probe."""
    if not _probe_tcp(host, port, timeout=SOCKET_TIMEOUT_S):
        return False
    return _probe_http(f"http://{host}:{port}/api/tags", timeout=timeout)


def _probe_m5_air_vocal(host: str, port: int, timeout: float = 0.3) -> bool:
    """Return True if M5 Air responds to a 1-token vocal completion check within *timeout* seconds."""
    url = f"http://{host}:{port}/v1/chat/completions"
    payload = b'{"model":"mlx-community--Qwen3.8-27B-4bit","messages":[{"role":"user","content":"."}],"max_tokens":1}'
    try:
        req = urllib.request.Request(
            url,
            data=payload,
            headers={
                "User-Agent": "AcmeLab/5.0",
                "Content-Type": "application/json"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


def resolve_active_deep_thought_target(timeout: float = API_PROBE_TIMEOUT_S) -> dict:
    """
    [FEAT-500 / FEAT-502] Ping-First & Stick Multi-Seat Resolver:
    Probes M5 Air (:8000) with a 1-token vocal completion check first.
    If M5 Air returns an error or fails, falls back to Kender (:11434).
    If both remote seats fail, returns LOCAL (vLLM :8088).
    """
    # [FEAT-502] 1-token vocal completion check for M5 Air
    m5_air = DEEP_THOUGHT_TARGETS[0]
    if _probe_m5_air_vocal(m5_air["host"], m5_air["port"], timeout=0.3):
        return m5_air

    # Fallback to Kender (TCP + HTTP probe)
    kender = DEEP_THOUGHT_TARGETS[1]
    if _probe_tcp(kender["host"], kender["port"], timeout=SOCKET_TIMEOUT_S):
        if _probe_http(f"http://{kender['host']}:{kender['port']}{kender['probe_path']}", timeout=timeout):
            return kender

    return DEEP_THOUGHT_TARGETS[-1]  # Fallback to LOCAL


class SpeculativeTriageRelay:
    """
    [SPR-67_0 / FEAT-500] Speculative Triage Relay with Dynamic Deep Thought Multi-Seat Resolution.
    Races Sovereign Deep Thought (M5 Air / Kender) and Local vLLM for the fastest triage JSON.
    [FEAT-486 / FEAT-500] A Dual-Check Gate probes M5 Air first, then Kender:
    If a remote Deep Thought target is reachable, a 10.0s patient warmup runway is granted.
    If remote seats are unreachable, the head-start window is skipped with zero delay
    and local vLLM is dispatched immediately.
    """
    def __init__(self, broadcast_callback, deep_thought_fn=None, vllm_fn=None, t_warm=5.0,
                 kender_fn=None, socket_timeout=SOCKET_TIMEOUT_S, api_timeout=API_PROBE_TIMEOUT_S):
        self.broadcast = broadcast_callback
        self.deep_thought_fn = deep_thought_fn or kender_fn
        self.kender_fn = self.deep_thought_fn # backward compatibility
        self.vllm_fn = vllm_fn
        self.t_warm = t_warm
        self.head_start_window = 2 * t_warm
        self.socket_timeout = socket_timeout
        self.api_timeout = api_timeout

    async def relay(self, query, context, triage_schema, request_id="default"):
        """
        Execute the speculative relay.
        Returns (triage_dict, winner_name) or (None, None).
        """
        logging.info(f"[SPR-67_0] Initiating Speculative Relay (Head-start: {self.head_start_window}s)")

        # [FEAT-500] Dual-Check Gate: Check if remote Deep Thought (M5 Air or Kender) is live
        active_target = resolve_active_deep_thought_target(self.api_timeout)
        target_name = active_target["name"]

        if target_name == "LOCAL":
            logging.info("[FEAT-500] Remote Deep Thought seats unreachable. Fast dual-check gate: dispatching local vLLM with zero delay.")
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
