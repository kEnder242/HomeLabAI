import asyncio
import logging

class SpeculativeTriageRelay:
    """
    [SPR-64_1] Speculative Triage Relay with Kender Priority Window.
    Races Remote Kender (Ollama) and Local vLLM for the fastest triage JSON.
    """
    def __init__(self, broadcast_callback, kender_fn, vllm_fn, t_warm=1.25):
        self.broadcast = broadcast_callback
        self.kender_fn = kender_fn
        self.vllm_fn = vllm_fn
        self.t_warm = t_warm
        self.head_start_window = 2 * t_warm

    async def relay(self, query, context, triage_schema, request_id="default"):
        """
        Execute the speculative relay.
        Returns (triage_dict, winner_name) or (None, None).
        """
        logging.info(f"[SPR-64_1] Initiating Speculative Relay (Head-start: {self.head_start_window}s)")
        
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
                "source": "Brain (Insight)",
                "console": "Right"
            }
        else: # vllm
            return {
                "channel": "pinky",
                "source": "Pinky (Triage)",
                "console": "Left"
            }
