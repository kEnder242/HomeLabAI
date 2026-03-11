import asyncio
import json
import logging
import re
import random
import os
import sys
from infra.montana import reclaim_logger

class CognitiveHub:
    """
    [FEAT-145] Cognitive Hub: Modularized Reasoning & Dispatch Logic.
    Extracts the 'Thinking' logic from acme_lab.py to improve maintainability.
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
        
        # [FEAT-178] Semantic Integration
        self.semantic_map_path = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/semantic_map.json")
        self.semantic_map = {}
        if os.path.exists(self.semantic_map_path):
            with open(self.semantic_map_path, "r") as f:
                self.semantic_map = json.load(f)

    async def execute_dispatch(self, text, source, shutdown_event=None, is_internal=False):
        """
        Standardizes the dispatch of reasoning results to the user.
        Returns the clean text if it was a plain message, or True if it handled a tool.
        """
        logging.info(f"[DEBUG] Dispatch: source='{source}' text='{text[:30]}...'")
        
        # 1. Clean the text (Remove potential LoRA or node artifacts)
        clean_text = text.replace("<|eot_id|>", "").replace("<|begin_of_text|>", "").strip()

        # 2. Extract Tool Calls (JSON detection)
        matches = re.findall(r'(\{.*?\})', clean_text, re.DOTALL)
        if matches:
            try:
                params = json.loads(matches[0])
                tool = params.get("tool")
                
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

                # [RE-FEAT-145] Ghost Tool Sentry: Verify tool exists in resident schema
                available_tools = []
                t_name = source.split("(")[0].strip().lower()
                if t_name in self.residents:
                    try:
                        # [OPTIMIZATION] We use a cached tool list if possible to avoid MCP round-trip
                        tool_resp = await self.residents[t_name].list_tools()
                        available_tools = [t.name for t in tool_resp.tools]
                    except Exception:
                        available_tools = []

                # Hardcoded Hub Tools (Known Truths)
                known_hub_tools = ["reply_to_user", "ask_brain", "bounce_node", "scribble_note", "trigger_morning_briefing", "build_cv_summary", "access_personal_history"]
                
                if tool not in available_tools and tool not in known_hub_tools:
                    logging.warning(f"[HUB] Hallucination Detected: {source} tried to use '{tool}'. Shunting to Pinky.")
                    hallucination_msg = f"Egad! I tried to use '{tool}', but my circuits don't support it yet. Narf!"
                    return await self.execute_dispatch(hallucination_msg, "Pinky (System)", shutdown_event=shutdown_event)

                if tool == "build_cv_summary" or tool == "access_personal_history":
                    logging.info(f"[HUB] Cross-node tool call: {tool} requested by {source}")
                    if "archive" in self.residents:
                        res = await self.residents["archive"].call_tool(tool, params)
                        return await self.execute_dispatch(res.content[0].text, f"Archive ({tool})", shutdown_event=shutdown_event)
                    else:
                        return await self.execute_dispatch("Archive Node is offline.", "Pinky (System)", shutdown_event=shutdown_event)

                if tool == "bounce_node":
                    reason = params.get("reason", "No reason provided.")
                    logging.warning(f"[HUB] Bounce requested by {source}: {reason}")
                    await self.broadcast({
                        "brain": f"Hemisphere reset initiated: {reason}",
                        "brain_source": "System",
                        "channel": "chat"
                    })
                    
                    # [RE-FEAT-045] Re-prime the node's engine
                    target_node = None
                    # If source is "Brain (Shadow)" or "Brain (Result)", target "brain"
                    t_name = source.split("(")[0].strip().lower()
                    if t_name in self.residents:
                        target_node = self.residents[t_name]
                    
                    if target_node:
                        try:
                            res = await target_node.call_tool("ping_engine", {"force": True})
                            data = json.loads(res.content[0].text)
                            msg = f"Reset complete. Success: {data.get('success')}. Detail: {data.get('message')}"
                            return await self.execute_dispatch(msg, f"{t_name.upper()} (System)", shutdown_event=shutdown_event)
                        except Exception as e:
                            logging.error(f"[HUB] Bounce failed: {e}")
                            return await self.execute_dispatch(f"Reset failed: {e}", f"{t_name.upper()} (System)", shutdown_event=shutdown_event)
                    
                    return await self.execute_dispatch(f"Reset complete for {source}.", f"{source} (System)", shutdown_event=shutdown_event)

                if tool == "trigger_morning_briefing":
                    logging.info(f"[HUB] Morning Briefing requested by {source}.")
                    # This is handled via the callback passed to process_query
                    if hasattr(self, '_trigger_briefing'):
                        await self._trigger_briefing()
                        return True
                    else:
                        return await self.execute_dispatch("Briefing logic unreachable.", "Pinky (System)", shutdown_event=shutdown_event)

                if tool == "select_file":
                    fname = params.get("filename")
                    await self.broadcast({"type": "file_content_request", "filename": fname})
                    return True

                if tool == "notify_file_open":
                    logging.info(f"[WORKBENCH] User is viewing: {params.get('filename')}")
                    return True

                if tool == "ask_brain":
                    task = params.get("task", "")
                    logging.info(f"[HUB] Pinky delegating to Brain: {task}")
                    await self.broadcast({
                        "brain": self.get_oracle_signal("Brain"),
                        "brain_source": "The Brain (Synthesizing...)",
                        "channel": "insight"
                    })
                    
                    if "brain" in self.residents:
                        # [FEAT-174.1] Strategic Pre-Gating
                        metadata = {"expert_adapter": "exp_for"} # Forensic Architect default
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
                        "brain_source": source.replace("Result", "").strip(),
                        "channel": "chat"
                    })
                    return True
                
                # If it's a tool we don't handle at Hub level, dispatch to the resident who called it
                logging.info(f"[HUB] Forwarding tool {tool} back to {source}")
                await self.broadcast({
                    "brain": clean_text,
                    "brain_source": source.replace("Result", "").strip(),
                    "channel": "insight"
                })
                return True

            except Exception as e:
                logging.error(f"[HUB] Tool Dispatch Error: {e}")
                return await self.execute_dispatch(f"Error executing tool: {e}", "Pinky (System)", shutdown_event=shutdown_event)

        if "{" not in clean_text:
            await self.broadcast({
                "brain": clean_text,
                "brain_source": source.replace("Result", "").strip(),
                "channel": "chat",
                "is_internal": is_internal
            })
            return clean_text

    def _route_expert_domain(self, query, interjection=""):
        """[FEAT-174.1] Strategic Routing: Identifies the expert adapter needed using JSON anchors."""
        q_low = query.lower()
        i_low = interjection.lower()
        
        # [BKM-015] Use loaded anchors for dynamic routing
        for domain, cfg in self.intent_anchors.items():
            adapter = cfg.get("adapter")
            anchors = cfg.get("anchors", [])
            for anchor in anchors:
                if anchor in q_low or anchor in i_low:
                    return adapter
        
        return "exp_for" # Default Forensic/Architect

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0, turn_density=1.0):
        """The Central Reasoning Pipeline with [GHOST-01] Parallel Turn Bundler."""
        if retry_count > 2:
            logging.warning("[HUB] Max retries reached. Surrendering to base model.")
            return await self.execute_dispatch("Egad! Even the experts are stumped. Proceeding with caution.", "Pinky (System)", shutdown_event=shutdown_event)

        # [FEAT-190] Inject callbacks for tool-based logic
        if trigger_briefing_callback:
            self._trigger_briefing = trigger_briefing_callback

        logging.info(f"[USER] Intercom Query: {query} (Retry: {retry_count}, Density: {turn_density:.2f})")
        
        # 1. Triage Intent (Casual vs Strategic)
        is_casual = len(query.split()) < 4 or any(k in query.lower() for k in ["hello", "hi", "hey", "narf", "poit", "zort"])
        
        # 2. Strategic Routing (The Expert MoE)
        selected_expert = self._route_expert_domain(query)
        
        # [PHASE 2] Turn Bundling: Parallel Dispatch
        dispatch_tasks = []
        
        if is_casual and not mic_active and retry_count == 0:
            if "pinky" in self.residents:
                t_pinky = asyncio.create_task(self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: GREETING] {exit_hint}"}))
                dispatch_tasks.append((t_pinky, "Pinky"))
        else:
            # Strategic Path
            if "pinky" in self.residents and retry_count == 0:
                await self.broadcast({
                    "brain": self.get_oracle_signal("Pinky"),
                    "brain_source": "Pinky (Intuition)",
                    "channel": "insight",
                    "is_internal": True
                })
                t_pinky = asyncio.create_task(self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: STRATEGIC_INTENT] {exit_hint}"}))
                dispatch_tasks.append((t_pinky, "Pinky"))

            if self.brain_online() and "brain" in self.residents:
                # [FEAT-174.1] Strategic Pre-Gating
                metadata = {"expert_adapter": selected_expert}
                t_brain = asyncio.create_task(self.monitor_task_with_tics(
                    self.residents["brain"].call_tool("deep_think", {"task": query, "metadata": metadata})
                ))
                dispatch_tasks.append((t_brain, "Brain"))

        # [GHOST-01-RECOVER] Parallel Turn Bundler: Collect all responses
        bundled_results = []
        if dispatch_tasks:
            pending = {t for t, s in dispatch_tasks}
            task_to_source = {t: s for t, s in dispatch_tasks}
            try:
                async with asyncio.timeout(120):
                    while pending:
                        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
                        for task in done:
                            try:
                                res = await task
                                source = task_to_source[task]
                                bundled_results.append({"source": source, "text": res.content[0].text})
                            except Exception as e:
                                logging.error(f"[HUB] Task failed for {task_to_source[task]}: {e}")
            except asyncio.TimeoutError:
                for t in pending: t.cancel()
                logging.warning("[HUB] Turn bundling timed out.")

        # 4. Processing Bundled Results
        for result in bundled_results:
            result_text = result["text"]
            source = result["source"]
            
            # [VISUAL THINK] Mark Pinky's strategic interjections as internal
            internal_flag = False
            if source == "Pinky" and any(r["source"] == "Brain" for r in bundled_results):
                internal_flag = True

            # Recursive check: if response is a tool call, handle it
            if "{" in result_text:
                await self.execute_dispatch(result_text, f"{source} (Result)", shutdown_event=shutdown_event)
                continue

            # Fidelity Gate (The BKM Audit)
            if source == "Brain":
                # [FEAT-154] Use turn_density to adjust vibe thresholds
                # Higher density (more fast turns) = lower threshold for "thin"
                base_threshold = 20
                adjusted_threshold = max(5, base_threshold - int(turn_density * 2))
                
                is_thin = len(result_text.split()) < adjusted_threshold and len(query.split()) > 4
                
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
                        # Execute targeted mass scan
                        try:
                            scan_script = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py")
                            proc = await asyncio.create_subprocess_exec(
                                sys.executable, scan_script, "--keyword", query,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE
                            )
                            await proc.communicate()
                        except Exception as e:
                            logging.error(f"[HALLWAY] Scan execution failed: {e}")

                        return await self.process_query(query, mic_active, shutdown_event, exit_hint, retry_count=retry_count+1, turn_density=turn_density)
                    
                    logging.warning(f"[FEAT-173.2] Fidelity FAILED for {selected_expert}. Triggering Strategic Pivot.")
                    await self.broadcast({
                        "brain": "derivation too thin... swapping glasses and retrying. Poit!",
                        "brain_source": "Pinky (Fidelity)",
                        "channel": "insight",
                        "is_internal": True
                    })
                    # Retry with pivot
                    return await self.process_query(query, mic_active, shutdown_event, exit_hint, retry_count=retry_count+1, turn_density=turn_density)

            # Passed Fidelity Gate or not Brain
            await self.execute_dispatch(result_text, f"{source} (Result)", shutdown_event=shutdown_event, is_internal=internal_flag)

        if not bundled_results:
            return await self.execute_dispatch("The Cognitive Hub is out of alignment.", "Pinky (System)", shutdown_event=shutdown_event)
        
        return True
