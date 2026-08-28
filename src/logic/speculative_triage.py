import asyncio
import logging
import socket

# [FEAT-486] Remote Kender (Ollama) endpoint used by the fast dual-check gate.
KENDER_HOST = "192.168.1.26"
KENDER_PORT = 11434
SOCKET_TIMEOUT_S = 0.2
API_PROBE_TIMEOUT_S = 0.6


def _probe_tcp(host: str, port: int, timeout: float = SOCKET_TIMEOUT_S) -> bool:
    """Return True if a TCP connect succeeds within *timeout* seconds."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


def _probe_ollama(host: str = KENDER_HOST, port: int = KENDER_PORT, timeout: float = API_PROBE_TIMEOUT_S) -> bool:
    """Return True if Kender TCP connects AND Ollama /api/tags responds within *timeout* seconds."""
    if not _probe_tcp(host, port, timeout=SOCKET_TIMEOUT_S):
        return False
    try:
        import urllib.request
        req = urllib.request.Request(f"http://{host}:{port}/api/tags", headers={"User-Agent": "AcmeLab/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as response:
            return response.status == 200
    except Exception:
        return False


class SpeculativeTriageRelay:
    """
    [SPR-64_1] Speculative Triage Relay with Kender Priority Window.
    Races Remote Kender (Ollama) and Local vLLM for the fastest triage JSON.
    [FEAT-486] A Dual-Check Gate (TCP + HTTP /api/tags) is applied at the front of relay():
    If the Remote Kender Ollama API is unreachable, the speculative head-start window (10.0s)
    is skipped entirely and local vLLM is dispatched with zero delay.
    If Kender Ollama is responsive, a 10.0s patient runway is granted to allow Kender
    to warm from idle disk sleep (~5.4s) + generate (~0.3s) without false timeouts.
    """
    def __init__(self, broadcast_callback, kender_fn, vllm_fn, t_warm=5.0,
                 kender_host=KENDER_HOST, kender_port=KENDER_PORT,
                 socket_timeout=SOCKET_TIMEOUT_S, api_timeout=API_PROBE_TIMEOUT_S):
        self.broadcast = broadcast_callback
        self.kender_fn = kender_fn
        self.vllm_fn = vllm_fn
        self.t_warm = t_warm
        self.head_start_window = 2 * t_warm
        self.kender_host = kender_host
        self.kender_port = kender_port
        self.socket_timeout = socket_timeout
        self.api_timeout = api_timeout

    async def relay(self, query, context, triage_schema, request_id="default"):
        """
        Execute the speculative relay.
        Returns (triage_dict, winner_name) or (None, None).
        """
        logging.info(f"[SPR-64_1] Initiating Speculative Relay (Head-start: {self.head_start_window}s)")

        # [FEAT-486] Dual-Check Gate: If Remote Kender or Ollama /api/tags is unreachable,
        # skip the speculative head-start window with ZERO delay and dispatch
        # local vLLM immediately. If responsive, grant 10.0s patient warmup runway.
        if not _probe_ollama(self.kender_host, self.kender_port, self.api_timeout):
            logging.info("[FEAT-486] Kender/Ollama unreachable. Fast dual-check gate: dispatching local vLLM with zero delay.")
            result = await self._run_vllm(query, context, triage_schema, request_id)
            if self._is_valid_triage(result):
                return result, "vllm"
            return None, None

        # 1. Launch Kender
        kender_task = asyncio.create_task(self._run_kender(query, context, triage_schema, request_id))
        
        # 2. Wait for head-start window
        done, pending = await asyncio.wait(
            [kender_task],
            timeout=self.head_start_window
        )
        
        # 3. If Kender finishes in head-start, it wins
        if done:
            try:
                result = done.pop().result()
                if self._is_valid_triage(result):
                    logging.info("[SPR-64_1] Kender won (Head-start completion)")
                    return result, "kender"
            except Exception as e:
                logging.warning(f"[SPR-64_1] Kender failed in head-start: {e}")
        
        # 4. Kender slow: Launch local vLLM
        logging.info("[SPR-64_1] Kender slow. Launching local vLLM candidate...")
        await self.broadcast({
            "type": "crosstalk",
            "brain": "[SPECULATIVE] Kender slow. Launching local vLLM candidate...",
            "brain_source": "System"
        })
        
        vllm_task = asyncio.create_task(self._run_vllm(query, context, triage_schema, request_id))
        
        # 5. Race the remaining tasks
        runners = [kender_task, vllm_task]
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
                        
                        winner = "vllm" if task is vllm_task else "kender"
                        logging.info(f"[SPR-64_1] {winner.upper()} won (Speculative race)")
                        return result, winner
                except Exception as e:
                    logging.warning(f"[SPR-64_1] Runner failed: {e}")
                    continue
                    
        return None, None

    async def _run_kender(self, query, context, triage_schema, request_id):
        return await self.kender_fn(query, context, triage_schema, request_id)

    async def _run_vllm(self, query, context, triage_schema, request_id):
        return await self.vllm_fn(query, context, triage_schema, request_id)

    def _is_valid_triage(self, result):
        if not isinstance(result, dict):
            return False
        # Check for essential triage fields
        required_fields = ["vibe", "addressed_to", "importance"]
        return all(field in result for field in required_fields)

    @staticmethod
    def get_console_metadata(winner):
        """
        Return channel/source metadata based on winner.
        """
        if winner == "kender":
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
