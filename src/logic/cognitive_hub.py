import asyncio
import json
import logging
import re
import os
from infra.cognitive_audit import CognitiveAudit

class CognitiveHub:
    """
    [FEAT-145] Cognitive Hub: Modularized Reasoning & Dispatch Logic.
    [FEAT-203] Bicameral Bridge: Hardened neural signal extraction.
    [FEAT-239] Neural Action Tags: Natural language steering hints.
    [FEAT-240] Phase 2: Native MCP Sampling Relay.
    """
    def __init__(self, residents, broadcast_callback, sensory_manager, brain_online_callback, get_oracle_signal_callback, monitor_task_with_tics_callback):
        self.residents = residents
        self.broadcast = broadcast_callback
        self.sensory = sensory_manager
        self.brain_online = brain_online_callback
        self.get_oracle_signal = get_oracle_signal_callback
        self.monitor_task_with_tics = monitor_task_with_tics_callback
        self.auditor = None  # [FEAT-190] The Judge
        
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
        
        self.resonant_history = []
        self.current_fuel = 0.0
        self.current_topic = "Casual"

    def bridge_signal_clean(self, text):
        """
        [FEAT-203] Bicameral Bridge Signal Cleaning Utility.
        Robustly extracts and sanitizes JSON from 3B model outputs.
        """
        if "{" not in text:
            return None

        # 1. Strip markdown blocks
        clean = re.sub(r"```json\s*|\s*```", "", text).strip()

        # 2. Find innermost { } block
        match = re.search(r'(\{.*\})', clean, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # [HARDENING] Salvage truncated JSON tool calls
            if '{"tool":' in clean:
                start_idx = clean.find('{"tool":')
                json_str = clean[start_idx:]
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    if json_str.count('"') % 2 != 0:
                        json_str += '"'
                    json_str += '}' * (open_braces - close_braces)
            else:
                return None

        # 3. Structural Sanitization
        json_str = json_str.replace("{{", "{").replace("}}", "}")
        json_str = json_str.replace("'", '"')
        json_str = json_str.replace("True", "true").replace("False", "false")
        json_str = json_str.replace('"::', '":')

        return json_str

    async def execute_dispatch(self, text, source, shutdown_event=None, is_internal=False, original_query=None, retry_count=0, final=True):
        """
        [FEAT-238.1] Combined Dispatch: Persona Speech + Tool Action.
        Ensures persona is maintained even when tools are used for steering.
        """
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
                logging.info(f"[HUB] Action Tag: UPLINK via {source}. Boosting Fuel.")
                self.current_fuel = 1.0
            elif action == "THINK MORE":
                logging.info(f"[HUB] Action Tag: THINK MORE via {source}. Boosting Fuel.")
                self.current_fuel = min(1.0, self.current_fuel + 0.3)

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
                    data = json.loads(sanitized)
                    tool = data.get("tool")
                    params = data.get("parameters", {})

                    # [HARDENING] Deep Search for sloppy JSON tool names
                    if not tool:
                        valid_tools = ["ask_brain", "shallow_think", "reply_to_user", "close_lab", "generate_bkm", "access_personal_history", "build_cv_summary"]
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

                    if tool == "shallow_think":
                        # If Pinky or Shadow calls shallow_think on themselves, it's a VETO
                        self.current_fuel = 0.0
                        if not raw_speech:
                            raw_speech = params.get("task") or params.get("context") or "Narf! Thinking fast."

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
                    primary_entry_points = ["facilitate", "shallow_think", "deep_think", "triage_situational_vibe", "native_sample"]
                    if tool in primary_entry_points and tool != "shallow_think": # shallow_think is now a veto signal
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
        """[FEAT-184] Vibe-based adapter selection."""
        try:
            if 'archive' not in self.residents:
                return "exp_for"
            vibe_res = await self.residents['archive'].call_tool("query_vibe", {"query_text": query})
            vibe_json = vibe_res.content[0].text
            vibe_data = json.loads(vibe_json)
            return vibe_data.get("adapter", "exp_for")
        except Exception:
            return "exp_for"

    async def _process_node_stream(self, node_id, query, context, source_name, tools=None, behavioral_guidance="", shutdown_event=None, fuel_threshold=0.0):
        """[FEAT-233.4] Internal Token Buffer & Stream Parser."""
        if node_id not in self.residents:
            return ""
        
        full_text = ""
        # [FEAT-242.1] Handshake Tic
        await self.broadcast({
            "type": "crosstalk",
            "brain": f"Initiating {source_name} intuition...",
            "final": False
        })

        try:
            generator = await self.residents[node_id].create_message(
                query=query,
                context=context,
                tools=tools,
                behavioral_guidance=behavioral_guidance
            )
            
            async for token in generator:
                full_text += token
                # Mid-stream parsing for [ACTION] tags or fuel boosts could go here
            
            if full_text:
                # Buffering check: Only dispatch to UI once node finishes (Paragraph Pop)
                await self.execute_dispatch(full_text, source_name, shutdown_event=shutdown_event, final=True)
            
            return full_text
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

        # [FEAT-072.1] Auto-Trigger Briefing logic
        if "briefing" in query.lower() or "summary" in query.lower():
             await self.trigger_morning_briefing()

        # 1. Lab Node Triage
        addressed_to = "MICE" # Default to collective
        if "lab" in self.residents:
            try:
                # Triage is still a single block for logic reasons
                t_res = await self.residents["lab"].call_tool("native_sample", {"query": query})
                t_clean = self.bridge_signal_clean(t_res.content[0].text)
                if t_clean:
                    t_parsed = json.loads(t_clean)
                    triage_data_update = {k.lower(): v for k, v in t_parsed.items()}
                    
                    # [FEAT-244] Speaker Masking Scalar
                    addressed_to = triage_data_update.get("addressed_to", "MICE").upper()

                    # Multiplicative Fuel Function
                    raw_imp = float(triage_data_update.get("importance", 0.5))
                    raw_cas = float(triage_data_update.get("casual", 0.5))
                    raw_int = float(triage_data_update.get("intrigue", 0.5))
                    self.current_fuel = ((1.0 - raw_cas) * (raw_int + raw_imp)) / 2.0
                    
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
            except Exception as e:
                logging.error(f"[HUB] Triage Failed: {e}")
                self.current_fuel = 0.2
                intent = "STRATEGIC"

        fuel_start = self.current_fuel

        # [FEAT-231.1] Operational Shortcut
        if intent == "OPERATIONAL":
            if "pinky" in self.residents:
                p_res = await self.residents["pinky"].call_tool("native_sample", {"query": f"[SYSTEM_DIRECTIVE]: {query}", "context": "OPERATIONAL_SHORTCUT"})
                return await self.execute_dispatch(p_res.content[0].text, "System", final=True)

        selected_expert = await self._route_expert_domain(query) if intent != "CASUAL" else "standard"

        # 3. Proactive Archivist
        historical_context = ""
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            try:
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year_match.group(1)}"})
                historical_context = str(res_context.content[0].text)
            except Exception:
                pass

        # 4. Parallel Local Inference (Streaming)
        pinky_text = ""
        shadow_text = ""
        
        async def run_pinky():
            nonlocal pinky_text
            # [FEAT-244] Pinky Muting
            if addressed_to in ["PINKY", "MICE"]:
                p_context = (f"[ROUTE]: PINKY -> BRAIN\n[FUEL]: {fuel_start:.2f} | [TOPIC]: {self.current_topic}\n"
                             f"[MODE]: " + ("FRAME_ONLY" if fuel_start > 0.6 else "DIRECT_RESPONSE"))
                pinky_text = await self._process_node_stream(
                    "pinky", query, p_context, "Pinky (Triage)",
                    tools=["ask_brain", "shallow_think", "vram_vibe_check", "get_lab_health"],
                    shutdown_event=shutdown_event
                )

        async def run_shadow():
            nonlocal shadow_text
            # [FEAT-229.2] Shadow Overhear Pivot (Threshold 0.2)
            # [FEAT-244] Shadow Muting (Only if BRAIN or MICE are addressed)
            if fuel_start > 0.2 and addressed_to in ["BRAIN", "MICE"]:
                s_context = (f"[FUEL]: {fuel_start:.2f} | [ROLE]: TECHNICAL_INTUITION")
                shadow_text = await self._process_node_stream(
                    "shadow", query, s_context, "Brain (Intuition)",
                    tools=["ask_brain", "shallow_think"],
                    shutdown_event=shutdown_event
                )

        await asyncio.gather(run_pinky(), run_shadow())

        # 5. Sovereign Brain (Streaming)
        # [FEAT-244] Brain Muting
        if self.brain_online and "brain" in self.residents and self.current_fuel > 0.6 and addressed_to in ["BRAIN", "MICE"]:
            b_context = ""
            if historical_context:
                b_context += f"[HISTORICAL_TRUTH]:\n{historical_context}\n\n"
            if pinky_text:
                b_context += f"[PINKY_GATEWAY_FRAME]: {pinky_text}\n"
            if shadow_text:
                b_context += f"[SHADOW_INTUITION]: {shadow_text}\n"

            verbosity = "Provide full-spectrum exhaustive synthesis." if self.current_fuel > 0.8 else "Provide moderate technical depth."
            
            brain_full = await self._process_node_stream(
                "brain", query, b_context, "Brain (Result)",
                behavioral_guidance=f"{verbosity} (Expert Domain: {selected_expert})",
                tools=["read_chronological_excerpts", "peek_strategic_map", "update_whiteboard"],
                shutdown_event=shutdown_event
            )
            
            # Cognitive Audit
            if brain_full and not getattr(self, "is_extraction", False):
                if not self.auditor and "pinky" in self.residents:
                    self.auditor = CognitiveAudit(self.residents["pinky"])
                if self.auditor and not await self.auditor.audit_technical_truth(query, brain_full, ""):
                    retract_res = await self.residents["pinky"].call_tool("native_sample", {"query": "[AUDIT_FAILURE]", "context": brain_full[:100]})
                    retract_full = str(retract_res.content[0].text)
                    await self.execute_dispatch(retract_full, "Pinky (Retraction)", final=True)
                    return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

            if brain_full:
                await self.evaluate_grounding("Brain", brain_full, self.current_fuel, shutdown_event)

        return True

    async def evaluate_grounding(self, source, text, fuel, shutdown_event):
        """[FEAT-247] Physical Audit Gate: Pinky audits Brain for feasibility."""
        if "pinky" not in self.residents or fuel < 0.7:
            return
        
        # Refined Grounding Query
        cooldown_query = (
            f"The {source} has proposed a strategy. Audit this for physical feasibility "
            "(VRAM/Time/Complexity) and provide a 1-sentence 'Reality Check' "
            "from the perspective of the Lab's hardware constraints."
        )
        
        try:
            # [BKM-015.1] Natural persona audit
            res_res = await self.residents["pinky"].call_tool("native_sample", {
                "query": cooldown_query, 
                "context": f"[PROPOSED_STRATEGY]: {text[:1000]}"
            })
            res_full = str(res_res.content[0].text)
            await self.execute_dispatch(res_full, "Pinky (Physical Audit)", is_internal=True, final=True)
        except Exception:
            pass
