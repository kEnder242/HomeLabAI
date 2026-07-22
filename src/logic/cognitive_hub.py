import asyncio
import json
import logging
import os
import re
import time
import random
from v5.common.types import LAB_VERSION

# [FEAT-T20.2] Lazy import — avoids hard dep if DCGM is absent
def _get_telemetry_collector():
    try:
        from infra.telemetry_collector import get_collector
        return get_collector()
    except Exception:
        return None

# [Task 4.2] V5 Cognitive Hub: The Logical Core
# Objective: Manage multi-node reasoning waterfall and strategic routing.

class CognitiveHub:


    def __init__(self, residents, broadcast_callback, sensory_manager, get_vram_status, trigger_morning_briefing, last_prime_callback=None, waterfall_queue=None, hibernate_callback=None, set_active_domain=None):
        from collections import defaultdict
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.get_vram_status = get_vram_status
        self.trigger_morning_briefing_cb = trigger_morning_briefing
        self.last_prime_callback = last_prime_callback
        self.waterfall_queue = waterfall_queue # [FEAT-233.2] Internal Token Buffer
        self.hibernate_callback = hibernate_callback
        self.set_active_domain = set_active_domain

        self.session_buffers = defaultdict(str)
        self.active_intent = None
        self.current_interest = 0.0
        self._boosted_interest = False
        self.current_topic = "INTERFACE"
        self.last_activity = time.time()
        
        # [SPR-41_2] Context Starvation tracking: nodes that returned [ERROR: CONTEXT_STARVED]
        self.context_starved_nodes = set()
        
        # [FEAT-356] Foil-Aware Memory (Unified Session Ledger)
        self.round_table_memory = []
        self.turn_thought_trace = {}
        
        # [Task 6.3] Hygiene: Process Tracking
        self.processed_ids = set()
        self.request_lock = asyncio.Lock()
        
        # [FEAT-350] Gibberish Guard: Stable Baseline
        self.consecutive_parse_failures = 0
        self.lora_enabled = True
        self.triage_failures = 0 # [FEAT-270] Track consecutive failures
        
        # [FEAT-181] Semantic Integration
        self.semantic_map_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/semantic_map.json")
        self.semantic_map = {}
        if os.path.exists(self.semantic_map_path):
            try:
                with open(self.semantic_map_path, "r") as f:
                    self.semantic_map = json.load(f)
            except Exception:
                pass
        
        # [BKM-015] Role Token Routing: Load tokens from config/role_tokens.json
        # Script-relative path: HomeLabAI/src/logic/ → ../../config/
        self._config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        self._role_tokens_path = os.path.join(self._config_dir, "role_tokens.json")
        self.role_tokens = {}
        if os.path.exists(self._role_tokens_path):
            try:
                with open(self._role_tokens_path, "r") as f:
                    self.role_tokens = json.load(f)
            except Exception:
                pass

        # [BKM-015] Token → routing override map.
        # Tokens live in config/role_tokens.json (single source of truth);
        # routing targets are pre-defined per the role token contract.
        self._token_routes = {
            "<|PINKY|>":   {"addressed_to": "PINKY",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.5, "casual": 0.3, "intrigue": 0.5},
            "<|BRAIN|>":   {"addressed_to": "BRAIN",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8, "casual": 0.1, "intrigue": 0.7},
            "<|THOUGHT|>": {"addressed_to": "BRAIN",  "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8, "casual": 0.1, "intrigue": 0.7},
        }

        self.auditor = None  # [FEAT-190] The Judge

        # [FEAT-T20.2] Wire telemetry callback on each BicameralNode resident
        self._tel_collector = _get_telemetry_collector()
        for node in self.residents.values():
            if hasattr(node, '_on_telemetry'):
                node._on_telemetry = self._collect_telemetry
            # Also wire on the underlying BicameralNode if wrapped
            underlying = getattr(node, '_node', node)
            if underlying is not node and hasattr(underlying, '_on_telemetry'):
                underlying._on_telemetry = self._collect_telemetry

    def _wrap_residents_for_sandbox(self):
        """[Task 1.3] Wraps call_tool and list_tools on all resident sessions to enforce sandbox."""
        for name, session in self.residents.items():
            # Handle mock objects in test environments
            is_mock = "Mock" in type(session).__name__
            
            if is_mock:
                # Store original methods if not already stored
                if "_original_call_tool" not in session.__dict__:
                    session._original_call_tool = session.call_tool
                    session._original_list_tools = session.list_tools
                
                async def wrapped_call_tool(tool_name, arguments=None, *, session_ref=session, **kwargs):
                    vibe = getattr(self, "current_vibe", "TECHNICAL")
                    if vibe != "META":
                        blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                        if any(kw in tool_name.lower() for kw in blocked_keywords):
                            raise ValueError(f"Tool '{tool_name}' blocked by Sandbox: Current vibe is '{vibe}' (requires 'META')")
                    return await session_ref._original_call_tool(tool_name, arguments=arguments, **kwargs)
                    
                async def wrapped_list_tools(*args, session_ref=session, **kwargs):
                    resp = await session_ref._original_list_tools(*args, **kwargs)
                    vibe = getattr(self, "current_vibe", "TECHNICAL")
                    if vibe != "META":
                        blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                        if hasattr(resp, "tools"):
                            resp.tools = [t for t in resp.tools if not any(kw in t.name.lower() for kw in blocked_keywords)]
                    return resp
                
                from unittest.mock import AsyncMock
                session.call_tool = AsyncMock(side_effect=wrapped_call_tool)
                session.list_tools = AsyncMock(side_effect=wrapped_list_tools)
            else:
                if "_original_call_tool" not in session.__dict__:
                    # Use object.__setattr__ to bypass mock or custom descriptors
                    object.__setattr__(session, "_original_call_tool", session.call_tool)
                    object.__setattr__(session, "_original_list_tools", session.list_tools)
                    
                    async def wrapped_call_tool(tool_name, arguments=None, *, session_ref=session, **kwargs):
                        vibe = getattr(self, "current_vibe", "TECHNICAL")
                        if vibe != "META":
                            blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                            if any(kw in tool_name.lower() for kw in blocked_keywords):
                                raise ValueError(f"Tool '{tool_name}' blocked by Sandbox: Current vibe is '{vibe}' (requires 'META')")
                        return await session_ref._original_call_tool(tool_name, arguments=arguments, **kwargs)
                        
                    async def wrapped_list_tools(*args, session_ref=session, **kwargs):
                        resp = await session_ref._original_list_tools(*args, **kwargs)
                        vibe = getattr(self, "current_vibe", "TECHNICAL")
                        if vibe != "META":
                            blocked_keywords = ["git", "systemd", "systemctl", "state_machine", "close_lab", "bounce_node", "lab_train_adapter"]
                            if hasattr(resp, "tools"):
                                resp.tools = [t for t in resp.tools if not any(kw in t.name.lower() for kw in blocked_keywords)]
                        return resp
                        
                    object.__setattr__(session, "call_tool", wrapped_call_tool)
                    object.__setattr__(session, "list_tools", wrapped_list_tools)

    async def handle_stream_token(self, data):
        """[FEAT-233.2] Ingests token into session buffers and audits for vetoes."""
        raw_source = str(data.get("brain_source", data.get("source", "Unknown"))).lower()
        
        # [Task 14.3] Map raw node names to UI-friendly display names
        display_map = {
            "lab": "Lab (Triage)",
            "pinky": "Pinky (Response)",
            "brain": "Brain (Archive)",
            "thought": "Deep Thought"
        }
        source = display_map.get(raw_source, raw_source)
        data["brain_source"] = source
        
        token = data.get("brain", "")
        # Extract request ID if present
        request_id = data.get("request_id", "default")
        buf_key = f"{request_id}_{raw_source}"

        # [NEW] Push to waterfall queue for real-time UI delivery
        # [FEAT-361] 100% Transparency: No masking of inter-node whispers.
        if hasattr(self, 'waterfall_queue') and self.waterfall_queue:
            await self.waterfall_queue.put(data)

        if token:
            self.session_buffers[buf_key] += token
            # Audit for dynamic interjections if importance is high
            if self.current_interest > 0.8:
                await self._check_dynamic_audit(source, token)

    def bridge_signal_clean(self, text):
        """[FEAT-145] Cleans the raw LLM output for valid JSON blocks."""
        if not text:
            return None
        
        if "{" not in text:
            # [FIX] Silence [RAW_OUTPUT] for connection errors to reduce UI noise
            is_connection_error = "vLLM connection failed" in text or "Error:" in text
            if not is_connection_error:
                msg = f"[RAW_OUTPUT] Missing JSON anchor. Text: {text[:200]}..."
                logging.warning(f"[HUB] {msg}")
                asyncio.create_task(self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"}))
            return None

        # [FEAT-347] Nuclear JSON Extractor: Multi-block match for 3B resilience
        # This handles cases where models output multiple blocks or trailing garbage.
        json_blocks = re.findall(r'(\{.*?\})', text, re.DOTALL)
        if not json_blocks:
            # Fallback to greedy if non-greedy fails
            match = re.search(r'(\{.*\})', text, re.DOTALL)
            if match:
                json_blocks = [match.group(1)]
            else:
                return None

        # Find the first block that contains valid triage fields
        for block in json_blocks:
            try:
                data = json.loads(block)
                if "intent" in data or "vibe" in data or "addressed_to" in data:
                    return data
            except Exception:
                continue
        return None

    async def monitor_task_with_tics(self, coro, node_id="lab"):
        """[FEAT-267] Display periodic 'Tics' (e.g., Narf!) during long node runs."""
        task = asyncio.create_task(coro)
        
        # Start a background tic broadcaster
        async def _tic_loop():
            current_delay = 5.0
            while not task.done():
                try:
                    await asyncio.sleep(current_delay)
                    if task.done():
                        break
                        
                    # Request a context-aware tic/quip from the Lab node
                    tic_msg = ""
                    # Persona definition
                    persona = "Pinky (character-faithful tic)" if node_id.lower() == "pinky" else "Deep Thought (analytical thinking response)"
                    
                    try:
                        tic_res = await self.residents["lab"].call_tool("think", {
                            "query": f"[SYSTEM_TIC]: Provide a {persona} for the Lab's current state.",
                            "temperature": 0.8
                        })
                        tic_msg = tic_res.content[0].text
                    except Exception:
                        pass

                    if not tic_msg:
                        # Fallback to base persona tics/quips
                        if node_id.lower() == "pinky":
                            tic_msg = random.choice(["Narf!", "Poit!", "Zort!", "Egad!", "Troz!"])
                        else:
                            tic_msg = "Analyzing parameters... deep thought in progress."

                    try:
                        await self.broadcast({
                            "type": "crosstalk",
                            "brain": tic_msg,
                            "brain_source": node_id.capitalize(),
                            "channel": "insight" if node_id.lower() in ["brain", "thought"] else "chat",
                            "final": False,
                            "version": LAB_VERSION
                        })
                        # Exponential backoff for tics to avoid spamming
                        current_delay = min(current_delay * 1.5, 15.0)
                    except Exception:
                        if task.done():
                            break
                        await asyncio.sleep(1.0)
                except Exception:
                    break
        
        asyncio.create_task(_tic_loop())
        return await task

    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, interest_threshold=0.0, temperature=0.0, repetition_penalty=1.1, retry_count=0, use_lora=True, response_format=None, request_id="default"):
        """[FEAT-233.5] Internal Waterfall Proxy: Handshakes the node and yields tokens."""
        if hasattr(self, "round_table_memory") and self.round_table_memory:
            debate_context = "\n\n[PREVIOUS_DEBATE]:\n" + "\n".join(self.round_table_memory)
            if "[PREVIOUS_DEBATE]" not in query:
                query += debate_context

        if node_id not in self.residents:
            return
        
        # [Task 12.7] Ensure response_format is valid for Pydantic
        if response_format is None:
            response_format = {}

        # [FEAT-242.1] Handshake Tic (Gated via FEAT-365)
        enabled = True
        try:
             # Heuristic: Find config from the 'lab' resident if available
             if "lab" in self.residents and hasattr(self.residents["lab"], "config"):
                  enabled = self.residents["lab"].config.get("enable_reflexes", True)
        except Exception:
             pass

        if enabled:
            channel = "insight" if "brain" in source_name.lower() or "thought" in source_name.lower() else "chat"
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Initiating {source_name} intuition...",
                "brain_source": source_name,
                "final": False,
                "channel": channel
            })

        try:
            # [Task 2.3] Persona Interest: Adjust behavioral density based on scalar
            stance = ""
            if self.current_interest > 0.75:
                stance = "\n[STANCE]: ACADEMIC (Evidence-heavy, dense, refer to GEM/SCAR IDs)."
            elif self.current_interest < 0.3:
                stance = "\n[STANCE]: INTERFACE (Witty, character-first, high brevity)."
            
            guidance = stance
            if behavioral_guidance:
                guidance += f"\n[BEHAVIORAL_GUIDANCE]: {behavioral_guidance}"

            # [FEAT-407] Vibe-Specific Context Isolation: Wrap RAG context in
            # <historical_record> tags + inject GROUNDING_PROTOCOL for HISTORICAL/FORENSIC/TECHNICAL vibes.
            # Prevents bedrock/operational metadata bleed into past-tense briefs.
            _vibe = getattr(self, "current_vibe", "TECHNICAL")
            if _vibe.upper() in ("HISTORICAL", "FORENSIC", "TECHNICAL") and context:
                context = f"<historical_record>\n{context}\n</historical_record>"
                guidance += "\nGROUNDING_PROTOCOL: Formulate your response EXCLUSIVELY from the evidence provided inside the <historical_record> tags. Focus your analysis solely on the target events, dates, and validation systems described within these tags."

            # [Task 1.1] Spark the node and wait for full block
            node = self.residents[node_id]
            
            # [Task 9.1] Isolated Buffer Key
            name_map = {"lab": "lab", "pinky": "pinky", "brain": "brain", "thought": "deep thought"}
            src_key = name_map.get(node_id, node_id)
            buf_key = f"{request_id}_{src_key}"
            self.session_buffers[buf_key] = ""
            
            # [Task 9.2] Hub relies on the Node's telemetry queue to populate the Foyer drainer.
            call_task = asyncio.create_task(node.call_tool("think", arguments={
                "query": query, "context": context, "tools": tools or [], 
                "behavioral_guidance": guidance,
                "temperature": temperature, "repetition_penalty": repetition_penalty,
                "use_lora": use_lora, "response_format": response_format, 
                "request_id": request_id
            }))
            
            full_text = ""
            last_len = 0
            while not call_task.done():
                await asyncio.sleep(0.05)
                curr_buffer = self.session_buffers[buf_key]
                if len(curr_buffer) > last_len:
                    new_tokens = curr_buffer[last_len:]
                    full_text += new_tokens
                    
                    # Check for peer-vote interest boosting signals [FEAT-238]
                    if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                        self._boosted_interest = True
                        old_interest = self.current_interest
                        self.current_interest = min(1.0, self.current_interest + 0.3)
                        logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                        
                    yield new_tokens
                    last_len = len(curr_buffer)
                    
                    # [FEAT-404] Context Starvation check: abort immediately if starvation detected
                    if "[ERROR: CONTEXT_STARVED]" in full_text:
                        logging.warning(f"[HUB] Context starvation detected mid-stream for {node_id}. Aborting.")
                        call_task.cancel()
                        break
                    
            # Get the final result and any remaining buffer
            try:
                res = await call_task
            except asyncio.CancelledError:
                res = "[ERROR: CONTEXT_STARVED]"
            curr_buffer = self.session_buffers[buf_key]
            if len(curr_buffer) > last_len:
                new_tokens = curr_buffer[last_len:]
                full_text += new_tokens
                
                # Check for peer-vote interest boosting signals [FEAT-238]
                if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                    self._boosted_interest = True
                    old_interest = self.current_interest
                    self.current_interest = min(1.0, self.current_interest + 0.3)
                    logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                    
                yield new_tokens
                
            # If the node didn't stream anything (e.g. error or missing logic), fallback to the full response
            if not full_text:
                if hasattr(res, 'content') and len(res.content) > 0:
                    full_text = res.content[0].text
                else:
                    full_text = str(res)
                
                # Check for peer-vote interest boosting signals [FEAT-238]
                if ("<boost_interest>" in full_text or "<upvote>" in full_text) and not self._boosted_interest:
                    self._boosted_interest = True
                    old_interest = self.current_interest
                    self.current_interest = min(1.0, self.current_interest + 0.3)
                    logging.info(f"[HUB] [FEAT-238] Council of Hemispheres: Node {node_id} boosted interest from {old_interest:.2f} to {self.current_interest:.2f}.")
                    
                yield full_text
            
            # [SPR-41_2] Context Starvation Detection: if node returned CONTEXT_STARVED, bypass cascade
            if "[ERROR: CONTEXT_STARVED]" in full_text:
                self.context_starved_nodes.add(node_id)
                source_display = source_name or node_id
                logging.warning(f"[HUB] {source_display} returned CONTEXT_STARVED token.")
                await self.broadcast({
                    "type": "crosstalk",
                    "brain": f"[HUB] ⚠ Context Starvation detected from {source_display}. Cascade bypassed.",
                    "brain_source": "System"
                })
            
            self.turn_thought_trace[node_id] = full_text
            if node_id == "thought":
                self.turn_thought_trace["brain"] = full_text
            self.session_buffers[buf_key] = "" # Clear buffer
            
            # [FEAT-287] Activity Latch
            if node_id in ["brain", "thought"]:
                self.last_activity = time.time()
                if hasattr(self, 'last_prime_callback') and self.last_prime_callback:
                    self.last_prime_callback(time.time())
            
            # [Task 14.2] Drainer Primacy: Removed execute_dispatch(). 
            # The Foyer's waterfall_drainer handles the final Pop delivery.
            
        except Exception as e:
            logging.error(f"[HUB] Stream from {node_id} failed: {e}")

    async def execute_dispatch(self, text, source_name, shutdown_event=None, retry_count=0, final=False):
        """Dispatches a finalized block to the UI."""
        await self.broadcast({
            "type": "chat",
            "brain": text,
            "brain_source": source_name,
            "final": final
        })

    async def _check_dynamic_audit(self, source, token):
        """Placeholder for FEAT-190 The Judge."""
        pass

    def _collect_telemetry(self, event: dict) -> None:
        """
        [FEAT-T20.1/T20.2] Telemetry collector callback.
        Called by BicameralNode._emit_telemetry() at end of generation.
        Enriches with live GPU snapshot and writes to ledger.
        """
        if not self._tel_collector:
            return
        try:
            sample = self._tel_collector.snapshot(
                node=event.get("node", ""),
                request_id=event.get("request_id", "default"),
            )
            # Overlay token-level metrics from the node
            sample.ttft_ms = event.get("ttft_ms", 0.0)
            sample.total_tokens = event.get("total_tokens", 0)
            sample.duration_s = event.get("duration_s", 0.0)
            sample.engine_type = event.get("engine_type", "")
            sample.model = event.get("model", "")
            sample.enrich_economics()
            self._tel_collector.write_ledger(sample)
            logging.debug(
                f"[TEL] {sample.node} | TTFT={sample.ttft_ms:.0f}ms "
                f"tps={sample.tokens_per_sec:.1f} "
                f"power={sample.gpu_power_w:.0f}W "
                f"J/tok={sample.joules_per_token:.4f}"
            )
        except Exception as e:
            logging.debug(f"[TEL] Collect failed: {e}")

    async def process_query(self, turn, shutdown_event=None, request_id=None, trigger_briefing_callback=None):
        """[FEAT-145] Main Reasoning Waterfall."""
        self.turn_thought_trace = {}
        if request_id is None:
            import uuid
            request_id = uuid.uuid4().hex[:8]
        
        # [NEW] Unified Early Priming
        logging.info(f"[PRIME] Spawning priming task for: {turn[:20]}")
        asyncio.create_task(self._prime_first_try(turn))
        
        # [SPR-41_2] Reset context starvation tracker per query
        self.context_starved_nodes.clear()
        
        # Initialize default vibe for Sandbox Tool Isolation
        self.current_vibe = "TECHNICAL"
        self._wrap_residents_for_sandbox()
        
        logging.info(f"[HUB_GUARD] Request {request_id} entering process_query. Set size: {len(self.processed_ids)}")
        async with self.request_lock:
            if request_id in self.processed_ids:
                logging.warning(f"[HUB_GUARD] REJECTED redundant request: {request_id}")
                return
            self.processed_ids.add(request_id)
            logging.info(f"[HUB_GUARD] ACCEPTED request: {request_id}")
        
        # [Task 9.7] Direct Intent Overrides
        if turn.startswith("[TRIGGER]"):
            task = turn.replace("[TRIGGER]", "").strip().lower()
            await self._run_triggered_task(task)
            return



        # [Goal 5] Override Detection: Scan for override indicators (matching GEM-xxxx)
        import re
        gem_match = re.search(r"\b(GEM-[a-fA-F0-9]{4})\b", turn, re.IGNORECASE)
        is_correction = any(kw in turn.lower() for kw in ["correct", "wrong", "fix", "override", "change", "update"])
        
        if gem_match and is_correction:
            gem_id = gem_match.group(1).upper()
            logging.info(f"[HUB] Goal 5: Override intent detected for {gem_id} in query: {turn}")
            
            # Start background crosstalk notify
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"[HUB] Processing correction for {gem_id}...",
                "brain_source": "System"
            })
            
            # Parse the override
            updates = await self._parse_override_with_resident(gem_id, turn)
            if updates:
                # Save override
                self._save_override_to_file(gem_id, updates)
                confirm_msg = f"[SYSTEM]: Correction registered for {gem_id}. Applied updates: {updates}. This override will be active during the next compile."
            else:
                confirm_msg = f"[SYSTEM]: Correction detected for {gem_id}, but failed to extract fields. No updates applied."
                
            await self._stream_message_to_ui(confirm_msg, source="System", request_id=request_id)
            return

        # 1. Triage Phase
        logging.info(f"[HUB] Triage starting for query: {turn[:40]}...")
        t_text = ""
        t_parsed = None
        
        # [BKM-015] Role Token Routing: Bypass LLM triage if query contains a role token
        if self.role_tokens:
            for token in self.role_tokens:
                if token in turn:
                    route = self._token_routes.get(token)
                    if route:
                        turn = turn.replace(token, "").strip()
                        t_parsed = dict(route)
                        t_parsed["is_explicit_token"] = True
                        logging.info(f"[HUB] Role token '{token}' detected. Direct routing to {t_parsed['addressed_to']}.")
                        await self.broadcast({
                            "type": "crosstalk",
                            "brain": f"[HUB] Role token '{token}' → {t_parsed['addressed_to']}. Bypassing triage.",
                            "brain_source": "System",
                            "version": LAB_VERSION
                        })
                        break
        
        # [FEAT-350] Engine Stabilization: Retry loop for small models
        for triage_attempt in range(3):
            if t_parsed is not None:
                break
            try:
                await self.broadcast({
                    "type": "crosstalk", 
                    "brain": f"Triage Attempt {triage_attempt+1}...", 
                    "brain_source": "System"
                })
                
                # [Task 12.2] Brain Early-Reply: Let Brain fill dead air while waking
                if not self.get_vram_status():
                    logging.info("[HUB] Engine warming. Routing to KENDER immediately.")
                    if triage_attempt == 0:
                        await self.broadcast({
                            "type": "crosstalk", 
                            "brain": "Lab is warming its anchors. Reaching out to Deep Thought...", 
                            "brain_source": "System",
                            "version": LAB_VERSION
                        })
                        try:
                            # Pass to thought node to fill dead air
                            async for _ in self._process_node_stream(
                                "thought", turn, "", "Deep Thought", tools=[], temperature=0.7, request_id=request_id
                            ):
                                pass
                        except Exception as e:
                            logging.warning(f"[HUB] Early-reply failed: {e}")
                    
                    wait_limit = 18 if triage_attempt == 0 else 3
                    for _ in range(wait_limit):
                        if self.get_vram_status():
                            break
                        await asyncio.sleep(5.0)
                
                # [Task 9.2 & FEAT-418] Guided Decoding Schema for Triage
                triage_schema = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_result",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "addressed_to": {"type": "string", "enum": ["NONE", "BRAIN", "PINKY", "MICE"]},
                                "vibe": {"type": "string", "enum": ["TECHNICAL", "CASUAL", "HISTORICAL", "ANALYTICAL", "OPERATIONAL", "FORENSIC", "META", "WYWO"]},
                                "domain": {"type": "string", "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard"]},
                                "casual": {"type": "number"},
                                "intrigue": {"type": "number"},
                                "importance": {"type": "number"},
                                "situation": {"type": "string"},
                                "hints": {"type": "string"}
                            },
                            "required": ["addressed_to", "vibe", "domain", "casual", "intrigue", "importance"]
                        }
                    }
                }

                triage_mode_context = (
                    "[MODE]: TRIAGE (Grounding: Casual greetings/quips like 'what's up', 'hey', 'hi' MUST evaluate as "
                    "addressed_to: PINKY, vibe: CASUAL, importance: 0.1. Direct technical queries set addressed_to: BRAIN. "
                    "Unaddressed or general queries set addressed_to: NONE.)"
                )

                async for token in self._process_node_stream(
                    "lab", turn, triage_mode_context, "Lab (Triage)", tools=[], temperature=0.0, response_format=triage_schema, request_id=request_id
                ):
                    t_text += token

                logging.info(f"[HUB] Triage Output: {t_text}")

                t_clean = self.bridge_signal_clean(t_text)
                if not t_clean:
                    # [FIX] Do NOT scythe if it's a connection error (vLLM is just slow)
                    is_connection_error = "vLLM connection failed" in t_text or "Error:" in t_text
                    
                    if not is_connection_error:
                        self.consecutive_parse_failures += 1
                        if self.consecutive_parse_failures >= 3:
                            msg = f"[WARNING] Engine instability detected (Gibberish). Attempting to maintain baseline. (Consecutive: {self.consecutive_parse_failures})"
                            logging.warning(msg)
                            await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})

                        if self.consecutive_parse_failures >= 10:
                            if self.hibernate_callback:
                                msg = "[ALARM] Persistent corruption detected. Triggering H2 Engine Scythe for reset."
                                logging.error(msg)
                                await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
                                await self.broadcast({"type": "status", "state": "recovery", "message": "AUTONOMOUS_RECOVERY: Resetting Engine."})
                                asyncio.create_task(self.hibernate_callback(level=2, recover=True))
                    else:
                        logging.warning("[HUB] Triage yielded connection error. Retrying without scythe penalty.")

                    logging.error(f"[HUB] TRIAGE_PARSE_FAILURE: Raw output follows:\n{t_text}")
                    raise ValueError("TRIAGE_PARSE_FAILURE")

                self.consecutive_parse_failures = 0 # Reset on success
                self.triage_failures = 0 # [FIX] Reset on successful parse
                t_parsed = t_clean
                await self.broadcast({
                    "type": "crosstalk",
                    "brain": f"[HUB] Triage successful. Vibe: {t_parsed.get('vibe')}",
                    "brain_source": "System",
                    "version": LAB_VERSION
                })
                break
            except Exception as e:
                logging.warning(f"[HUB] Triage Attempt {triage_attempt+1} failed: {e}")
                t_text = ""
                await asyncio.sleep(2)

        if not t_parsed:
            logging.error("[HUB] All triage attempts failed. Falling back to PINKY.")
            t_parsed = {"vibe": "CASUAL", "addressed_to": "PINKY", "importance": 0.5, "domain": "standard"}

        # [Triage Intent Gate] Check if triage output requests morning briefing
        hints = str(t_parsed.get("hints", "")).lower()
        situation = str(t_parsed.get("situation", "")).lower()
        if "morning_briefing" in hints or "morning_briefing" in situation or "trigger_morning_briefing" in hints:
            logging.info("[HUB] Triage Intent Gate: Morning briefing triggered via triage.")
            if trigger_briefing_callback:
                await trigger_briefing_callback()
            else:
                await self.trigger_morning_briefing(request_id=request_id)
            return

        # 2. Routing Phase
        importance = float(t_parsed.get("importance", 0.5))
        casual = float(t_parsed.get("casual", 0.5))
        intrigue = float(t_parsed.get("intrigue", 0.5))
        
        # [FEAT-234] Unified Interest Calculation: Damped casual penalty to prevent conversational veto
        interest = ((1.0 - (casual * 0.5)) * (intrigue + importance)) / 2.0
        self.current_interest = max(0.0, min(1.0, interest))
        
        vibe = t_parsed.get("vibe", "").upper()
        self.current_vibe = vibe
        self._wrap_residents_for_sandbox()
        
        target = t_parsed.get("addressed_to", "PINKY").lower()
        
        if self.set_active_domain:
            self.set_active_domain(t_parsed.get("domain", "standard"))
        
        # [Task 15.1] Conversational Grace Override & [Task 18.3] Pinky Un-gagging
        behavioral_guidance = ""
        context = ""
        if vibe == "CASUAL":
            behavioral_guidance = "[MODE]: CONVERSATIONAL (Natural, witty, brief greetings. No technical lecturing.)"
        elif vibe == "WYWO":
            # [FEAT-409] WYWO Retrieval: Pull nightly dialogue and subconscious dreams
            nightly_dialogue = "No recent nightly dialogue recorded."
            dialogue_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json")
            if os.path.exists(dialogue_path):
                try:
                    with open(dialogue_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            nightly_dialogue = f"Topic: {data.get('topic')}\nDialogue: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load nightly dialogue: {e}")
            
            recruiter_report = "No recruiter report found."
            recruiter_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
            if os.path.exists(recruiter_path):
                try:
                    with open(recruiter_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            recruiter_report = f"Topic: {data.get('topic')}\nContent: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load recruiter report: {e}")
            
            system_status = "No system status found."
            status_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        data = json.load(f)
                        system_status = f"Status: {data.get('status', 'unknown')}\nDetails: {data.get('details', 'none')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load system status: {e}")
            
            pager_activity = "No pager activity found."
            pager_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json")
            if os.path.exists(pager_path):
                try:
                    with open(pager_path, "r") as f:
                        data = json.load(f)
                        if data.get("activity"):
                            pager_activity = f"Activity: {data.get('activity')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load pager activity: {e}")
            
            dreams = "No long-term subconscious dreams found."
            if "archive" in self.residents:
                try:
                    res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 2})
                    if hasattr(res, 'content') and len(res.content) > 0:
                        dreams = res.content[0].text
                except Exception as e:
                    logging.error(f"[HUB] Failed to load Diamond Wisdom for WYWO: {e}")

            context = (
                f"[NIGHTLY_DIALOGUE_RECORD]:\n{nightly_dialogue}\n\n"
                f"[RECRUITER_REPORT]:\n{recruiter_report}\n\n"
                f"[SYSTEM_STATUS]:\n{system_status}\n\n"
                f"[PAGER_ACTIVITY]:\n{pager_activity}\n\n"
                f"[SUBCONSCIOUS_DREAM_WISDOM]:\n{dreams}"
            )
            behavioral_guidance = (
                "[MODE]: STANDUP (Synthesize a high-density, professional summary of recent nightly dialogues "
                "and subconscious dreams consolidated during nightly runs. Explain what nodes debated, "
                "the key decisions or validation wisdom stored, and any resulting system changes.)"
            )
        else:
            # If it's not casual, ensure Pinky synthesizes the RAG hints rather than just dumping them.
            behavioral_guidance = "[MODE]: SYNTHESIS (Do not raw-dump tags or RAG refs. Speak conversationally, using the provided context as background knowledge.)"
            # Pass the triage hints as context so Pinky has something to synthesize.
            context = f"Triage Situation: {t_parsed.get('situation', '')}\nTriage Hints: {t_parsed.get('hints', '')}"

        # [FEAT-418] The Symmetrical Interest Cascade (Lead Speaker + Interjection Threshold)
        target_upper = str(target).upper()
        if target_upper in ["BRAIN", "THOUGHT", "DEEP"]:
            lead_node = "brain"
        elif target_upper == "MICE":
            lead_node = "both"
        else: # "PINKY" or "NONE"
            lead_node = "pinky"

        if lead_node == "brain":
            # Brain leads Turn 1
            await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id)
            # Turn 2: Pinky interjects if interest is high
            if self.current_interest > 0.5:
                async for token in self._process_node_stream(
                    "pinky", turn, context, "Pinky (Foil Interjection)", 
                    tools=[], temperature=0.7, request_id=request_id,
                    behavioral_guidance="[MODE]: FOIL_INTERJECTION (Brief, witty, intuitive quip following Brain's response.)"
                ):
                    if shutdown_event and shutdown_event.is_set():
                        break
        elif lead_node == "both":
            # Both speak on Turn 1 ("Hey mice!")
            full_pinky_text = ""
            async for token in self._process_node_stream(
                "pinky", turn, context, "Pinky (Response)", 
                tools=[], temperature=0.7, request_id=request_id,
                behavioral_guidance=behavioral_guidance
            ):
                full_pinky_text += token
                if shutdown_event and shutdown_event.is_set():
                    break
            await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id)
        else:
            # Pinky leads Turn 1 (Default for PINKY or NONE)
            full_pinky_text = ""
            async for token in self._process_node_stream(
                "pinky", turn, context, "Pinky (Response)", 
                tools=[], temperature=0.7, request_id=request_id,
                behavioral_guidance=behavioral_guidance
            ):
                full_pinky_text += token
                if shutdown_event and shutdown_event.is_set():
                    break
            
            # Intercept morning briefing tool call from Pinky's response
            if "trigger_morning_briefing" in full_pinky_text:
                logging.info("[HUB] Intercepted trigger_morning_briefing tool call from Pinky's response.")
                if trigger_briefing_callback:
                    await trigger_briefing_callback()
                else:
                    await self.trigger_morning_briefing(request_id=request_id)
                return
            
            # Turn 2: Brain interjects if interest is high
            if self.current_interest > 0.5:
                await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id)

        # [FEAT-356] Unified Session Ledger: Record turn summary
        turn_ledger = f"User: {turn}"
        pinky_res = self.turn_thought_trace.get("pinky")
        if pinky_res:
            turn_ledger += f"\nPinky: {pinky_res}"
        brain_res = self.turn_thought_trace.get("thought") or self.turn_thought_trace.get("brain")
        if brain_res:
            turn_ledger += f"\nBrain: {brain_res}"
        critique_res = self.turn_thought_trace.get("critique")
        if critique_res:
            turn_ledger += f"\nPinky Summary: {critique_res}"
        self.round_table_memory.append(turn_ledger)

    async def evaluate_grounding(self, source, text, interest=0.8, shutdown_event=None, request_id="default"):
        """
        [FEAT-227] The Grounding Gate (V5).
        Restores character balance by prompting Pinky to critique or conversationally 
        summarize Deep Thought's technical output directly into the Chat pane.
        """
        if "pinky" not in self.residents:
            return
        
        # Calculate dynamic scaling based on length
        importance = interest
        if len(text) > 800:
            importance = min(1.0, importance + 0.2)
            
        if importance <= 0.5:
            logging.info(f"[HUB] Grounding Gate skipped for {source} (Interest/Importance: {importance:.2f} <= 0.5).")
            return
            
        logging.info(f"[HUB] Grounding Gate triggered for {source} (Interest/Importance: {importance:.2f} > 0.5).")
        # [FEAT-356] Pinky as Coherence Judge
        critique_query = (
            f"Analyze the following response from {source} for logic errors, hand-waving, technical slop, or contradictions.\n\n"
            f"[RESPONSE TO EVALUATE]:\n{text}\n\n"
            "Evaluate its technical coherence and output a JSON block matching this schema:\n"
            "{\n"
            "  \"score\": 5, // 1-5 rating of logic/coherence\n"
            "  \"reasoning\": \"brief explanation of the score\",\n"
            "  \"slop_found\": false, // true if logic errors or slop exist\n"
            "  \"retort\": \"a challenging technical retort pointing out logical flaws, or a supportive technical critique summary\"\n"
            "}\n"
            "STRICT: Output ONLY valid JSON inside curly braces."
        )

        eval_schema = {
            "type": "json_schema",
            "json_schema": {
                "name": "coherence_evaluation",
                "schema": {
                    "type": "object",
                    "properties": {
                        "score": {"type": "integer", "minimum": 1, "maximum": 5},
                        "reasoning": {"type": "string"},
                        "slop_found": {"type": "boolean"},
                        "retort": {"type": "string"}
                    },
                    "required": ["score", "reasoning", "slop_found", "retort"]
                }
            }
        }

        # Vibe-Aware Tone mapping
        vibe = self.current_vibe.upper() if hasattr(self, 'current_vibe') and self.current_vibe else "CASUAL"
        vibe_tone = "Tone guidance: Casual, friendly, peer-to-peer."
        if vibe == "TECHNICAL":
            vibe_tone = "Tone guidance: Grounded, slightly critique-oriented, checking technical viability."
        elif vibe == "HISTORICAL":
            vibe_tone = "Tone guidance: Reflective, nostalgic, referencing previous engineering scars."
        elif vibe == "FORENSIC":
            vibe_tone = "Tone guidance: Cynical, investigative, auditing telemetry patterns."
        elif vibe == "META":
            vibe_tone = "Tone guidance: Self-aware, observing the lab's state machine."
        elif vibe == "OPERATIONAL":
            vibe_tone = "Tone guidance: Direct, diagnostic-focused, emphasizing active system state and logs."
        elif vibe == "ANALYTICAL":
            vibe_tone = "Tone guidance: Systematic, comparative, weighting trade-offs with high objectivity."

        try:
            # [FEAT-406] Coherence Judge Evaluation: Call Pinky's think tool for evaluation and retort
            res_eval = await self.residents["pinky"].call_tool("think", {
                "query": critique_query, 
                "context": f"Technical Output to evaluate:\n{text}",
                "behavioral_guidance": f"Act as a strict Coherence Critic. Check for logic errors, slop, or inconsistency. {vibe_tone}",
                "response_format": eval_schema,
                "request_id": request_id
            })
            
            eval_text = ""
            if hasattr(res_eval, 'content') and len(res_eval.content) > 0:
                eval_text = res_eval.content[0].text
            else:
                eval_text = str(res_eval)
            
            # Parse evaluation result
            eval_data = {}
            match = re.search(r'\{.*\}', eval_text, re.DOTALL)
            if match:
                try:
                    eval_data = json.loads(match.group(0))
                except Exception:
                    pass
            
            # Default fallback if parsing failed
            if not eval_data:
                eval_data = {
                    "score": 5,
                    "reasoning": "Coherence check passed implicitly or output formatting failed.",
                    "slop_found": False,
                    "retort": eval_text
                }
            
            # Save the critique response to turn_thought_trace for the ledger
            retort_text = eval_data.get("retort", "")
            self.turn_thought_trace["critique"] = retort_text
            
            # Log evaluations to .round_table_evals.json
            eval_file_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/.round_table_evals.json")
            existing_evals = []
            if os.path.exists(eval_file_path):
                try:
                    with open(eval_file_path, "r") as f:
                        existing_evals = json.load(f)
                except Exception:
                    pass
            
            new_eval = {
                "timestamp": time.time(),
                "source": source,
                "score": eval_data.get("score", 5),
                "reasoning": eval_data.get("reasoning", ""),
                "slop_found": eval_data.get("slop_found", False),
                "retort": retort_text
            }
            existing_evals.append(new_eval)
            
            # Atomic write (.tmp + replace)
            tmp_path = eval_file_path + ".tmp"
            try:
                with open(tmp_path, "w") as f:
                    json.dump(existing_evals, f, indent=2)
                os.replace(tmp_path, eval_file_path)
            except Exception as e:
                logging.error(f"[HUB] Failed to save evaluations to .round_table_evals.json: {e}")

            # Dispatch retort as terminal summary to the chat window
            await self.execute_dispatch(retort_text, "Pinky (Coherence Critic)", shutdown_event=shutdown_event, final=True)
        except Exception as e:
            logging.error(f"[HUB] Coherence critique failed: {e}")

    async def _distill_strategic_brief(self, raw_context, request_id="default"):
        """[Task 2.2] Context Precision: Synthesize raw RAG into a dense brief."""
        if not raw_context or "brain" not in self.residents:
            return raw_context
            
        logging.info("[HUB] Context Precision: Distilling raw RAG into Strategic Brief...")
        try:
            prompt = (
                "Synthesize the following raw technical artifacts into a 2-paragraph high-density 'Strategic Brief'. "
                "Extract specific platform anchors, validation targets, and known PECI/MSR scars. "
                "STRICT: NO ROLEPLAY. PROVIDE ONLY THE TECHNICAL SYNTHESIS."
            )
            # Use 'think' to generate distillation
            res = await self.residents["brain"].call_tool("think", {
                "query": prompt, 
                "context": raw_context,
                "behavioral_guidance": "Distill for Strategic Thought.",
                "request_id": request_id
            })
            
            brief = ""
            if hasattr(res, 'content') and len(res.content) > 0:
                brief = res.content[0].text
            else:
                brief = str(res)
                
            logging.info(f"[HUB] Distillation complete ({len(brief)} chars).")
            return f"[STRATEGIC_BRIEF]:\n{brief}\n\n[RAW_CONTEXT_APPEND]:\n{raw_context[:1000]}..."
        except Exception as e:
            logging.warning(f"[HUB] Context distillation failed: {e}")
            return raw_context

    async def _get_node_tools(self, node_id: str) -> list:
        """[SPR-41_1] Retrieve active tool names from a resident node's MCP server."""
        node = self.residents.get(node_id)
        if not node or not hasattr(node, 'mcp'):
            return []
        try:
            mcp_tools = await node.mcp.list_tools()
            return [t.name for t in mcp_tools]
        except Exception as e:
            logging.warning(f"[HUB] Failed to list tools for {node_id}: {e}")
            return []

    async def _run_brain_leg(self, query, triage, shutdown_event=None, request_id="default"):
        """Handles Brain (4090) leg of the waterfall."""
        # [Task 2.2] Context Precision
        vibe = triage.get("vibe", "").upper()
        if vibe == "WYWO":
            # Construct WYWO context
            nightly_dialogue = "No recent nightly dialogue recorded."
            dialogue_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/nightly_dialogue.json")
            if os.path.exists(dialogue_path):
                try:
                    with open(dialogue_path, "r") as f:
                        data = json.load(f)
                        if data.get("content"):
                            nightly_dialogue = f"Topic: {data.get('topic')}\nDialogue: {data.get('content')}"
                except Exception as e:
                    logging.error(f"[HUB] Failed to load nightly dialogue: {e}")
            
            dreams = "No long-term subconscious dreams found."
            if "archive" in self.residents:
                try:
                    res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 2})
                    if hasattr(res, 'content') and len(res.content) > 0:
                        dreams = res.content[0].text
                except Exception as e:
                    logging.error(f"[HUB] Failed to load Diamond Wisdom for WYWO: {e}")

            raw_context = (
                f"[NIGHTLY_DIALOGUE_RECORD]:\n{nightly_dialogue}\n\n"
                f"[SUBCONSCIOUS_DREAM_WISDOM]:\n{dreams}"
            )
        else:
            raw_context = f"Triage Situation: {triage.get('situation', '')}\nTriage Hints: {triage.get('hints', '')}"
        
        distilled_context = await self._distill_strategic_brief(raw_context, request_id=request_id)

        # Dispatch to Brain Node
        # [FEAT-408] Tool-Driven Waterfall Cascade: Pass active MCP tools to remote reasoner
        dt_response = ""
        active_tools = await self._get_node_tools("thought")
        async for token in self._process_node_stream(
            "thought", query, distilled_context, "Deep Thought", tools=active_tools, temperature=0.2, request_id=request_id
        ):
            dt_response += token
            if shutdown_event and shutdown_event.is_set():
                break

        # [SPR-41_2] Skip cascade if context starvation was detected
        if "thought" in self.context_starved_nodes:
            self.context_starved_nodes.discard("thought")
            logging.info("[HUB] Brain leg cascade bypassed due to CONTEXT_STARVED.")
            return
        
        # [FEAT-227] The Grounding Gate: Let Pinky critique and summarize the final technical/strategic output in the main chat pane
        await self.evaluate_grounding("Deep Thought", dt_response, interest=self.current_interest, shutdown_event=shutdown_event, request_id=request_id)

    async def _run_triggered_task(self, task_name):
        """[Task 9.7] Handles one-off system triggers (Recruiter, Librarian, etc)."""
        import subprocess
        import sys
        
        # Path Discovery
        SRC_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
        
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Executing Triggered Task: {task_name.upper()}",
            "brain_source": "System"
        })
        
        try:
            if task_name == "recruiter":
                script = os.path.join(SRC_DIR, "recruiter.py")
                subprocess.Popen([sys.executable, script])
            elif task_name == "lab":
                script = os.path.join(WORKSPACE_DIR, "field_notes/scan_librarian.py")
                subprocess.Popen([sys.executable, script])
            elif task_name == "forge":
                script = os.path.join(SRC_DIR, "mass_scan.py")
                subprocess.Popen([sys.executable, script])
            
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Task {task_name.upper()} dispatched to background.",
                "brain_source": "System"
            })
        except Exception as e:
            logging.error(f"[HUB] Failed to run triggered task {task_name}: {e}")

    async def _parse_override_with_resident(self, gem_id, turn):
        """Use the resident model to parse key-value corrections from user query."""
        prompt = f"""
        [TASK]
        Extract performance reviews/validation correction updates for the entry identifier '{gem_id}' from this message.
        
        [MESSAGE]
        {turn}
        
        [OUTPUT FORMAT]
        Return JSON only with keys:
        - "date": "YYYY-MM-DD" or null
        - "tags": ["tag1", "tag2"] or null
        - "summary": "updated text summary" or null
        
        JSON:
        """
        # Call node to parse
        node = self.residents.get("pinky")
        if not node:
            node = self.residents.get("brain")
            
        if node:
            try:
                response_str = await node.think(prompt, internal=True)
                import re
                import json
                match = re.search(r'\{.*\}', response_str, re.DOTALL)
                if match:
                    updates = json.loads(match.group(0))
                    return {k: v for k, v in updates.items() if v is not None}
            except Exception as e:
                logging.error(f"[HUB] Override parsing error: {e}")
        return None

    def _save_override_to_file(self, gem_id, updates):
        """Append or update correction rules in overrides.json atomically."""
        overrides_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/overrides.json")
        overrides = {}
        if os.path.exists(overrides_path):
            try:
                with open(overrides_path, "r") as f:
                    overrides = json.load(f)
            except Exception:
                pass
                
        if "overrides" not in overrides:
            overrides["overrides"] = {}
            
        if gem_id not in overrides["overrides"]:
            overrides["overrides"][gem_id] = {}
        overrides["overrides"][gem_id].update(updates)
        
        # Atomic write
        tmp = overrides_path + ".tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(overrides, f, indent=2)
            os.replace(tmp, overrides_path)
            logging.info(f"[HUB] Successfully committed override for {gem_id} to overrides.json")
        except Exception as e:
            logging.error(f"[HUB] Failed to save overrides.json: {e}")

    async def _stream_message_to_ui(self, message, source="System", request_id="default"):
        """Streams a message character-by-character to the UI waterfall."""
        if hasattr(self, 'waterfall_queue') and self.waterfall_queue:
            chunk_size = 5
            for i in range(0, len(message), chunk_size):
                chunk = message[i:i+chunk_size]
                await self.waterfall_queue.put({
                    "brain": chunk,
                    "source": source,
                    "brain_source": source,
                    "final": False,
                    "request_id": request_id
                })
                await asyncio.sleep(0.01)
            # Finalize
            await self.waterfall_queue.put({
                "brain": "",
                "source": source,
                "brain_source": source,
                "final": True,
                "request_id": request_id
            })

    async def handle_workspace_save(self, filename, content):
        """[FEAT-050] Strategic Vibe Check: Performs logic/code validation on save."""
        logging.info(f"[HUB] User saved workspace file: {filename}")
        
        if not hasattr(self, 'last_save_event'):
            self.last_save_event = 0.0
            
        import time
        if time.time() - self.last_save_event < 10.0:
            return
        self.last_save_event = time.time()
        
        # 1. Pinky notice
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Narf! I noticed you saved {filename}!",
            "brain_source": "Pinky",
            "channel": "chat",
            "final": True
        })
        
        # 2. Brain validation
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Strategic Vibe Check: Analyzing architecture constraints for {filename}...",
            "brain_source": "The Brain",
            "channel": "insight",
            "final": True
        })

    async def trigger_morning_briefing(self, request_id="default"):
        """[FEAT-072.1] Present the morning briefing to the user."""
        wisdom_text = ""
        if "archive" in self.residents:
            try:
                # 1. Fetch latest wisdom from long-term memory
                res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 1})
                if hasattr(res, 'content') and len(res.content) > 0:
                    text_content = res.content[0].text
                    try:
                        data = json.loads(text_content)
                        wisdom_text = data.get("text", "")[:4000]
                    except Exception:
                        wisdom_text = text_content[:4000]
            except Exception as e:
                logging.error(f"[HUB] Failed to load Diamond Wisdom: {e}")
        
        # 2. Read status.json
        status_data = {}
        status_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/status.json")
        if os.path.exists(status_path):
            try:
                with open(status_path, "r") as f:
                    status_data = json.load(f)
            except Exception as e:
                logging.error(f"[HUB] Failed to load status.json: {e}")

        # 3. Read recruiter_report.json
        recruiter_data = {}
        recruiter_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/recruiter_report.json")
        if os.path.exists(recruiter_path):
            try:
                with open(recruiter_path, "r") as f:
                    recruiter_data = json.load(f)
            except Exception as e:
                logging.error(f"[HUB] Failed to load recruiter_report.json: {e}")

        # 4. Read pager_activity.json
        pager_warnings = []
        pager_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/pager_activity.json")
        if os.path.exists(pager_path):
            try:
                with open(pager_path, "r") as f:
                    activities = json.load(f)
                    # Filter for critical/warning alerts and take last 3
                    filtered = [act for act in activities if act.get("severity", "").upper() in ["CRITICAL", "WARNING"]]
                    pager_warnings = filtered[-3:]
            except Exception as e:
                logging.error(f"[HUB] Failed to load pager_activity.json: {e}")

        # 5. Format the briefing prompt
        prompt_parts = []
        prompt_parts.append("Generate a morning briefing using the following system status and context:")
        if wisdom_text:
            prompt_parts.append(f"\n[DIAMOND WISDOM CONTEXT]:\n{wisdom_text}")
        if status_data:
            prompt_parts.append(f"\n[SYSTEM STATUS]:\n{json.dumps(status_data, indent=2)}")
        if recruiter_data:
            prompt_parts.append(f"\n[RECRUITER REPORT]:\n{json.dumps(recruiter_data, indent=2)}")
        if pager_warnings:
            prompt_parts.append(f"\n[RECENT PAGER WARNINGS/ERRORS]:\n{json.dumps(pager_warnings, indent=2)}")
        
        prompt_parts.append(
            "\n[INSTRUCTION]:\nSynthesize the above information into a high-density, professional news briefing. "
            "Address Jason directly. Highlight any critical alerts or new job listings, and summarize our current system VRAM and status. "
            "CRITICAL GROUNDING RULE: You must ONLY use the facts provided above. Do NOT imagine, guess, or invent any metrics, job listings, or status details. If any metric or list is empty or not provided, state that it is not available. Every detail must be strictly grounded."
        )
        
        briefing_prompt = "\n".join(prompt_parts)

        # 6. Stream via Pinky
        if "pinky" in self.residents:
            async for _ in self._process_node_stream(
                "pinky", briefing_prompt, "[MODE]: MORNING_BRIEFING", "Pinky (Briefing)",
                tools=[], temperature=0.1, request_id=request_id
            ):
                pass

    async def _prime_first_try(self, turn):
        """[NEW] First Try: Persona-faithful quick response."""
        # Persona defaults to Deep Thought as it's pre-triage
        persona = "Deep Thought (naive, laconic, hesitant to answer directly, slightly arrogant)"
        logging.info(f"[PRIME] Initiating priming for turn: {turn[:50]}")
        
        tic_msg = None
        
        # Opportunistic check: if KENDER is immediately available, try to get a quip.
        if "thought" in self.residents:
            try:
                logging.info(f"[PRIME] Calling 'think' tool for persona: {persona}")
                # Use a very short timeout; this is just to buy time for triage, not stall it.
                tic_res = await asyncio.wait_for(self.residents["thought"].call_tool("think", {
                    "query": f"[SYSTEM_TIC]: Provide a short 'First Try' response from {persona} acknowledging the query: '{turn[:50]}'. Do not answer the question directly. Acknowledge with arrogant hesitance, knowing the waterfall process will handle the details.",
                    "temperature": 0.8
                }), timeout=3.0)
                tic_msg = tic_res.content[0].text
                logging.info(f"[PRIME] Tic generated: {tic_msg[:30]}")
            except Exception as e:
                logging.error(f"[PRIME] Tic generation failed: {e}")
                
        if not tic_msg:
            tic_msg = "Initiating mental synthesis... deep thought in progress."
            
        await self.broadcast({
            "type": "crosstalk",
            "brain": tic_msg,
            "brain_source": "Deep Thought",
            "channel": "insight",
            "final": False,
            "version": LAB_VERSION
        })
        logging.info("[PRIME] Broadcast complete.")
