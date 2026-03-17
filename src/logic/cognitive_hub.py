import asyncio
import json
import logging
import re
import os
import sys

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

    async def execute_dispatch(self, text, source, shutdown_event=None, is_internal=False, original_query=None, retry_count=0, sources=None):
        """
        Standardizes the dispatch of reasoning results to the user.
        [FEAT-203] Uses Bicameral Bridge signal cleaning.
        """
        logging.info(f"[DEBUG] Dispatch: source='{source}' text='{text[:30]}...'")
        
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
                            return await self._dispatch_plain_text(clean_text, source, is_internal)

                    if tool == "close_lab":
                        logging.warning(f"[HUB] SHUTDOWN requested by {source}.")
                        await self.broadcast({
                            "brain": "Acme Lab is closing. Goodnight.",
                            "brain_source": "System",
                            "channel": "chat"
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
                        return await self.execute_dispatch(hallucination_msg, "Pinky (System)", shutdown_event=shutdown_event)

                    if tool in ["build_cv_summary", "access_personal_history"]:
                        if "archive" in self.residents:
                            res = await self.residents["archive"].call_tool(tool, params)
                            return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event)
                        else:
                            return await self.execute_dispatch("Archive Node is offline.", "Pinky (System)", shutdown_event=shutdown_event)

                    if tool == "bounce_node":
                        reason = params.get("reason", "No reason provided.")
                        await self.broadcast({
                            "brain": f"Hemisphere reset initiated: {reason}",
                            "brain_source": "System",
                            "channel": "chat"
                        })
                        if t_name in self.residents:
                            try:
                                res = await self.residents[t_name].call_tool("ping_engine", {"force": True})
                                r_data = json.loads(res.content[0].text)
                                msg = f"Reset complete. Success: {r_data.get('success')}. Detail: {r_data.get('message')}"
                                return await self.execute_dispatch(msg, f"{t_name.upper()} (System)", shutdown_event=shutdown_event)
                            except Exception as e:
                                return await self.execute_dispatch(f"Reset failed: {e}", f"{t_name.upper()} (System)", shutdown_event=shutdown_event)
                        return True

                    if tool == "trigger_morning_briefing":
                        if hasattr(self, '_trigger_briefing'):
                            await self._trigger_briefing()
                            return True
                        return await self.execute_dispatch("Briefing logic unreachable.", "Pinky (System)", shutdown_event=shutdown_event)

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
                            "channel": "insight"
                        })
                        if "brain" in self.residents:
                            metadata = {"expert_adapter": "exp_for"}
                            b_res = await self.monitor_task_with_tics(
                                self.residents["brain"].call_tool("deep_think", {"task": task, "metadata": metadata})
                            )
                            return await self.execute_dispatch(b_res.content[0].text, "Brain (Result)", shutdown_event=shutdown_event)
                        else:
                            return await self.execute_dispatch("Strategic Sovereign is offline.", "Pinky (System)", shutdown_event=shutdown_event)

                    if tool == "reply_to_user":
                        reply = params.get("text", "Egad! Empty reply.")
                        await self.broadcast({
                            "brain": reply,
                            "brain_source": source,
                            "channel": "chat"
                        })
                        return True

                    logging.info(f"[HUB] Forwarding tool {tool} back to {source}")
                    await self.broadcast({
                        "brain": clean_text,
                        "brain_source": source.replace("Result", "").strip(),
                        "channel": "insight"
                    })
                    return True

            except json.JSONDecodeError as e:
                logging.error(f"[HUB] Bridge Signal Extraction Failed: {e} | Raw: {clean_text[:50]}")
                return await self._dispatch_plain_text(clean_text, source, is_internal)
            except Exception as e:
                logging.error(f"[HUB] Tool Dispatch Error: {e}")
                return await self.execute_dispatch(f"Error executing tool: {e}", "Pinky (System)", shutdown_event=shutdown_event)

        return await self._dispatch_plain_text(clean_text, source, is_internal)

    async def _dispatch_plain_text(self, text, source, is_internal):
        await self.broadcast({
            "brain": text,
            "brain_source": source,
            "channel": "chat",
            "is_internal": is_internal
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
        
        # 1. Situational Triage (Lab Node [FEAT-184/154])
        triage_data = {"intent": "STRATEGIC", "domain": "standard", "situation": "[UNKNOWN]", "hints": ""}
        if "lab" in self.residents:
            try:
                t_res = await self.residents["lab"].call_tool("triage_situational_vibe", {"query": query, "turn_density": turn_density})
                t_json = t_res.content[0].text if hasattr(t_res, 'content') else str(t_res)
                # [FEAT-199] Hybrid Triage Parsing (Pipe or JSON)
                if "|" in t_json and "intent" not in t_json.lower():
                    parts = t_json.split("|")
                    if len(parts) >= 2:
                        triage_data["intent"] = parts[0].strip().upper()
                        triage_data["domain"] = parts[1].strip().lower()
                        if len(parts) >= 3:
                            triage_data["situation"] = parts[2].strip()
                        if len(parts) >= 4:
                            triage_data["hints"] = parts[3].strip()
                else:
                    t_clean = self.bridge_signal_clean(t_json)
                    if t_clean:
                        t_parsed = json.loads(t_clean)
                        triage_data.update({k.lower(): v for k, v in t_parsed.items()})
                logging.info(f"[HUB] Lab Node Triage: {triage_data.get('intent')} | Domain: {triage_data.get('domain')}")
            except Exception as e:
                logging.error(f"[HUB] Lab Node Triage Failed: {e}. Falling back.")
                if len(query.split()) < 4 or any(k in query.lower() for k in ["hello", "hi", "hey", "narf", "poit"]):
                    triage_data["intent"] = "CASUAL"
        
        is_casual = triage_data.get("intent") == "CASUAL"
        is_extraction = "[ARCHIVE_EXTRACT]" in query
        selected_expert = triage_data.get("domain", "standard")
        current_situation = triage_data.get("situation", "")
        vibe_hints = triage_data.get("hints", "")
        
        # 2. Predictive Warm-up & [FEAT-207] Airtime Check
        brain_is_remote = False
        if "brain" in self.residents:
            try:
                import socket
                infra_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config/infrastructure.json")
                if os.path.exists(infra_path):
                    with open(infra_path, "r") as f:
                        infra = json.load(f)
                    primary = infra.get("nodes", {}).get("brain", {}).get("primary", "localhost")
                    if primary != "localhost" and primary != "127.0.0.1":
                        ip_hint = infra.get("hosts", {}).get(primary, {}).get("ip_hint", "127.0.0.1")
                        try:
                            ip = socket.gethostbyname(primary)
                        except Exception:
                            ip = ip_hint
                        if ip != "127.0.0.1":
                            brain_is_remote = True
            except Exception as e:
                logging.debug(f"[HUB] Failed to resolve brain remote status: {e}")

        if not is_casual and self.brain_online:
            logging.info("[HUB] Strategic triage detected. Pre-warming Brain...")
            if "brain" in self.residents:
                # Trigger a non-blocking ping to wake up the 4090
                asyncio.create_task(self.residents["brain"].call_tool("ping_engine", {"force": True}))

        # 3. [FEAT-211] Proactive Archivist: Look for years/keywords
        historical_context = ""
        historical_sources = []
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            year = year_match.group(1)
            try:
                # Use sub-second local retrieval via Archive Node
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year}"})
                rag_data = json.loads(res_context.content[0].text) if "{" in res_context.content[0].text else {"text": res_context.content[0].text}
                historical_context = rag_data.get("text", res_context.content[0].text)
                historical_sources = rag_data.get("sources", [])
                logging.info(f"[HUB] [FEAT-211] Archivist retrieved context for {year}.")
            except Exception as e:
                logging.error(f"[HUB] Archivist failed: {e}")

        if not is_casual:
            selected_expert = await self._route_expert_domain(query)

        dispatch_tasks = []
        if is_casual and not is_extraction and not mic_active and retry_count == 0:
            if "pinky" in self.residents:
                t_pinky = asyncio.create_task(self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: {current_situation}] {vibe_hints}"}))
                dispatch_tasks.append((t_pinky, "Pinky"))
        else:
            pinky_intuition = ""
            shadow_intuition = ""
            
            # [FEAT-207] Tricameral Flow Stage 1: Pinky (Instant Triage)
            if "pinky" in self.residents and retry_count == 0:
                await self.broadcast({
                    "brain": self.get_oracle_signal("Pinky"),
                    "brain_source": "Pinky (Triage)",
                    "channel": "insight",
                    "is_internal": True
                })
                try:
                    res = await self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: {current_situation}] {vibe_hints}"})
                    pinky_intuition = res.content[0].text
                    # Broadcast Pinky as Triage/Intuition, NOT Result
                    await self.execute_dispatch(pinky_intuition, "Pinky (Triage)", shutdown_event=shutdown_event, is_internal=True)

                except Exception as e:
                    logging.error(f"[HUB] Pinky intuition failed: {e}")

            # [FEAT-207] Tricameral Flow Stage 2: Shadow Brain (Fast Intuition)
            if "brain" in self.residents and brain_is_remote and retry_count == 0:
                await self.broadcast({
                    "brain": "Initiating local technical intuition... Narf!",
                    "brain_source": "Shadow",
                    "channel": "insight",
                    "is_internal": True
                })
                try:
                    # Execute a shallow_think on the local 2080 Ti
                    s_res = await self.residents["brain"].call_tool("shallow_think", {
                        "task": query, 
                        "context": f"Triage: {pinky_intuition}\nTruth: {historical_context}"
                    })
                    shadow_intuition = s_res.content[0].text
                    # Broadcast Shadow as Intuition
                    await self.execute_dispatch(shadow_intuition, "Brain (Intuition)", shutdown_event=shutdown_event)
                except Exception as e:
                    logging.error(f"[HUB] Shadow intuition failed: {e}")

            # [FEAT-207] Tricameral Flow Stage 3: Sovereign Brain (Deep Synthesis)
            if self.brain_online and "brain" in self.residents:
                oracle_cat = "RETRIEVING" if historical_context else "HANDSHAKE"
                oracle_signal = self.get_oracle_signal(oracle_cat)
                await self.execute_dispatch(oracle_signal, "Brain (Signal)", shutdown_event=shutdown_event, is_internal=True)
                
                hearing_tag = f"\n\n[PINKY_HEARING]: {pinky_intuition}" if pinky_intuition else ""
                shadow_tag = f"\n\n[SHADOW_INTUITION]: {shadow_intuition}" if shadow_intuition else ""
                truth_tag = f"\n\n[ARCHIVAL_TRUTH]: {historical_context}" if historical_context else ""
                
                history_tag = ""
                if self.resonant_history:
                    history_content = "\n".join(self.resonant_history[-3:])
                    history_tag = f"\n\n[RESONANT_HISTORY]:\n{history_content}"
                
                if pinky_intuition:
                    self.resonant_history.append(f"- {pinky_intuition}")
                    if len(self.resonant_history) > 10:
                        self.resonant_history.pop(0)

                tool_allowlist = ["ask_brain", "reply_to_user"]
                archival_map_context = ""
                if selected_expert in ["exp_for", "exp_tlm"] or is_extraction:
                    tool_allowlist.extend(["list_cabinet", "read_document", "peek_strategic_map", "read_chronological_excerpts"])
                    if self.semantic_map:
                        strat = len(self.semantic_map.get("strategic_layer", []))
                        themes = list(self.semantic_map.get("analytical_layer", {}).keys())
                        archival_map_context = f"\n[ARCHIVAL_TOPOGRAPHY]: Archive contains {strat} Diamond anchors themes: {themes}."

                metadata = {
                    "expert_adapter": selected_expert,
                    "behavioral_guidance": getattr(self, "current_vibe_guidance", ""),
                    "pinky_hearing": pinky_intuition,
                    "shadow_intuition": shadow_intuition,
                    "archival_truth": historical_context,
                    "resonant_history": self.resonant_history[-3:],
                    "tool_allowlist": tool_allowlist,
                    "sources": historical_sources
                }
                
                # Execute Sovereignty turn with mandatory completion
                res_deep = await self.monitor_task_with_tics(
                    self.residents["brain"].call_tool("deep_think", {
                        "task": f"{query}{hearing_tag}{shadow_tag}{truth_tag}{history_tag}{archival_map_context}", 
                        "metadata": metadata
                    })
                )
                result_text = res_deep.content[0].text

                # [FEAT-077] Fidelity Gate: Audit Sovereign Output
                if not is_extraction:
                    base_threshold = 20
                    is_thin = len(result_text.split()) < base_threshold and len(query.split()) > 4
                    if "3.141" in result_text: # Technical constant bypass
                        is_thin = False

                    if is_thin:
                        if retry_count == 1:
                            # [FEAT-179] The Hallway Protocol (Agentic-R)
                            logging.warning(f"[FEAT-179] Pivot FAILED. Triggering Hallway Protocol for: {query}")
                            await self.broadcast({
                                "brain": "Expert pivot insufficient... performing deep archival harvest. Poit!",
                                "brain_source": "Pinky (Forensic)",
                                "channel": "insight",
                                "is_internal": True
                            })
                            try:
                                scan_script = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py")
                                proc = await asyncio.create_subprocess_exec(sys.executable, scan_script, "--keyword", query, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
                                await proc.communicate()
                            except Exception as e:
                                logging.error(f"[HALLWAY] Scan execution failed: {e}")
                            return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)
                        
                        logging.warning("[HUB] Fidelity Pivot triggered for Sovereign turn.")
                        return await self.process_query(query, mic_active, shutdown_event, retry_count=retry_count+1)

                await self.execute_dispatch(result_text, "Brain (Result)", sources=historical_sources, shutdown_event=shutdown_event)
            else:
                # [SOVEREIGN GATE] Forbidden to failover if this is a high-fidelity extraction
                if is_extraction:
                    await self.execute_dispatch("❌ Sovereign offline. Archive extraction forbidden in failover mode.", "Brain (Error)", shutdown_event=shutdown_event)
                    return True

                # Standard failover for casual/strategic
                if shadow_intuition:
                     await self.execute_dispatch(shadow_intuition, "Brain (Result)", sources=historical_sources, shutdown_event=shutdown_event)
                elif "pinky" in self.residents:
                     # Final fallback to Pinky
                     res = await self.residents["pinky"].call_tool("facilitate", {"query": f"[FAILOVER]: {query}", "context": ""})
                     await self.execute_dispatch(res.content[0].text, "Brain (Failover)", shutdown_event=shutdown_event)

        return True
