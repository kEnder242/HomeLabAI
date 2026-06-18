import asyncio
import json
import logging
import os
import re
import time
import random
from v5.common.types import LAB_VERSION

# [Task 4.2] V5 Cognitive Hub: The Logical Core
# Objective: Manage multi-node reasoning waterfall and strategic routing.

class CognitiveHub:
    IDENTITY_BEDROCK = (
        "[LAB_IDENTITY]: Acme Lab is your digital container (Z87-Linux native). You reside within it. The user is the Lead Engineer who built you.\n"
        "[TOPOGRAPHY]: 3-Tier Memory in effect. Layer 1 (Diamond): Star artifacts. Layer 2 (Archive): RAG historical logs. Layer 3 (Raw): Direct telemetry (RAPL/MSR).\n"
        "[ARCHIVAL_MAP]: Archive spans 2005-2024. High-density evidence in [Telemetry: 2019-2024], [Firmware: 2011-2018], [Automation: 2020-2024].\n"
        "[INHABITANTS]: Pinky (Right Hemisphere - Casual/Triage/STT), Brain (Subconscious - Intuition/Refinement), Deep Thought (Sovereign - Strategic reasoning on 4090).\n"
    )

    def __init__(self, residents, broadcast_callback, sensory_manager, get_vram_status, trigger_morning_briefing, last_prime_callback=None, waterfall_queue=None, hibernate_callback=None):
        from collections import defaultdict
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.get_vram_status = get_vram_status
        self.trigger_morning_briefing_cb = trigger_morning_briefing
        self.last_prime_callback = last_prime_callback
        self.waterfall_queue = waterfall_queue # [FEAT-233.2] Internal Token Buffer
        self.hibernate_callback = hibernate_callback

        self.session_buffers = defaultdict(str)
        self.active_intent = None
        self.current_interest = 0.0
        self.current_topic = "INTERFACE"
        self.last_activity = time.time()
        
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
        
        self.auditor = None  # [FEAT-190] The Judge

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
                if "intent" in data or "vibe" in data:
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

    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, interest_threshold=0.0, temperature=0.0, repetition_penalty=1.0, retry_count=0, use_lora=True, response_format=None, request_id="default"):
        """[FEAT-233.5] Internal Waterfall Proxy: Handshakes the node and yields tokens."""
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
            
            guidance = self.IDENTITY_BEDROCK + stance
            if behavioral_guidance:
                guidance += f"\n[BEHAVIORAL_GUIDANCE]: {behavioral_guidance}"
            
            # [Task 1.1] Spark the node and wait for full block
            node = self.residents[node_id]
            
            # [Task 9.1] Isolated Buffer Key
            name_map = {"lab": "lab", "pinky": "pinky", "brain": "brain", "thought": "deep thought"}
            src_key = name_map.get(node_id, node_id)
            buf_key = f"{request_id}_{src_key}"
            self.session_buffers[buf_key] = ""
            
            # [Task 9.2] Hub relies on the Node's telemetry queue to populate the Foyer drainer.
            call_task = asyncio.create_task(node.call_tool("think", {
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
                    yield new_tokens
                    last_len = len(curr_buffer)
                    
            # Get the final result and any remaining buffer
            res = await call_task
            curr_buffer = self.session_buffers[buf_key]
            if len(curr_buffer) > last_len:
                new_tokens = curr_buffer[last_len:]
                full_text += new_tokens
                yield new_tokens
                
            # If the node didn't stream anything (e.g. error or missing logic), fallback to the full response
            if not full_text:
                if hasattr(res, 'content') and len(res.content) > 0:
                    full_text = res.content[0].text
                else:
                    full_text = str(res)
                yield full_text
            
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

    async def process_query(self, turn, shutdown_event=None, request_id=None):
        """[FEAT-145] Main Reasoning Waterfall."""
        if request_id is None:
            import uuid
            request_id = uuid.uuid4().hex[:8]
        
        # [NEW] Unified Early Priming
        logging.info(f"[PRIME] Spawning priming task for: {turn[:20]}")
        asyncio.create_task(self._prime_first_try(turn))
        
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

        # 1. Triage Phase
        logging.info(f"[HUB] Triage starting for query: {turn[:40]}...")
        t_text = ""
        t_parsed = None
        
        # [FEAT-350] Silicon Stabilization: Retry loop for small models
        for triage_attempt in range(3):
            try:
                await self.broadcast({
                    "type": "crosstalk", 
                    "brain": f"Triage Attempt {triage_attempt+1}...", 
                    "brain_source": "System"
                })
                
                # [Task 12.2] Sovereign Early-Reply: Let Brain fill dead air while waking
                if not self.get_vram_status():
                    logging.info("[HUB] Silicon warming. Routing to KENDER immediately.")
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
                
                # [Task 9.2] Guided Decoding Schema for Triage
                triage_schema = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "triage_result",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "intent": {"type": "string", "enum": ["STRATEGIC", "CASUAL", "RECALL"]},
                                "addressed_to": {"type": "string", "enum": ["BRAIN", "PINKY", "MICE"]},
                                "vibe": {"type": "string", "enum": ["TECHNICAL", "CASUAL", "HISTORICAL", "ANALYTICAL", "OPERATIONAL", "FORENSIC", "META"]},
                                "domain": {"type": "string", "enum": ["exp_tlm", "exp_bkm", "exp_for", "standard"]},
                                "casual": {"type": "number"},
                                "intrigue": {"type": "number"},
                                "importance": {"type": "number"},
                                "situation": {"type": "string"},
                                "hints": {"type": "string"}
                            },
                            "required": ["intent", "addressed_to", "vibe", "domain"]
                        }
                    }
                }

                async for token in self._process_node_stream(
                    "lab", turn, "[MODE]: TRIAGE", "Lab (Triage)", tools=[], temperature=0.0, response_format=triage_schema, request_id=request_id
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
                            msg = f"[WARNING] Silicon instability detected (Gibberish). Attempting to maintain baseline. (Consecutive: {self.consecutive_parse_failures})"
                            logging.warning(msg)
                            await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})

                        if self.consecutive_parse_failures >= 10:
                            if self.hibernate_callback:
                                msg = "[ALARM] Persistent corruption detected. Triggering H2 Silicon Scythe for reset."
                                logging.error(msg)
                                await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
                                await self.broadcast({"type": "status", "state": "recovery", "message": "AUTONOMOUS_RECOVERY: Resetting Silicon."})
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
                    "brain": f"[HUB] Triage successful. Intent: {t_parsed.get('intent')}",
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
            t_parsed = {"intent": "CASUAL", "addressed_to": "PINKY", "importance": 0.5}

        # 2. Routing Phase
        importance = float(t_parsed.get("importance", 0.5))
        self.current_interest = importance
        
        target = t_parsed.get("addressed_to", "PINKY").lower()
        vibe = t_parsed.get("vibe", "").upper()
        
        # [Task 15.1] Conversational Grace Override & [Task 18.3] Pinky Un-gagging
        behavioral_guidance = ""
        context = ""
        if vibe == "CASUAL":
            behavioral_guidance = "[MODE]: CONVERSATIONAL (Natural, witty, brief greetings. No technical lecturing.)"
        else:
            # If it's not casual, ensure Pinky synthesizes the RAG hints rather than just dumping them.
            behavioral_guidance = "[MODE]: SYNTHESIS (Do not raw-dump tags or RAG refs. Speak conversationally, using the provided context as background knowledge.)"
            # Pass the triage hints as context so Pinky has something to synthesize.
            context = f"Triage Situation: {t_parsed.get('situation', '')}\nTriage Hints: {t_parsed.get('hints', '')}"

        if "brain" in target or "deep" in target:
            # Elevate to Sovereign
            await self._run_brain_leg(turn, t_parsed, shutdown_event=shutdown_event, request_id=request_id)
        else:
            # Local Response
            async for _ in self._process_node_stream(
                "pinky", turn, context, "Pinky (Response)", 
                tools=[], temperature=0.7, request_id=request_id,
                behavioral_guidance=behavioral_guidance
            ):
                pass

    async def _run_brain_leg(self, query, triage, shutdown_event=None, request_id="default"):
        """Handles Sovereign (4090) leg of the waterfall."""
        # [Task 2.2] Context Distillation
        distilled_context = ""
        try:
            # Call brain node to summarize archives
            res = await self.residents["brain"].call_tool("think", {
                "query": f"Summarize archive context for: {query[:100]}",
                "request_id": request_id,
                "response_format": {}
            })
            distilled_context = ""
            if hasattr(res, 'content') and len(res.content) > 0:
                distilled_context = res.content[0].text
            else:
                distilled_context = str(res)
        except Exception as e:
            logging.warning(f"[HUB] Context distillation failed: {e}")

        # Dispatch to Sovereign
        # Side-channel Telemetry Relay handles the broadcast.
        # We just need to exhaust the generator to ensure the node task completes.
        async for token in self._process_node_stream(
            "thought", query, distilled_context, "Deep Thought", tools=[], temperature=0.2, request_id=request_id
        ):
            if shutdown_event and shutdown_event.is_set():
                break

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

    async def trigger_morning_briefing(self):
        """[FEAT-072.1] Present the latest Diamond Wisdom to the user."""
        if "archive" not in self.residents:
            return
        
        try:
            # 1. Fetch latest wisdom from long-term memory
            res = await self.residents["archive"].call_tool("get_context", {"query": "Latest Diamond Wisdom synthesis", "n_results": 1})
            data = json.loads(res.content[0].text)
            wisdom_text = data.get("text", "")
            
            if "No relevant artifacts" in wisdom_text:
                return

            # 2. Present via Pinky
            briefing_query = f"Summarize this Diamond Wisdom for the morning briefing: {wisdom_text[:500]}"
            async for _ in self._process_node_stream(
                "pinky", briefing_query, "[MODE]: DIRECT_RESPONSE", "Pinky (Briefing)",
                tools=[], temperature=0.7
            ):
                pass
        except Exception as e:
            logging.error(f"[HUB] Morning Briefing failed: {e}")

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
