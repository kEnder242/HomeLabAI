import asyncio
import json
import logging
import re
import os
from infra.cognitive_audit import CognitiveAudit

class CognitiveHub:
    """
    [FEAT-145] Cognitive Hub: Modularized Reasoning & Dispatch Logic.
    [FEAT-203] Bicameral Bridge: Hardened neural signal extraction and parallel gate protection.
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
        
        # [FEAT-188] Resonant Memory: Buffer for Pinky's intuition
        self.resonant_history = []
        self.auditor = None

    def bridge_signal_clean(self, text):
        """
        [FEAT-203] Bicameral Bridge Signal Cleaning Utility.
        Robustly extracts and sanitizes JSON from 3B model outputs.
        """
        if "{" not in text:
            return None

        # 1. Strip markdown blocks
        clean = re.sub(r"```json\s*|\s*```", "", text)

        # 2. Find innermost { } block to handle double braces and conversational chatter
        match = re.search(r'(\{.*\})', clean, re.DOTALL)
        if match:
            json_str = match.group(1)
        else:
            # Salvage truncated JSON
            if "{" in clean:
                json_str = clean[clean.find("{"):] + '\n  "error": "truncated"\n}'
            else:
                return None

        # 3. Structural Sanitization
        json_str = json_str.replace("{{", "{").replace("}}", "}")
        json_str = json_str.replace("'", '"')
        json_str = json_str.replace("True", "true").replace("False", "false")

        # 4. Domain Multi-Pick Correction: "domain": "a", "b", ... -> "domain": "a"
        json_str = re.sub(r'("domain":\s*"[^"]+")((?:,\s*"[^"]+")+)(?=\s*,|\s*\})', r'\1', json_str)
        # Clean up trailing commas
        json_str = re.sub(r',\s*\}', r'\n}', json_str)

        return json_str

    async def execute_dispatch(self, text, source, shutdown_event=None, is_internal=False, original_query=None, retry_count=0, sources=None, final=True):
        """
        Standardizes the dispatch of reasoning results to the user.
        [FEAT-203] Uses Bicameral Bridge signal cleaning.
        [FEAT-229] Support 'final' flag for speculative yielding.
        """
        logging.info(f"[DEBUG] Dispatch: source='{source}' final={final} text='{text[:30]}...'")
        
        # 1. Clean the text (Remove potential LoRA or node artifacts)
        clean_text = text.replace("<|eot_id|>", "").replace("<|begin_of_text|>", "").strip()
        
        # [FEAT-110] Shadow Moat: Persona Isolation
        if "Brain" in source:
            pinky_isms = ["narf", "poit", "zort", "egad", "trotro"]
            for ism in pinky_isms:
                clean_text = re.sub(rf'\b{ism}\b', '', clean_text, flags=re.IGNORECASE).strip()
            clean_text = clean_text.replace("  ", " ").replace(" .", ".").replace(" ,", ",")

        # 2. Extract Tool Calls (Nuclear Gate)
        json_block = self.bridge_signal_clean(clean_text)

        if json_block:
            try:
                # Validation gate: must contain "tool" or a known Hub key
                if '"tool"' not in json_block and '"reply_to_user"' not in json_block and '"facilitate"' not in json_block and '"name"' not in json_block:
                    pass # Not a tool call
                else:
                    data = json.loads(json_block)
                    tool = data.get("tool")
                    params = data.get("parameters", {})
                    
                    if not tool:
                        if "reply_to_user" in data:
                            tool = "reply_to_user"
                            params = {"text": data["reply_to_user"]}
                        else:
                            return await self._dispatch_plain_text(clean_text, source, is_internal, final=final)

                    if tool == "close_lab":
                        logging.warning(f"[HUB] SHUTDOWN requested by {source}.")
                        await self.broadcast({
                            "brain": "Acme Lab is closing. Goodnight.",
                            "brain_source": "System",
                            "channel": "chat",
                            "final": True,
                            "reset_session": True
                        })
                        if shutdown_event:
                            shutdown_event.set()
                        return True

                    # [RE-FEAT-145] Ghost Tool Sentry
                    available_tools = []
                    t_name = source.split("(")[0].strip().lower()
                    if t_name in self.residents:
                        try:
                            tool_resp = await self.residents[t_name].list_tools()
                            available_tools = [t.name for t in tool_resp.tools]
                        except Exception:
                            available_tools = []

                    known_hub_tools = ["reply_to_user", "ask_brain", "bounce_node", "scribble_note", "trigger_morning_briefing", "build_cv_summary", "access_personal_history", "select_file", "notify_file_open"]
                    
                    if tool not in available_tools and tool not in known_hub_tools:
                        logging.warning(f"[HUB] Hallucination Detected: {source} tried to use '{tool}'. Applying Neural Shock.")
                        if original_query and retry_count < 2:
                            shock_query = f"[SYSTEM_SHOCK]: You attempted to use tool '{tool}' which is INVALID. Use only provided tools. Re-think your approach.\n\nOriginal Query: {original_query}"
                            return await self.process_query(shock_query, shutdown_event=shutdown_event, retry_count=retry_count + 1)
                        
                        hallucination_msg = f"Egad! I tried to use '{tool}', but my circuits don't support it yet. Narf!"
                        return await self.execute_dispatch(hallucination_msg, "Pinky (System)", shutdown_event=shutdown_event, final=True)

                    if tool in ["build_cv_summary", "access_personal_history"]:
                        if "archive" in self.residents:
                            res = await self.residents["archive"].call_tool(tool, params)
                            return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event, final=True)
                        else:
                            return await self.execute_dispatch("Archive Node is offline.", "Pinky (System)", shutdown_event=shutdown_event, final=True)

                    if tool == "bounce_node":
                        reason = params.get("reason", "No reason provided.")
                        await self.broadcast({
                            "brain": f"Hemisphere reset initiated: {reason}",
                            "brain_source": "System",
                            "channel": "chat",
                            "final": True
                        })
                        if t_name in self.residents:
                            try:
                                res = await self.residents[t_name].call_tool("ping_engine", {"force": True})
                                r_data = json.loads(res.content[0].text)
                                msg = f"Reset complete. Success: {r_data.get('success')}. Detail: {r_data.get('message')}"
                                return await self.execute_dispatch(msg, f"{t_name.upper()} (System)", shutdown_event=shutdown_event, final=True)
                            except Exception as e:
                                return await self.execute_dispatch(f"Reset failed: {e}", f"{t_name.upper()} (System)", shutdown_event=shutdown_event, final=True)
                        return True

                    if tool == "trigger_morning_briefing":
                        if hasattr(self, '_trigger_briefing'):
                            await self._trigger_briefing()
                            return True
                        return await self.execute_dispatch("Briefing logic unreachable.", "Pinky (System)", shutdown_event=shutdown_event, final=True)

                    if tool == "select_file":
                        fname = params.get("filename")
                        await self.broadcast({"type": "file_content_request", "filename": fname})
                        return True

                    if tool == "notify_file_open":
                        return True

                    if tool == "ask_brain":
                        task = params.get("task", "")
                        await self.broadcast({
                            "brain": self.get_oracle_signal("Brain"),
                            "brain_source": "The Brain (Synthesizing...)",
                            "channel": "insight",
                            "final": False
                        })
                        if "brain" in self.residents:
                            metadata = {"expert_adapter": "exp_for"}
                            b_res = await self.monitor_task_with_tics(
                                self.residents["brain"].call_tool("deep_think", {"task": task, "metadata": metadata})
                            )
                            return await self.execute_dispatch(b_res.content[0].text, "Brain (Result)", shutdown_event=shutdown_event, final=True)
                        else:
                            return await self.execute_dispatch("Strategic Sovereign is offline.", "Pinky (System)", shutdown_event=shutdown_event, final=True)

                    if tool == "reply_to_user":
                        reply = params.get("text", "Egad! Empty reply.")
                        await self.broadcast({
                            "brain": reply,
                            "brain_source": source,
                            "channel": "chat",
                            "final": True
                        })
                        return True

                    logging.info(f"[HUB] Forwarding tool {tool} back to {source}")
                    await self.broadcast({
                        "brain": clean_text,
                        "brain_source": source.replace("Result", "").strip(),
                        "channel": "insight",
                        "final": True
                    })
                    return True

            except json.JSONDecodeError as e:
                logging.error(f"[HUB] Bridge Signal Extraction Failed: {e} | Raw: {clean_text[:50]}")
                return await self._dispatch_plain_text(clean_text, source, is_internal, final=final)
            except Exception as e:
                logging.error(f"[HUB] Tool Dispatch Error: {e}")
                return await self.execute_dispatch(f"Error executing tool: {e}", "Pinky (System)", shutdown_event=shutdown_event, final=True)

        return await self._dispatch_plain_text(clean_text, source, is_internal, final=final)

    async def _dispatch_plain_text(self, text, source, is_internal, final=True):
        await self.broadcast({
            "brain": text,
            "brain_source": source,
            "channel": "chat",
            "is_internal": is_internal,
            "final": final,
            "topic": getattr(self, "current_topic", "Casual"),
            "fuel": getattr(self, "current_fuel", 0.0)
        })
        return text

    async def _route_expert_domain(self, query, interjection=""):
        try:
            if 'archive' not in self.residents:
                return "exp_for"
            vibe_res = await self.residents['archive'].call_tool("query_vibe", {"query_text": query})
            vibe_json = vibe_res.content[0].text if hasattr(vibe_res, 'content') else str(vibe_res)
            vibe_data = json.loads(vibe_json)
            adapter = vibe_data.get("adapter", "exp_for")
            self.current_vibe_guidance = vibe_data.get("guidance", "")
            return adapter
        except Exception as e:
            logging.error(f"[HUB] Vibe Check Failed: {e}")
            return "exp_for"

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0, turn_density=1.0):
        if retry_count > 2:
            logging.warning("[HUB] Max retries reached. Surrendering to base model.")
            return await self.execute_dispatch("Egad! Even the experts are stumped. Proceeding with caution.", "Pinky (System)", shutdown_event=shutdown_event)

        if trigger_briefing_callback:
            self._trigger_briefing = trigger_briefing_callback

        logging.info(f"[USER] Intercom Query: {query} (Retry: {retry_count}, Density: {turn_density:.2f})")
        
        # 1. Situational Triage (Lab Node [FEAT-184/154/233])
        triage_data = {"intent": "STRATEGIC", "domain": "standard", "topic": "Casual", "casual": 0.5, "intrigue": 0.5, "importance": 0.5}
        
        if "lab" in self.residents:
            try:
                # [FEAT-233] Incremental Triage Streaming
                t_stream = await self.residents["lab"].call_tool("triage_situational_vibe", {"query": query, "turn_density": turn_density}, stream=True)
                full_t_json = ""
                async for token in t_stream:
                    full_t_json += token
                    # Incremental parse: the moment we have 'intent', we can proceed
                    if '"intent":' in full_t_json:
                        m = re.search(r'"intent":\s*"([^"]+)"', full_t_json)
                        if m:
                            triage_data["intent"] = m.group(1).upper()
                            logging.info(f"[HUB] Incremental Intent Identified: {triage_data['intent']}")
                            break
                
                # Consume remaining triage tokens
                async for token in t_stream:
                    full_t_json += token
                
                t_clean = self.bridge_signal_clean(full_t_json)
                if t_clean:
                    t_parsed = json.loads(t_clean)
                    triage_data.update({k.lower(): v for k, v in t_parsed.items()})
                
                # [FEAT-231.2] Multiplicative Fuel Function
                raw_importance = float(triage_data.get("importance", 0.5))
                raw_casual = float(triage_data.get("casual", 0.5))
                raw_intrigue = float(triage_data.get("intrigue", 0.5))
                self.current_fuel = ((1.0 - raw_casual) * (raw_intrigue + raw_importance)) / 2.0
                self.current_topic = triage_data.get("topic", "Casual")

                logging.info(f"[HUB] Scalar Triage: Intent={triage_data.get('intent')} Topic={self.current_topic} Fuel={self.current_fuel:.2f}")
            except Exception as e:
                logging.error(f"[HUB] Lab Node Triage Failed: {e}. Falling back.")
                self.current_topic = "Casual"
                self.current_fuel = 0.2
                if len(query.split()) < 4 or any(k in query.lower() for k in ["hello", "hi", "hey", "narf", "poit"]):
                    triage_data["intent"] = "CASUAL"
        
        fuel = self.current_fuel
        
        # [FEAT-231.1] Operational Shortcut
        if triage_data.get("intent") == "OPERATIONAL":
            logging.info("[HUB] Operational Shortcut triggered.")
            if "pinky" in self.residents:
                res = await self.residents["pinky"].call_tool("facilitate", {"query": f"[SYSTEM_DIRECTIVE]: {query}"})
                return await self.execute_dispatch(res.content[0].text, "System", shutdown_event=shutdown_event, final=True)

        if triage_data.get("intent") != "CASUAL":
            selected_expert = await self._route_expert_domain(query)
        else:
            selected_expert = triage_data.get("domain", "standard")

        # 3. Proactive Archivist (RAG context)
        historical_context = ""
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            try:
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year_match.group(1)}"})
                historical_context = str(res_context.content[0].text)
            except Exception:
                pass

        pinky_text = ""
        shadow_text = ""
        
        # [FEAT-233] The Waterfall Handshake: Token-based relay
        # [Task 8.2] The pinky_pipe: Live token transfer between nodes
        pinky_pipe = asyncio.Queue()

        async def process_pinky():
            nonlocal pinky_text
            if "pinky" in self.residents:
                p_stream = await self.residents["pinky"].call_tool("facilitate", {"query": query}, stream=True)
                async for token in p_stream:
                    pinky_text += token
                    # Pipe to the shared queue for Shadow
                    await pinky_pipe.put(token)
                    # [Task 8.3] Real-time Streaming to UI
                    await self.broadcast({"brain": token, "brain_source": "Pinky", "final": False, "topic": self.current_topic, "fuel": fuel})
                
                # Signal end of pipe
                await pinky_pipe.put(None)
                
                # Final Promotion (adds to persistent history)
                await self.execute_dispatch(pinky_text, "Pinky (Triage)", shutdown_event=shutdown_event, is_internal=False, final=True)

        async def process_shadow():
            nonlocal shadow_text
            if "shadow" in self.residents:
                # [FEAT-233.2] Shadow consumes the pinky_pipe live
                s_stream = await self.residents["shadow"].call_tool("shallow_think", {
                    "task": query, 
                    "context_queue": pinky_pipe,
                    "context": f"Triage: {triage_data.get('intent')}"
                }, stream=True)
                
                async for token in s_stream:
                    shadow_text += token
                    if fuel > 0.2:
                        await self.broadcast({"brain": token, "brain_source": "Shadow", "final": False, "topic": self.current_topic, "fuel": fuel})
                
                # Final Promotion
                if fuel > 0.2:
                    await self.execute_dispatch(shadow_text, "Brain (Intuition)", shutdown_event=shutdown_event, is_internal=False, final=True)

        await asyncio.gather(process_pinky(), process_shadow())

        # [FEAT-207] Stage 3: Sovereign Brain
        if self.brain_online and "brain" in self.residents and fuel > 0.6:
            metadata = {
                "expert_adapter": selected_expert, 
                "pinky_hearing": pinky_text, 
                "shadow_intuition": shadow_text, 
                "archival_truth": historical_context,
                "fuel": fuel,
                "topic": self.current_topic,
                "verbosity_directive": "Provide full-spectrum exhaustive synthesis." if fuel > 0.8 else "Provide moderate technical depth."
            }
            
            # [FEAT-190] The Judge: Cognitive Audit of Sovereign Output
            # Note: We stream brain result for UI feedback but audit the final text
            b_stream = await self.residents["brain"].call_tool("deep_think", {"task": query, "metadata": metadata}, stream=True)
            brain_text = ""
            async for token in b_stream:
                brain_text += token
                # [Task 8.3] Real-time Streaming to UI (Eliminates Paragraph Pop)
                await self.broadcast({"brain": token, "brain_source": "Brain", "final": False, "topic": self.current_topic, "fuel": fuel})
            
            # Perform Audit on final text
            if not getattr(self, "is_extraction", False):
                if not self.auditor and "pinky" in self.residents:
                    self.auditor = CognitiveAudit(self.residents["pinky"])
                
                if self.auditor:
                    is_valid = await self.auditor.audit_technical_truth(query, brain_text, "")
                    if not is_valid:
                        # [FEAT-231.3] Verbal Retraction
                        if "pinky" in self.residents:
                            retract_res = await self.residents["pinky"].call_tool("facilitate", {
                                "query": "[AUDIT_FAILURE]: The Sovereign output failed technical validation.",
                                "context": f"Failure: {brain_text[:200]}..."
                            })
                            await self.execute_dispatch(retract_res.content[0].text, "Pinky (Retraction)", shutdown_event=shutdown_event, is_internal=False, final=True)
                        return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

            await self.execute_dispatch(brain_text, "Brain (Result)", shutdown_event=shutdown_event, final=True)
            await self.evaluate_grounding("Brain", brain_text, fuel, shutdown_event)

        return True

    async def evaluate_grounding(self, source, text, fuel, shutdown_event):
        """
        [FEAT-227] The Grounding Gate (Cooldown).
        Restores character balance after verbose or high-stakes technical synthesis.
        """
        if "pinky" not in self.residents:
            return

        # Importance calculation using scalar Fuel and length
        importance = fuel
        if len(text) > 800:
            importance = min(1.0, importance + 0.2)
        
        if importance > 0.7:
            logging.info(f"[HUB] Grounding Gate triggered for {source} (Importance: {importance:.2f}).")
            
            cooldown_query = (
                f"The {source} hemisphere just provided a deep technical response. "
                "1. Provide a 1-sentence persona-driven summary (TL;DR). "
                "2. Probabilistically add a 'Pondering' challenge (Are you pondering what I'm pondering?) if you see a technical edge case."
            )
            
            try:
                # Cooldown turns are terminal and do not re-trigger the relay
                res_cool = await self.residents["pinky"].call_tool("facilitate", {
                    "query": cooldown_query, 
                    "context": f"Technical Output: {text}"
                })
                cool_text = res_cool.content[0].text
                
                # Robust JSON extraction
                m = re.search(r'(\{.*\})', cool_text, re.DOTALL)
                if m:
                    try:
                        dec = json.loads(m.group(1))
                        cool_text = dec.get("parameters", {}).get("text", cool_text)
                    except Exception:
                        pass
                
                # Dispatch as terminal summary
                await self.execute_dispatch(cool_text, "Pinky (Summary)", shutdown_event=shutdown_event, is_internal=True)
            except Exception as e:
                logging.error(f"[HUB] Grounding Gate failed: {e}")
