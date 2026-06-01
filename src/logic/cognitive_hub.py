import asyncio
import json
import logging
import re
import os
import time
import datetime
from collections import deque
from infra.cognitive_audit import CognitiveAudit

class CognitiveHub:
    """
    [FEAT-145] Cognitive Hub: Modularized Reasoning & Dispatch Logic.
    [FEAT-203] Bicameral Bridge: Hardened neural signal extraction.
    [FEAT-239] Neural Action Tags: Natural language steering hints.
    [FEAT-240] Phase 2: Native MCP Sampling Relay.
    """
    # [FEAT-351] Physical Bedrock (BKM-015): Shared Identity Preamble
    # [FEAT-088] Topographical Injection: Oriented within 18 years of technical scars.
    IDENTITY_BEDROCK = (
        "[LAB_IDENTITY]: Acme Lab (Z87-Linux native). High-fidelity silicon validation environment.\n"
        "[TOPOGRAPHY]: 3-Tier Memory in effect. Layer 1 (Diamond): Star artifacts. Layer 2 (Archive): RAG historical logs. Layer 3 (Raw): Direct telemetry (RAPL/MSR).\n"
        "[ARCHIVAL_MAP]: Archive spans 2005-2024. High-density evidence in [Telemetry: 2019-2024], [Firmware: 2011-2018], [Automation: 2020-2024].\n"
        "[INHABITANTS]: Pinky (Right Hemisphere - Casual/Triage/STT), Brain (Subconscious - Intuition/Refinement), Deep Thought (Sovereign - Strategic reasoning on 4090).\n"
    )

    def __init__(self, residents, broadcast_callback, sensory_manager, get_vram_status, trigger_morning_briefing, monitor_task_with_tics, last_prime_callback=None, waterfall_queue=None, hibernate_callback=None):
        from collections import defaultdict
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.get_vram_status = get_vram_status
        self.trigger_morning_briefing_cb = trigger_morning_briefing
        self.monitor_task_with_tics = monitor_task_with_tics
        self.last_prime_callback = last_prime_callback
        self.waterfall_queue = waterfall_queue # [FEAT-233.2] Internal Token Buffer
        self.hibernate_callback = hibernate_callback
        
        # [FEAT-332] Dynamic Streaming Modes
        self.streaming_config = {
            "lab": "WATERFALL",
            "pinky": "WATERFALL",
            "thought": "WATERFALL",
            "brain": "WATERFALL"
        }
        
        # [FEAT-233.7] Session Buffers: Real-time context for inter-node overhearing
        self.session_buffers = defaultdict(str)
        self.round_table_memory = deque(maxlen=5) # [FEAT-356] FOIL-AWARE MEMORY
        self.consecutive_parse_failures = 0 # [FEAT-339] Triage stability tracker
        self.lora_enabled = True # [FEAT-339] Global LoRA toggle
        self.current_fuel = 0.0
        self.current_topic = "Casual"
        self.resonant_history = []
        self.triage_failures = 0 # [FEAT-270] Track consecutive failures

        # [BKM-015] Anchor Migration
        self.config_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "config")
        self.anchors_path = os.path.join(self.config_dir, "intent_anchors.json")
        self.intent_anchors = {}
        if os.path.exists(self.anchors_path):
            with open(self.anchors_path, "r") as f:
                self.intent_anchors = json.load(f)
        
        # [FEAT-181] Semantic Integration
        self.semantic_map_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/semantic_map.json")
        self.semantic_map = {}
        if os.path.exists(self.semantic_map_path):
            with open(self.semantic_map_path, "r") as f:
                self.semantic_map = json.load(f)
        
        self.auditor = None  # [FEAT-190] The Judge

    def on_token(self, data):
        """[FEAT-233.7] Real-time token ingestion for inter-node overhearing."""
        source = str(data.get("brain_source", data.get("source", "Unknown"))).lower()
        token = data.get("brain", "")
        if token:
            self.session_buffers[source] += token
            
            # [FEAT-362] Non-Blocking Waterfall: Stream to user immediately
            if self.waterfall_queue:
                try:
                    self.waterfall_queue.put_nowait(data)
                except Exception as e:
                    logging.error(f"[WATERFALL] Queue error: {e}")
            else:
                asyncio.create_task(self.broadcast(data))
                
            # [DEBUG] Trace waterfall flow
            if "triage" not in source:
                logging.debug(f"[WATERFALL] Ingested token from {source} ({len(self.session_buffers[source])} total)")

    def bridge_signal_clean(self, text):
        """[FEAT-220.1] Extract and sanitize the FIRST JSON block from raw LLM output. Hardened for vLLM 3B."""
        if not text:
            return None

        # [FEAT-339] Gibberish Guard: Proactively detect high-entropy or semantic garbage
        # If the text has extreme repetition or lacks alphanumeric content, flag it.
        if len(text) > 100:
            from collections import Counter
            counts = Counter(text)
            most_common, count = counts.most_common(1)[0]
            
            # Repetition Check (e.g. "!!!!!!!!!!")
            if count / len(text) > 0.4:
                msg = f"[GIBBERISH] High-entropy detected (Repeating '{most_common}'). Raw: {text[:50]}..."
                logging.warning(msg)
                # Broadcast for visibility but don't parse as JSON
                asyncio.create_task(self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"}))
                return None
                
            # Alphanumeric Density Check (e.g. "oru 使用(menuresponsive...")
            alnum_count = sum(1 for c in text if c.isalnum())
            alnum_density = alnum_count / len(text)
            if alnum_density < 0.2:
                msg = f"[GIBBERISH] Semantic garbage detected (Alnum Density: {alnum_density:.2f}). Raw: {text[:50]}..."
                logging.warning(msg)
                asyncio.create_task(self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"}))
                return None

        # [FEAT-355] Visible Consensus: Do NOT strip <thought> tags anymore.
        # They are now broadcast for inter-node debate and user visibility.
        
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

        # 3. Parse valid block
        valid_parsed = []
        for block in json_blocks:
            try:
                # [FEAT-220.2] Structural Sanitization
                block = block.replace("{{", "{").replace("}}", "}")
                # Fix common JSON errors from small models
                block = re.sub(r",\s*}", "}", block) # trailing comma
                block = block.replace("True", "true").replace("False", "false")
                block = block.replace('"::', '":')
                
                parsed = json.loads(block)
                if isinstance(parsed, dict):
                    valid_parsed.append(parsed)
            except Exception:
                continue

        # [FIX] Task 3: Return the first block that contains triage fields
        for parsed in valid_parsed:
            if "intent" in parsed or "fuel" in parsed:
                return parsed
                
        # Fallback for tool calls (which don't have intent/fuel)
        if valid_parsed:
            return valid_parsed[0]
            
        return None

    async def execute_dispatch(self, text, source, shutdown_event=None, original_query=None, retry_count=0, final=True, use_lora=True):
        """
        [FEAT-238.1] Combined Dispatch: Persona Speech + Tool Action.
        Ensures persona is maintained even when tools are used for steering.
        """
        if not text:
            return

        # [FEAT-339] Triage Loop Brake: Prevent tool-call recursion storms
        MAX_RECURSION = 5
        if retry_count >= MAX_RECURSION:
            msg = f"[ALARM] Max tool recursion reached ({MAX_RECURSION}) for {source}. Aborting loop."
            logging.warning(msg)
            await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
            return text
            
        # [FEAT-355] Open Debate: Broadcast thoughts to inter-node context
        if "<thought>" in str(text) and self.current_fuel > 0.6:
            # Map labels (e.g. "Deep Thought") to buffer keys (e.g. "thought")
            label_lower = source.lower()
            thought_source = "pinky" if "pinky" in label_lower else "thought"
            if "intuition" in label_lower or "brain" in label_lower:
                thought_source = "brain"
            
            if text not in self.session_buffers[thought_source]:
                self.session_buffers[thought_source] += f"\n{text}"

        # [FEAT-072.1] Signal-Based Morning Briefing Uplink
        if "trigger_morning_briefing" in str(text) and final:
            if hasattr(self, 'trigger_briefing_cb') and self.trigger_briefing_cb:
                await self.broadcast({"type": "crosstalk", "brain": "[HUB] Neural Signal detected: trigger_morning_briefing", "brain_source": "System"})
                asyncio.create_task(self.trigger_briefing_cb())
                # Strip signal from display text if it's a raw tool call string
                text = text.replace('{"tool": "trigger_morning_briefing", "parameters": {}}', "").strip()
                if not text:
                    return
        # 1. Clean and Strip Node Artifacts
        clean_text = str(text).replace("<|eot_id|>", "").replace("<|begin_of_text|>", "").strip()
        
        # [FEAT-110] Brain Moat
        if "Brain" in source:
            pinky_isms = ["narf", "poit", "zort", "egad", "trotro"]
            for ism in pinky_isms:
                clean_text = re.sub(rf'\b{ism}\b', '', clean_text, flags=re.IGNORECASE).strip()
            clean_text = clean_text.replace("  ", " ").replace(" .", ".").replace(" ,", ",")

        # 2. Extract Action Tags [FEAT-239]
        action_match = re.search(r'\[ACTION:\s*([^\]]+)\]', clean_text, re.IGNORECASE)
        if action_match:
            action = action_match.group(1).upper().strip()
            clean_text = clean_text.replace(action_match.group(0), "").strip()
            if action == "UPLINK":
                await self.broadcast({"type": "crosstalk", "brain": f"[HUB] Action Tag: UPLINK via {source}", "brain_source": "System"})
                self.current_fuel = 1.0
            elif action == "THINK MORE":
                await self.broadcast({"type": "crosstalk", "brain": f"[HUB] Action Tag: THINK MORE via {source}", "brain_source": "System"})
                self.current_fuel = min(1.0, self.current_fuel + 0.3)
            
            # [FEAT-265.4] Clinical Thoughts: Strip formatting from internal stances
            for tag in ["TECHNICAL_INTUITION", "SYSTEM_DESIGN_STANCE", "HISTORICAL_TRUTH"]:
                clean_text = clean_text.replace(f"[{tag}]:", "").strip()
                clean_text = clean_text.replace(f"{tag}:", "").strip()

        # 3. Nuclear Tool Interception (Search and Destroy)
        json_raw_match = re.search(r'(\{.*\})', clean_text, re.DOTALL)
        raw_speech = clean_text # Default to full text
        
        if json_raw_match:
            raw_block = json_raw_match.group(1)
            # SPEECH SALVAGE: Extract everything OUTSIDE the raw JSON block
            raw_speech = clean_text.replace(raw_block, "").strip()
            # Clean markdown leftovers from speech
            raw_speech = re.sub(r"```json\s*|\s*```", "", raw_speech).strip()
            
            # [FEAT-361] Speech Salvage: Ensure <thought> tags are preserved even if within JSON match
            thought_match = re.search(r'(<thought>.*?</thought>)', clean_text, re.DOTALL | re.IGNORECASE)
            if thought_match and thought_match.group(1) not in raw_speech:
                raw_speech = (thought_match.group(1) + "\n" + raw_speech).strip()

            sanitized = self.bridge_signal_clean(raw_block)
            if sanitized:
                try:
                    # [FEAT-270.3] Type-Agnostic Triage Parser (ERR-06)
                    if isinstance(sanitized, dict):
                        data = sanitized
                    else:
                        data = json.loads(sanitized)
                    
                    tool = data.get("tool")
                    params = data.get("parameters", {})

                    # [HARDENING] Deep Search for sloppy JSON tool names
                    if not tool:
                        valid_tools = ["ask_brain", "think", "reply_to_user", "close_lab", "generate_bkm", "access_personal_history", "build_cv_summary"]
                        # Task 19.7.1: Check guided decoding schema fields first
                        if "tool_name" in data:
                            tool = data["tool_name"]
                        else:
                            for val in data.values():
                                if isinstance(val, str):
                                    for vt in valid_tools:
                                        if vt in val.lower():
                                            tool = vt
                                            break
                                    if tool:
                                        break

                    # [Task 19.7.1] Extract Guided JSON thought if raw speech is empty
                    if not raw_speech and "thought" in data:
                        raw_speech = str(data["thought"])

                    # Handle Known Tools
                    if tool == "ask_brain":
                        self.current_fuel = 1.0
                        if not raw_speech:
                            raw_speech = "Narf! I'll ask Deep Thought for you."

                    if tool in ["think"]:
                        # If Pinky or The Brain calls think on themselves, it's a VETO
                        # [FEAT-295] Tooling Parity: Unifying think/think as demotion signals
                        self.current_fuel = 0.0
                        if not raw_speech:
                            raw_speech = params.get("task") or params.get("query") or params.get("context") or "Narf! Thinking fast."

                    if tool == "reply_to_user":
                        reply = params.get("text") or params.get("reply")
                        if reply and not raw_speech:
                            raw_speech = reply

                    if tool == "close_lab":
                        await self.broadcast({"brain": "Acme Lab is closing.", "brain_source": "System", "final": True})
                        if shutdown_event:
                            shutdown_event.set()
                        return True

                    # [FEAT-237] Loop-Breaker (Legacy compatibility)
                    primary_entry_points = ["think", "deep_think", "triage_situational_vibe"]
                    if tool in primary_entry_points and tool not in ["think"]: # think/think are veto signals
                        # Return speech only, block recursive tool call
                        if raw_speech:
                            return await self._dispatch_plain_text(raw_speech, source, final=final)
                        return True

                    # Forward utility tools
                    known_hub_tools = ["bounce_node", "scribble_note", "trigger_morning_briefing", "build_cv_summary", "access_personal_history", "select_file", "notify_file_open"]
                    if tool in known_hub_tools:
                        # [FEAT-072.1] Handle Morning Briefing Signal
                        if tool == "trigger_morning_briefing" and hasattr(self, 'trigger_briefing_cb') and self.trigger_briefing_cb:
                            logging.info("[HUB] Triggering Morning Briefing callback.")
                            asyncio.create_task(self.trigger_briefing_cb())
                            return True

                        if tool in ["build_cv_summary", "access_personal_history"] and "archive" in self.residents:
                            res = await self.residents["archive"].call_tool(tool, params)
                            return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event, retry_count=retry_count+1, final=True)

                except Exception as e:
                    logging.error(f"[HUB] JSON parsing failed: {e}")

        # 4. Final Dispatch
        if raw_speech:
            await self._dispatch_plain_text(raw_speech, source, final=final)
        
        return raw_speech

    async def _dispatch_plain_text(self, text, source, final=True):
        await self.broadcast({
            "brain": text,
            "brain_source": source,
            "channel": "chat",
            "final": final,
            "topic": self.current_topic,
            "fuel": self.current_fuel
        })
        return text

    async def _route_expert_domain(self, query, interjection=""):
        """[FEAT-184] Vibe-based adapter selection and situational guidance."""
        try:
            if 'archive' not in self.residents:
                return {"adapter": "exp_for", "guidance": ""}
            
            # [FIX] Strict timeout to prevent triage deadlocks during node hangs
            async with asyncio.timeout(5.0):
                vibe_res = await self.residents['archive'].call_tool("query_vibe", {"query_text": query})
                vibe_data = json.loads(vibe_res.content[0].text)
                return {
                    "adapter": vibe_data.get("adapter", "exp_for"),
                    "guidance": vibe_data.get("guidance", "")
                }
        except Exception as e:
            logging.debug(f"[HUB] Vibe routing failed or timed out: {e}")
            return {"adapter": "exp_for", "guidance": ""}

    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, fuel_threshold=0.0, temperature=0.0, repetition_penalty=1.0, retry_count=0, use_lora=True):
        """[FEAT-233.5] Internal Waterfall Proxy: Handshakes the node and waits for completion."""
        if node_id not in self.residents:
            return ""
        
        # [FEAT-242.1] Handshake Tic (Gated via FEAT-365)
        enabled = True
        try:
             # Heuristic: Find config from the 'lab' resident if available
             if "lab" in self.residents and hasattr(self.residents["lab"], "config"):
                  enabled = self.residents["lab"].config.get("enable_reflexes", True)
        except Exception:
             pass

        if enabled:
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Initiating {source_name} intuition...",
                "brain_source": source_name,
                "final": False
            })

        try:
            # [Task 20.3] Identity Bedrock: Prepend shared identity to every node call
            # This describes Lab topography and residents (BKM-015 compliant).
            guidance = self.IDENTITY_BEDROCK
            if behavioral_guidance:
                guidance += f"\n[BEHAVIORAL_GUIDANCE]: {behavioral_guidance}"
            
            # [Task 1.1] Spark the node and wait for full block
            node = self.residents[node_id]
            res = await node.call_tool("think", {
                "query": query, "context": context, "tools": tools or [], 
                "behavioral_guidance": guidance,
                "temperature": temperature, "repetition_penalty": repetition_penalty,
                "use_lora": use_lora
            })
            
            result_text = str(res.content[0].text) if hasattr(res, 'content') else str(res)
            
            # [FEAT-287] Activity Latch
            if node_id == "brain" or node_id == "thought":
                self.last_activity = time.time()
                if hasattr(self, 'last_prime_callback') and self.last_prime_callback:
                    self.last_prime_callback(time.time())
            
            # Final dispatch to UI
            await self.execute_dispatch(result_text, source_name, shutdown_event=shutdown_event, retry_count=retry_count, final=True)
            return result_text
            
        except Exception as e:
            logging.error(f"[HUB] Stream from {node_id} failed: {e}")
            return ""

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
            await self._process_node_stream(
                "pinky", briefing_query, "[MODE]: DIRECT_RESPONSE", "Pinky (Briefing)",
                tools=[], behavioral_guidance="Provide a warm, enthusiastic summary of the lab's evolution.",
                retry_count=0, use_lora=self.lora_enabled
            )
        except Exception as e:
            logging.error(f"[HUB] Morning Briefing failed: {e}")

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0, turn_density=1.0):
        if retry_count > 2:
            return await self.execute_dispatch("Max retries reached.", "System", shutdown_event=shutdown_event, retry_count=retry_count, use_lora=self.lora_enabled)

        logging.info(f"[USER] Intercom Query: {query}")
        original_raw_query = query
        
        # [FEAT-356] Ledger Prepending
        if self.round_table_memory:
            previous_debate = "\n".join(self.round_table_memory)
            query = f"[PREVIOUS_DEBATE]:\n{previous_debate}\n\n[CURRENT_QUERY]: {query}"
            
        self.current_fuel = 0.0
        self.current_topic = "Casual"
        intent = None # [Task 19.4.1] Initialize as None to prevent accidental override
        self.trigger_briefing_cb = trigger_briefing_callback
        
        # [FEAT-330] Internal Muting
        mute_all = "[INTERNAL]" in query

        # [FEAT-233.9] Reset Waterfall: Clear session buffers for fresh turn
        self.session_buffers.clear()

        # 1. Lab Node Triage
        addressed_to = "MICE" # Default to collective
        triage_data_update = {} # [FIX] Initialize early
        
        # [FEAT-368] Pre-Sync Handshake: If nodes aren't ready yet, provide immediate feedback
        if "lab" not in self.residents or "pinky" not in self.residents:
            logging.warning("[HUB] Nodes not yet synchronized. Providing pre-sync Vocal Handshake.")
            handshake = "<thought> The internal neural nodes are still synchronizing. I will provide a status handshake. </thought> Narf! I am here, but I am still establishing my internal connections. Just a moment!"
            await self.broadcast({"type": "chat", "brain": handshake, "brain_source": "Pinky (Handshake)"})
            return True

        if "lab" in self.residents:
            if not mute_all:
                await self.broadcast({"type": "crosstalk", "brain": f"[HUB] Triage starting for query: {query[:30]}...", "brain_source": "System"})
            
            # [FEAT-270.2] Triage Persistence
            for triage_attempt in range(3):
                try:
                    if not mute_all:
                        await self.broadcast({
                            "type": "crosstalk", 
                            "brain": f"Triage Attempt {triage_attempt+1}...", 
                            "brain_source": "System"
                        })
                    
                    # Triage is a blocking call to establish routing
                    # [FIX] Use stable sampling for high-fidelity prompt
                    # [FEAT-339] Support auto-disabling LoRA if silicon is producing gibberish
                    t_text = await self._process_node_stream(
                        "lab", query, "", "Lab (Triage)", 
                        temperature=0.2, repetition_penalty=1.2, 
                        retry_count=retry_count, use_lora=self.lora_enabled
                    )

                    logging.info(f"[HUB] Triage Output: {t_text}")
                    # [FEAT-355] Visible Triage: Broadcast for automated verification
                    asyncio.create_task(self.broadcast({
                        "type": "crosstalk", 
                        "brain": f"[HUB] Triage Result: {t_text}", 
                        "brain_source": "System"
                    }))

                    t_clean = self.bridge_signal_clean(t_text)
                    if not t_clean:
                        # [FEAT-339] Gibberish Guard: Downshift MUST happen before exception
                        # [FEAT-342] Silicon Scythe: Escalate to H3 reset if base model is screaming
                        # [FIX] Do NOT scythe if it's a connection error (vLLM is just slow)
                        is_connection_error = "vLLM connection failed" in t_text or "Error:" in t_text
                        
                        if not is_connection_error:
                            self.consecutive_parse_failures += 1
                            if self.consecutive_parse_failures >= 3 and self.lora_enabled:
                                self.lora_enabled = False
                                msg = "[ALARM] Silicon instability detected (Gibberish). Downshifting to Base Model (No-LoRA)."
                                logging.error(msg)
                                await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
                                await self.broadcast({"type": "status", "state": "downshifted", "message": "SAFETY MODE: LoRA Disabled."})

                            if (self.consecutive_parse_failures >= 5) or (not self.lora_enabled and self.consecutive_parse_failures >= 2):
                                if self.hibernate_callback:
                                    msg = "[ALARM] Base model corruption detected (Screaming). Triggering H2 Silicon Scythe."
                                    logging.error(msg)
                                    await self.broadcast({"type": "crosstalk", "brain": msg, "brain_source": "System"})
                                    await self.broadcast({"type": "status", "state": "recovery", "message": "AUTONOMOUS_RECOVERY: Resetting Silicon."})
                                    # [FIX] Task 12.1/12.2: Use level=2 (Lean Sleep) and enable RECOVERY to keep the Lobby alive
                                    asyncio.create_task(self.hibernate_callback(level=2, recover=True))
                        else:
                            logging.warning("[HUB] Triage yielded connection error. Retrying without scythe penalty.")

                        logging.error(f"[HUB] TRIAGE_PARSE_FAILURE: Raw output follows:\n{t_text}")
                        raise ValueError("TRIAGE_PARSE_FAILURE")

                    self.consecutive_parse_failures = 0 # Reset on success
                    self.triage_failures = 0 # [FIX] Reset on successful parse
                    if isinstance(t_clean, dict):
                        t_parsed = t_clean
                    else:
                        t_parsed = json.loads(t_clean)

                    self.triage_failures = 0 # [FIX] Reset on successful parse
                    triage_data_update = {k.lower(): v for k, v in t_parsed.items()}

                    # [FEAT-244] Speaker Masking Scalar
                    addressed_to = triage_data_update.get("addressed_to", "MICE").upper()

                    # Multiplicative Fuel Function
                    raw_imp = float(triage_data_update.get("importance", 0.5))
                    raw_cas = float(triage_data_update.get("casual", 0.5))
                    raw_int = float(triage_data_update.get("intrigue", 0.5))
                    
                    # [Task 19.3.1] Removed hardcoded fuel boost. Trust the LLM's assessment.
                    self.current_fuel = (((1.0 - raw_cas) * (raw_int + raw_imp)) / 2.0)
                    self.current_fuel = min(1.0, self.current_fuel) # Clamp to 1.0
                    
                    logging.info(f"[HUB] Triage: Importance={raw_imp} Casual={raw_cas} Intrigue={raw_int} -> FUEL={self.current_fuel:.2f}")

                    # [FEAT-246] Unified Vibe Schema

                    self.current_topic = triage_data_update.get("vibe", "PINKY_INTERFACE")
                    intent = triage_data_update.get("intent", "STRATEGIC")

                    # [REVISION-17.2] Direct Address Force
                    if addressed_to in ["BRAIN", "THOUGHT", "DEEP THOUGHT"]:
                        logging.info(f"[HUB] Direct Address: {addressed_to}. Forcing Sovereign promotion.")
                        self.current_fuel = max(0.65, self.current_fuel)
                    elif addressed_to == "PINKY" and self.current_fuel > 0.2:
                        logging.info("[HUB] Direct Address: Pinky. Forcing local-only turn.")
                        self.current_fuel = min(0.15, self.current_fuel)

                    if not mute_all:
                        await self.broadcast({"type": "status", "state": "triage_complete", "message": "Routing determined.", "brain_source": "System"})
                        await self.broadcast({"type": "crosstalk", "brain": "[HUB] Triage successful. Routing logic determined.", "brain_source": "System"})
                    break # SUCCESS

                
                except Exception as e:
                    logging.warning(f"[HUB] Triage Attempt {triage_attempt+1} failed: {e}")
                    # [Task 2.1] Forensic Record: Capture raw output on failure
                    try:
                        f_path = os.path.join(self.config_dir, "../logs/triage_forensic.log")
                        with open(f_path, "a") as f:
                            f.write(f"\n--- TRIAGE FAIL {datetime.datetime.now()} ---\n{t_text}\n--- END ---\n")
                    except Exception:
                        pass
                    
                    if triage_attempt < 2:
                        await asyncio.sleep(2.0 * (triage_attempt + 1))
                    else:
                        # [FIX] Task 2.5: Only penalize if NOT a connection error
                        is_connection_error = "vLLM connection failed" in t_text or "Error:" in t_text
                        if not is_connection_error:
                            self.triage_failures += 1
                            if self.triage_failures >= 3:
                                await self.broadcast({"type": "status", "state": "error", "message": "☢️ SILICON LOBOTOMY DETECTED. Resetting..."})
                                os._exit(1)
                        else:
                            logging.warning("[HUB] Triage connection error in final attempt. Providing Vocal Handshake.")
                            # [FEAT-368] Vocal Handshake: If engine is down, Pinky speaks for the system
                            handshake = "<thought> The heavy engine is still warming up. I will provide a status handshake. </thought> Narf! I am hearing you, but I am still warming up my archives. Just a moment!"
                            await self.broadcast({"type": "chat", "brain": handshake, "brain_source": "Pinky (Handshake)"})
                        
                        self.current_fuel = 0.2

        fuel_start = self.current_fuel
        situational_guidance = triage_data_update.get("hints", "")
        selected_expert = triage_data_update.get("domain", "standard")

        # [FEAT-231.1] Operational Shortcut
        if intent == "OPERATIONAL":
            if "pinky" in self.residents:
                p_res = await self.residents["pinky"].call_tool("think", {"query": f"[SYSTEM_DIRECTIVE]: {query}", "context": "OPERATIONAL_SHORTCUT"})
                return await self.execute_dispatch(p_res.content[0].text, "System", retry_count=retry_count, final=True)

        # 3. Proactive Archivist (RAG context)
        historical_context = ""
        archival_map_context = ""
        
        # [Task 19.4.1] Restore 3-Tier Semantic Map context
        if self.semantic_map:
            strat = len(self.semantic_map.get("strategic_layer", []))
            themes = list(self.semantic_map.get("analytical_layer", {}).keys())
            archival_map_context = f"\n[ARCHIVAL_TOPOGRAPHY]: Archive contains {strat} Diamond anchors across themes: {themes}."

        # [Task 19.4.1] Trigger RAG on RECALL intent instead of hardcoded regex
        if intent == "RECALL" and "archive" in self.residents:
            try:
                # [FEAT-306] Fix Context Leaking. Pass raw query to RAG, not debate-expanded.
                res_context = await self.residents["archive"].call_tool("get_context", {"query": original_raw_query})
                historical_context = str(res_context.content[0].text)
                
                # [FEAT-173] Agentic Backtracking: Retry if context is thin
                if len(historical_context) < 150 or "No relevant artifacts" in historical_context:
                    logging.info("[HUB] RAG result thin. Triggering Agentic Backtracking...")
                    # Search broadly using the situation/hints from triage
                    retry_query = f"{situational_guidance} {query}"
                    res_retry = await self.residents["archive"].call_tool("get_context", {"query": retry_query, "n_results": 5})
                    historical_context += f"\n[BACKTRACK_RETRIEVAL]:\n{res_retry.content[0].text}"
            except Exception:
                pass

        # [FEAT-088] Inject RAG Context into query for all nodes
        if historical_context:
            query = f"[HISTORICAL_TRUTH]: {historical_context}\n\n[USER_QUERY]: {original_raw_query}"

        # 4. Waterfall Local Inference (Cascading Spark)
        pinky_text = ""
        shadow_text = ""
        brain_full = ""
        
        async def run_pinky():
            nonlocal pinky_text
            p_context = f"ROUTE: PINKY -> BRAIN\nFUEL: {fuel_start:.2f} | TOPIC: {self.current_topic}\n"
            pinky_text = await self._process_node_stream(
                "pinky", query, p_context, "Pinky (Triage)",
                tools=["ask_brain", "think", "vram_vibe_check", "get_lab_health"],
                behavioral_guidance=situational_guidance or "Standard brevity. Focus on natural interaction.",
                shutdown_event=shutdown_event,
                retry_count=retry_count,
                use_lora=self.lora_enabled
            )

        async def run_brain_leg():
            nonlocal shadow_text
            thought_online = self.get_vram_status()
            threshold = 0.0 if not thought_online else 0.2
            role = "TECHNICAL_REASONER" if not thought_online else "TECHNICAL_INTUITION"
            
            if fuel_start > threshold:
                # [FEAT-233.8] Overhearing Pinky: Context Warming
                overheard = self.session_buffers.get("pinky", "")
                s_context = f"FUEL: {fuel_start:.2f} | ROLE: {role}\n[OVERHEARD_GATEWAY]: {overheard}"
                shadow_text = await self._process_node_stream(
                    "brain", query, s_context, "The Brain",
                    tools=["ask_brain", "think"],
                    behavioral_guidance=situational_guidance or "Provide immediate technical intuition.",
                    shutdown_event=shutdown_event,
                    retry_count=retry_count,
                    use_lora=self.lora_enabled
                )

        # [Task 1.2] Cascading Spark: Pinky -> Brain -> Deep Thought
        pinky_task = asyncio.create_task(run_pinky())
        brain_leg_task = None
        
        # 1. Brain Warming
        while not pinky_task.done():
            # If Pinky has started speaking, or if fuel is already high enough
            if len(self.session_buffers.get("pinky", "").split()) >= 3 or fuel_start > 0.4:
                logging.info("[HUB] Waterfall: Overheard Pinky. Cascading to Brain...")
                brain_leg_task = asyncio.create_task(run_brain_leg())
                break
            await asyncio.sleep(0.1)

        # [Task 1.3] Deep Thought Leg
        # Wait for either local node to finish OR for fuel spike
        while True:
            if pinky_task.done() and (not brain_leg_task or brain_leg_task.done()):
                break
            
            if self.current_fuel > 0.6:
                logging.info(f"[HUB] Waterfall: Dynamic Fuel ({self.current_fuel:.2f}) triggered Deep Thought early.")
                break
                
            await asyncio.sleep(0.5)

        # 5. Deep Thought (Final Waterfall Leg)
        thought_online = self.get_vram_status()
        can_run_thought = thought_online and "thought" in self.residents
        
        if (can_run_thought or not thought_online) and self.current_fuel > 0.6 and addressed_to in ["BRAIN", "MICE", "THOUGHT", "DEEP THOUGHT"]:
            target_node = "thought" if can_run_thought else "brain"
            source_label = "Deep Thought" if can_run_thought else "The Brain (Failover)"
            
            # [FEAT-233.8] Double Warming: Overhearing Pinky + Brain
            b_overheard_p = self.session_buffers.get("pinky", "")
            b_overheard_b = self.session_buffers.get("brain", "")
            
            b_context = ""
            if historical_context:
                b_context += f"[HISTORICAL_TRUTH]:\n{historical_context}\n\n"
            if archival_map_context:
                b_context += f"{archival_map_context}\n\n"
            
            b_context += f"[PINKY_HEARING]: {b_overheard_p}\n"
            b_context += f"[BRAIN_INTUITION]: {b_overheard_b}\n"

            verbosity = "Provide full-spectrum exhaustive synthesis." if self.current_fuel > 0.8 else "Provide moderate technical depth."
            
            brain_full = await self._process_node_stream(
                target_node, query, b_context, source_label,
                behavioral_guidance=f"{verbosity} (Expert Domain: {selected_expert})",
                tools=["read_chronological_excerpts", "peek_strategic_map", "update_whiteboard"],
                shutdown_event=shutdown_event,
                retry_count=retry_count,
                use_lora=self.lora_enabled
            )
            
            # Cognitive Audit
            if brain_full and not getattr(self, "is_extraction", False):
                if not self.auditor and "pinky" in self.residents:
                    self.auditor = CognitiveAudit(self.residents["pinky"])
                if self.auditor and not await self.auditor.audit_technical_truth(query, brain_full, ""):
                    retract_res = await self.residents["pinky"].call_tool("think", {"query": "[AUDIT_FAILURE]", "context": brain_full[:100]})
                    retract_full = str(retract_res.content[0].text)
                    await self.execute_dispatch(retract_full, "Pinky (Retraction)", retry_count=retry_count+1, final=True)
                    return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

            if brain_full:
                await self.evaluate_grounding("Deep Thought", brain_full, self.current_fuel, shutdown_event, retry_count=retry_count, use_lora=self.lora_enabled)

        # [FEAT-356] Ledger Appending
        turn_summary = f"USER: {original_raw_query}\n"
        if pinky_text:
            turn_summary += f"PINKY: {pinky_text}\n"
        if shadow_text:
            turn_summary += f"BRAIN: {shadow_text}\n"
        if brain_full:
            turn_summary += f"THOUGHT: {brain_full}\n"
        
        if turn_summary.strip() != f"USER: {original_raw_query}":
            self.round_table_memory.append(turn_summary.strip())

        return True

    async def evaluate_grounding(self, source, text, fuel, shutdown_event, retry_count=0, use_lora=True):
        """[FEAT-247] Physical Audit Gate: Pinky audits Deep Thought for feasibility."""
        # [REVISION-17.9] Lower gate to 0.5 to ensure common technical tasks are audited
        if "pinky" not in self.residents or fuel < 0.5:
            return
        
        # Refined Grounding Query
        cooldown_query = (
            f"The {source} has proposed a strategy. Audit this for physical feasibility "
            "(VRAM/Time/Complexity) and provide a 1-sentence 'Reality Check' "
            "from the perspective of the Lab's hardware constraints."
        )
        
        try:
            # [BKM-015.1] Natural persona audit
            res_res = await self.residents["pinky"].call_tool("think", {
                "query": cooldown_query, 
                "context": f"[PROPOSED_STRATEGY]: {text[:1000]}",
                "use_lora": use_lora
            })
            res_full = str(res_res.content[0].text)
            await self.execute_dispatch(res_full, "Pinky (Physical Audit)", retry_count=retry_count+1, final=True)
        except Exception:
            pass
