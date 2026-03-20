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
        clean_text = text.replace("<|eot_id|>", "").replace("<|begin_of_text|>", "").strip()
        
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
        if json_raw_match:
            raw_block = json_raw_match.group(1)
            sanitized = self.bridge_signal_clean(raw_block)
            
            # Remove the JSON immediately from the text to prevent leakage
            clean_text = clean_text.replace(raw_block, "").strip()
            clean_text = re.sub(r"```json\s*|\s*```", "", clean_text).strip()

            if sanitized:
                try:
                    data = json.loads(sanitized)
                    tool = data.get("tool")
                    params = data.get("parameters", {})

                    # Handle Known Tools
                    if tool == "ask_brain":
                        self.current_fuel = 1.0
                        if not clean_text:
                            clean_text = "Narf! I'll ask the Brain for you."

                    if tool == "shallow_think":
                        # If Pinky or Shadow calls shallow_think on themselves, it's a VETO
                        self.current_fuel = 0.0
                        if not clean_text:
                            clean_text = params.get("task") or params.get("context") or "Narf! Thinking fast."

                    if tool == "reply_to_user":
                        reply = params.get("text") or params.get("reply")
                        if reply and not clean_text:
                            clean_text = reply

                    if tool == "close_lab":
                        await self.broadcast({"brain": "Acme Lab is closing.", "brain_source": "System", "final": True})
                        if shutdown_event:
                            shutdown_event.set()
                        return True

                    # [FEAT-237] Loop-Breaker
                    primary_entry_points = ["facilitate", "shallow_think", "deep_think", "triage_situational_vibe"]
                    if tool in primary_entry_points:
                        # Return speech only, block recursive tool call
                        if clean_text:
                            return await self._dispatch_plain_text(clean_text, source, is_internal, final=final)
                        return True

                    # Forward utility tools
                    known_hub_tools = ["bounce_node", "scribble_note", "trigger_morning_briefing", "build_cv_summary", "access_personal_history", "select_file", "notify_file_open"]
                    if tool in known_hub_tools:
                        if tool in ["build_cv_summary", "access_personal_history"] and "archive" in self.residents:
                            res = await self.residents["archive"].call_tool(tool, params)
                            return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event, final=True)

                except Exception as e:
                    logging.error(f"[HUB] JSON parsing failed: {e}")

        # 4. Final Dispatch
        if clean_text:
            await self._dispatch_plain_text(clean_text, source, is_internal, final=final)
        
        return True

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

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0, turn_density=1.0):
        if retry_count > 2:
            return await self.execute_dispatch("Max retries reached.", "System", shutdown_event=shutdown_event)

        logging.info(f"[USER] Intercom Query: {query}")
        self.current_fuel = 0.0
        self.current_topic = "Casual"

        # 1. Situational Triage (Lab Node [FEAT-184/154/233])
        triage_data = {"intent": "STRATEGIC", "domain": "standard", "topic": "Casual", "casual": 0.5, "intrigue": 0.5, "importance": 0.5}
        if "lab" in self.residents:
            try:
                t_res = await self.residents["lab"].call_tool("triage_situational_vibe", {"query": query, "turn_density": turn_density})
                t_clean = self.bridge_signal_clean(t_res.content[0].text)
                if t_clean:
                    t_parsed = json.loads(t_clean)
                    triage_data.update({k.lower(): v for k, v in t_parsed.items()})
                
                # Multiplicative Fuel Function [FEAT-231.2]
                raw_imp = float(triage_data.get("importance", 0.5))
                raw_cas = float(triage_data.get("casual", 0.5))
                raw_int = float(triage_data.get("intrigue", 0.5))
                self.current_fuel = ((1.0 - raw_cas) * (raw_int + raw_imp)) / 2.0
                self.current_topic = triage_data.get("topic", "Casual")
            except Exception as e:
                logging.error(f"[HUB] Triage Failed: {e}")
                self.current_fuel = 0.2

        fuel_start = self.current_fuel

        # [FEAT-231.1] Operational Shortcut
        if triage_data.get("intent") == "OPERATIONAL":
            if "pinky" in self.residents:
                res = await self.residents["pinky"].call_tool("facilitate", {"query": f"[SYSTEM_DIRECTIVE]: {query}", "context": "OPERATIONAL_SHORTCUT"})
                return await self.execute_dispatch(res.content[0].text, "System", final=True)

        if triage_data.get("intent") != "CASUAL":
            selected_expert = await self._route_expert_domain(query)
        else:
            selected_expert = triage_data.get("domain", "standard")

        # 3. Proactive Archivist (Year detection [FEAT-228])
        historical_context = ""
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            try:
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year_match.group(1)}"})
                historical_context = str(res_context.content[0].text)
            except Exception:
                pass

        # 4. Parallel Local Inference
        pinky_text = ""
        shadow_text = ""
        
        async def process_pinky():
            nonlocal pinky_text
            if "pinky" in self.residents:
                p_context = (f"[ROUTE]: PINKY -> BRAIN\n[FUEL]: {fuel_start:.2f} | [TOPIC]: {self.current_topic}\n"
                             f"[MODE]: " + ("FRAME_ONLY" if fuel_start > 0.6 else "DIRECT_RESPONSE"))
                p_res = await self.residents["pinky"].call_tool("facilitate", {"query": query, "context": p_context})
                pinky_text = p_res.content[0].text
                await self.execute_dispatch(pinky_text, "Pinky (Triage)", shutdown_event=shutdown_event, final=True)

        async def process_shadow():
            nonlocal shadow_text
            if "shadow" in self.residents:
                s_context = (f"[FUEL]: {fuel_start:.2f} | [ROLE]: TECHNICAL_INTUITION")
                s_res = await self.residents["shadow"].call_tool("shallow_think", {"task": query, "context": s_context})
                shadow_text = s_res.content[0].text
                if self.current_fuel > 0.2:
                    await self.execute_dispatch(shadow_text, "Brain (Intuition)", shutdown_event=shutdown_event, final=True)

        await asyncio.gather(process_pinky(), process_shadow())

        # 5. Sovereign Brain (Post-Action Check)
        if self.brain_online and "brain" in self.residents and self.current_fuel > 0.6:
            metadata = {
                "expert_adapter": selected_expert, 
                "pinky_hearing": pinky_text, 
                "shadow_intuition": shadow_text, 
                "archival_truth": historical_context,
                "fuel": self.current_fuel,
                "topic": self.current_topic
            }
            b_res = await self.residents["brain"].call_tool("deep_think", {"task": query, "metadata": metadata})
            brain_text = b_res.content[0].text
            
            # Cognitive Audit [FEAT-190]
            if not self.auditor and "pinky" in self.residents:
                self.auditor = CognitiveAudit(self.residents["pinky"])
            if self.auditor and not await self.auditor.audit_technical_truth(query, brain_text, ""):
                # RETRY LOOP ON AUDIT FAILURE
                retract = await self.residents["pinky"].call_tool("facilitate", {"query": "[AUDIT_FAILURE]", "context": brain_text[:100]})
                await self.execute_dispatch(retract.content[0].text, "Pinky (Retraction)", final=True)
                return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

            await self.execute_dispatch(brain_text, "Brain (Result)", shutdown_event=shutdown_event, final=True)
            await self.evaluate_grounding("Brain", brain_text, self.current_fuel, shutdown_event)

        return True

    async def evaluate_grounding(self, source, text, fuel, shutdown_event):
        """[FEAT-227] The Grounding Gate (Cooldown)."""
        if "pinky" not in self.residents or fuel < 0.7:
            return
        cooldown_query = f"The {source} hemisphere provided deep technical synthesis. Provide a persona TL;DR."
        try:
            res_cool = await self.residents["pinky"].call_tool("facilitate", {"query": cooldown_query, "context": text[:500]})
            await self.execute_dispatch(res_cool.content[0].text, "Pinky (Summary)", is_internal=True)
        except Exception:
            pass
