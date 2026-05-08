import asyncio
import json
import logging
import re
import os
import time
import datetime
from infra.cognitive_audit import CognitiveAudit

class CognitiveHub:
    """
    [FEAT-145] Cognitive Hub: Modularized Reasoning & Dispatch Logic.
    [FEAT-203] Bicameral Bridge: Hardened neural signal extraction.
    [FEAT-239] Neural Action Tags: Natural language steering hints.
    [FEAT-240] Phase 2: Native MCP Sampling Relay.
    """
    def __init__(self, residents, broadcast_callback, sensory_manager, get_vram_status, trigger_morning_briefing, monitor_task_with_tics, last_prime_callback=None, waterfall_queue=None):
        from collections import defaultdict
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.get_vram_status = get_vram_status
        self.trigger_morning_briefing_cb = trigger_morning_briefing
        self.monitor_task_with_tics = monitor_task_with_tics
        self.last_prime_callback = last_prime_callback
        self.waterfall_queue = waterfall_queue # [FEAT-233.2] Internal Token Buffer
        
        # [FEAT-332] Dynamic Streaming Modes
        self.streaming_config = {
            "lab": "WATERFALL",
            "pinky": "WATERFALL",
            "brain": "WATERFALL",
            "shadow": "WATERFALL"
        }
        
        # [FEAT-233.7] Session Buffers: Real-time context for inter-node overhearing
        self.session_buffers = defaultdict(str)
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
            # [DEBUG] Trace waterfall flow
            if "triage" not in source:
                logging.debug(f"[WATERFALL] Ingested token from {source} ({len(self.session_buffers[source])} total)")

    def bridge_signal_clean(self, text):
        """[FEAT-220.1] Extract and sanitize the FIRST JSON block from raw LLM output. Hardened for vLLM 3B."""
        if not text:
            return None

        # [Task 2.2] Harden: Handle thinking blocks or pex noise
        # Strip <thought> tags if present
        text = re.sub(r"<thought>.*?</thought>", "", text, flags=re.DOTALL)
        
        if "{" not in text:
            return None

        # 1. Strip markdown blocks
        clean = re.sub(r"```json\s*|\s*```", "", text).strip()

        # 2. Extract JSON blocks via balanced brace matching
        json_blocks = []
        stack = 0
        start_idx = -1
        
        for i, char in enumerate(clean):
            if char == '{':
                if stack == 0:
                    start_idx = i
                stack += 1
            elif char == '}':
                stack -= 1
                if stack == 0 and start_idx != -1:
                    json_blocks.append(clean[start_idx:i+1])
                    start_idx = -1

        if not json_blocks:
            # Fallback to greedy regex
            match = re.search(r'(\{.*\})', clean, re.DOTALL)
            if match:
                json_blocks = [match.group(1)]
            else:
                return None

        # 3. Parse first valid block
        for block in json_blocks:
            try:
                # [FEAT-220.2] Structural Sanitization
                block = block.replace("{{", "{").replace("}}", "}")
                block = block.replace("'", '"')
                # Fix common JSON errors from small models
                block = re.sub(r",\s*}", "}", block) # trailing comma
                block = block.replace("True", "true").replace("False", "false")
                block = block.replace('"::', '":')
                return json.loads(block)
            except Exception:
                continue
        return None

    async def execute_dispatch(self, text, source, shutdown_event=None, is_internal=False, original_query=None, retry_count=0, final=True):
        """
        [FEAT-238.1] Combined Dispatch: Persona Speech + Tool Action.
        Ensures persona is maintained even when tools are used for steering.
        """
        if not text:
            return
            
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
        
        # [FEAT-110] Shadow Moat
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
                        for val in data.values():
                            if isinstance(val, str):
                                for vt in valid_tools:
                                    if vt in val.lower():
                                        tool = vt
                                        break
                                if tool:
                                    break

                    # Handle Known Tools
                    if tool == "ask_brain":
                        self.current_fuel = 1.0
                        if not raw_speech:
                            raw_speech = "Narf! I'll ask the Brain for you."

                    if tool in ["think"]:
                        # If Pinky or Shadow calls think on themselves, it's a VETO
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
                            return await self._dispatch_plain_text(raw_speech, source, is_internal, final=final)
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
                            return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event, final=True)

                except Exception as e:
                    logging.error(f"[HUB] JSON parsing failed: {e}")

        # 4. Final Dispatch
        if raw_speech:
            await self._dispatch_plain_text(raw_speech, source, is_internal, final=final)
        
        return raw_speech

    async def _dispatch_plain_text(self, text, source, is_internal, final=True):
        await self.broadcast({
            "brain": text,
            "brain_source": source,
            "channel": "chat",
            "is_internal": is_internal,
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

    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, fuel_threshold=0.0, is_internal=False, temperature=0.0, repetition_penalty=1.0):
        """[FEAT-233.5] Internal Waterfall Proxy: Handshakes the node and waits for completion."""
        if node_id not in self.residents:
            return ""
        
        # [FEAT-242.1] Handshake Tic (Only if not internal)
        if not is_internal:
            await self.broadcast({
                "type": "crosstalk",
                "brain": f"Initiating {source_name} intuition...",
                "brain_source": source_name,
                "final": False
            })

        try:
            # [Task 1.1] Spark the node and wait for full block
            # Real-time overhearing happens via handle_stream_ingest -> on_token
            node = self.residents[node_id]
            res = await node.call_tool("think", {
                "query": query, "context": context, "tools": tools or [], 
                "behavioral_guidance": behavioral_guidance, "internal": is_internal,
                "temperature": temperature, "repetition_penalty": repetition_penalty
            })
            
            result_text = str(res.content[0].text) if hasattr(res, 'content') else str(res)
            
            # [FEAT-287] Activity Latch
            if node_id == "brain" or node_id == "shadow":
                self.last_activity = time.time()
                if hasattr(self, 'last_prime_callback') and self.last_prime_callback:
                    self.last_prime_callback(time.time())
            
            # Final dispatch to UI
            await self.execute_dispatch(result_text, source_name, shutdown_event=shutdown_event, is_internal=is_internal, final=True)
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
                tools=[], behavioral_guidance="Provide a warm, enthusiastic summary of the lab's evolution."
            )
        except Exception as e:
            logging.error(f"[HUB] Morning Briefing failed: {e}")

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0, turn_density=1.0):
        if retry_count > 2:
            return await self.execute_dispatch("Max retries reached.", "System", shutdown_event=shutdown_event)

        logging.info(f"[USER] Intercom Query: {query}")
        self.current_fuel = 0.0
        self.current_topic = "Casual"
        intent = "STRATEGIC"
        self.trigger_briefing_cb = trigger_briefing_callback
        
        # [FEAT-330] Internal Muting
        mute_all = "[INTERNAL]" in query

        # [FEAT-233.9] Reset Waterfall: Clear session buffers for fresh turn
        self.session_buffers.clear()

        # 1. Lab Node Triage
        addressed_to = "MICE" # Default to collective
        triage_data_update = {} # [FIX] Initialize early
        
        if "lab" in self.residents:
            if not mute_all:
                await self.broadcast({"type": "crosstalk", "brain": f"[HUB] Triage starting for query: {query[:30]}...", "brain_source": "System"})
            
            # [FEAT-270.2] Triage Persistence
            for triage_attempt in range(3):
                try:
                    if not mute_all:
                        await self.broadcast({"type": "status", "state": "triage_start", "message": f"Triage Attempt {triage_attempt+1}...", "brain_source": "System"})
                    
                    # Triage is a blocking call to establish routing
                    # [FIX] Use stable sampling for high-fidelity prompt
                    t_text = await self._process_node_stream("lab", query, "", "Lab (Triage)", is_internal=True, temperature=0.2, repetition_penalty=1.2)

                    logging.info(f"[HUB] Triage Output: {t_text}")

                    t_clean = self.bridge_signal_clean(t_text)
                    if not t_clean:
                        logging.error(f"[HUB] TRIAGE_PARSE_FAILURE: Raw output follows:\n{t_text}")
                        raise ValueError("TRIAGE_PARSE_FAILURE")

                    # [FEAT-270.3] Type-Agnostic Triage Parser (ERR-06)
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
                    self.current_fuel = ((1.0 - raw_cas) * (raw_int + raw_imp)) / 2.0

                    logging.info(f"[HUB] Triage: Importance={raw_imp} Casual={raw_cas} Intrigue={raw_int} -> FUEL={self.current_fuel:.2f}")

                    # [FEAT-246] Unified Vibe Schema

                    self.current_topic = triage_data_update.get("vibe", "PINKY_INTERFACE")
                    intent = triage_data_update.get("intent", "STRATEGIC")

                    # [REVISION-17.2] Direct Address Force
                    if addressed_to == "BRAIN":
                        logging.info("[HUB] Direct Address: Brain. Forcing Sovereign promotion.")
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
                    except Exception: pass
                    
                    if triage_attempt < 2:
                        await asyncio.sleep(2.0 * (triage_attempt + 1))
                    else:
                        self.triage_failures += 1
                        if self.triage_failures >= 3:
                            await self.broadcast({"type": "status", "state": "error", "message": "☢️ SILICON LOBOTOMY DETECTED. Resetting..."})
                            os._exit(1)
                        
                        self.current_fuel = 0.2
                        intent = "STRATEGIC"

        fuel_start = self.current_fuel
        situational_guidance = triage_data_update.get("hints", "")
        selected_expert = triage_data_update.get("domain", "standard")

        # [FEAT-231.1] Operational Shortcut
        if intent == "OPERATIONAL":
            if "pinky" in self.residents:
                p_res = await self.residents["pinky"].call_tool("think", {"query": f"[SYSTEM_DIRECTIVE]: {query}", "context": "OPERATIONAL_SHORTCUT"})
                return await self.execute_dispatch(p_res.content[0].text, "System", final=True)

        # 3. Proactive Archivist (RAG context)
        historical_context = ""
        is_history_query = (self.current_topic == "PINKY_RECALL" or intent == "RECALL")
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            try:
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year_match.group(1)}"})
                historical_context = str(res_context.content[0].text)
            except Exception: pass

        # 4. Waterfall Local Inference (Cascading Spark)
        pinky_text = ""
        shadow_text = ""
        
        async def run_pinky():
            nonlocal pinky_text
            mute_pinky = addressed_to not in ["PINKY", "MICE"]
            p_context = (f"ROUTE: PINKY -> BRAIN\nFUEL: {fuel_start:.2f} | TOPIC: {self.current_topic}\n"
                         f"MODE: " + ("FRAME_ONLY" if fuel_start > 0.6 else "DIRECT_RESPONSE"))
            pinky_text = await self._process_node_stream(
                "pinky", query, p_context, "Pinky (Triage)",
                tools=["ask_brain", "think", "vram_vibe_check", "get_lab_health"],
                behavioral_guidance=situational_guidance or "Standard brevity. Focus on natural interaction.",
                shutdown_event=shutdown_event,
                is_internal=mute_pinky
            )

        async def run_shadow():
            nonlocal shadow_text
            brain_online = self.get_vram_status()
            threshold = 0.0 if not brain_online else 0.2
            role = "TECHNICAL_REASONER" if not brain_online else "TECHNICAL_INTUITION"
            mute_shadow = addressed_to not in ["BRAIN", "MICE"]
            
            if fuel_start > threshold:
                # [FEAT-233.8] Overhearing Pinky: Context Warming
                overheard = self.session_buffers.get("pinky", "")
                s_context = f"FUEL: {fuel_start:.2f} | ROLE: {role}\n[OVERHEARD_GATEWAY]: {overheard}"
                shadow_text = await self._process_node_stream(
                    "shadow", query, s_context, "Brain (Intuition)",
                    tools=["ask_brain", "think"],
                    behavioral_guidance=situational_guidance or "Provide immediate technical intuition.",
                    shutdown_event=shutdown_event,
                    is_internal=mute_shadow
                )

        # [Task 1.2] Cascading Spark: Pinky -> Shadow -> Brain
        pinky_task = asyncio.create_task(run_pinky())
        shadow_task = None
        
        # 1. Shadow Warming
        while not pinky_task.done():
            # If Pinky has started speaking, or if fuel is already high enough
            if len(self.session_buffers.get("pinky", "").split()) >= 3 or fuel_start > 0.4:
                logging.info("[HUB] Waterfall: Overheard Pinky. Cascading to Shadow...")
                shadow_task = asyncio.create_task(run_shadow())
                break
            await asyncio.sleep(0.1)

        # [Task 1.3] Brain Leg
        # Wait for either local node to finish OR for fuel spike
        while True:
            if pinky_task.done() and (not shadow_task or shadow_task.done()):
                break
            
            if self.current_fuel > 0.6:
                logging.info(f"[HUB] Waterfall: Dynamic Fuel ({self.current_fuel:.2f}) triggered Brain early.")
                break
                
            await asyncio.sleep(0.5)

        # 5. Sovereign Brain (Final Waterfall Leg)
        brain_online = self.get_vram_status()
        can_run_brain = brain_online and "brain" in self.residents
        
        if (can_run_brain or not brain_online) and self.current_fuel > 0.6 and addressed_to in ["BRAIN", "MICE"]:
            target_node = "brain" if can_run_brain else "shadow"
            source_label = "Brain (Result)" if can_run_brain else "Shadow (Failover)"
            
            # [FEAT-233.8] Double Warming: Overhearing Pinky + Shadow
            b_overheard_p = self.session_buffers.get("pinky", "")
            b_overheard_s = self.session_buffers.get("shadow", "")
            
            b_context = ""
            if historical_context:
                b_context += f"[HISTORICAL_TRUTH]:\n{historical_context}\n\n"
            
            b_context += f"[PINKY_HEARING]: {b_overheard_p}\n"
            b_context += f"[SHADOW_INTUITION]: {b_overheard_s}\n"

            verbosity = "Provide full-spectrum exhaustive synthesis." if self.current_fuel > 0.8 else "Provide moderate technical depth."
            
            brain_full = await self._process_node_stream(
                target_node, query, b_context, source_label,
                behavioral_guidance=f"{verbosity} (Expert Domain: {selected_expert})",
                tools=["read_chronological_excerpts", "peek_strategic_map", "update_whiteboard"],
                shutdown_event=shutdown_event
            )
            
            # Cognitive Audit
            if brain_full and not getattr(self, "is_extraction", False):
                if not self.auditor and "pinky" in self.residents:
                    self.auditor = CognitiveAudit(self.residents["pinky"])
                if self.auditor and not await self.auditor.audit_technical_truth(query, brain_full, ""):
                    retract_res = await self.residents["pinky"].call_tool("think", {"query": "[AUDIT_FAILURE]", "context": brain_full[:100], "internal": True})
                    retract_full = str(retract_res.content[0].text)
                    await self.execute_dispatch(retract_full, "Pinky (Retraction)", final=True)
                    return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

            if brain_full:
                await self.evaluate_grounding("Brain", brain_full, self.current_fuel, shutdown_event)

        return True

    async def evaluate_grounding(self, source, text, fuel, shutdown_event):
        """[FEAT-247] Physical Audit Gate: Pinky audits Brain for feasibility."""
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
                "internal": True
            })
            res_full = str(res_res.content[0].text)
            await self.execute_dispatch(res_full, "Pinky (Physical Audit)", is_internal=True, final=True)
        except Exception:
            pass
