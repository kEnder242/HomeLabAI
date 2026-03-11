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

    async def execute_dispatch(self, text, source, shutdown_event=None):
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
                known_hub_tools = ["reply_to_user", "ask_brain", "bounce_node", "scribble_note", "trigger_morning_briefing"]
                
                if tool not in available_tools and tool not in known_hub_tools:
                    logging.warning(f"[HUB] Hallucination Detected: {source} tried to use '{tool}'. Shunting to Pinky.")
                    hallucination_msg = f"Egad! I tried to use '{tool}', but my circuits don't support it yet. Narf!"
                    return await self.execute_dispatch(hallucination_msg, "Pinky (System)", shutdown_event=shutdown_event)

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

        # 3. Fallback: Pure Text
        await self.broadcast({
            "brain": clean_text,
            "brain_source": source.replace("Result", "").strip(),
            "channel": "chat"
        })
        return clean_text

    def _route_expert_domain(self, query, interjection=""):
        """[FEAT-174.1] Strategic Routing: Identifies the expert adapter needed."""
        domain_map = {
            "telemetry": "exp_tlm",
            "hardware": "exp_tlm",
            "silicon": "exp_tlm",
            "rapl": "exp_tlm",
            "architecture": "exp_bkm",
            "architectural": "exp_bkm",
            "bkm": "exp_bkm",
            "history": "exp_for",
            "code": "exp_for",
            "optimization": "exp_for"
        }
        
        q_low = query.lower()
        i_low = interjection.lower()
        
        for kw, expert in domain_map.items():
            if kw in q_low or kw in i_low:
                return expert
        
        return "exp_for" # Default Forensic/Architect

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint="", trigger_briefing_callback=None, retry_count=0):
        """The Central Reasoning Pipeline."""
        if retry_count > 2:
            logging.warning("[HUB] Max retries reached. Surrendering to base model.")
            return await self.execute_dispatch("Egad! Even the experts are stumped. Proceeding with caution.", "Pinky (System)", shutdown_event=shutdown_event)

        # [FEAT-190] Inject callbacks for tool-based logic
        if trigger_briefing_callback:
            self._trigger_briefing = trigger_briefing_callback

        logging.info(f"[USER] Intercom Query: {query} (Retry: {retry_count})")
        
        # 1. Triage Intent (Casual vs Strategic)
        is_casual = len(query.split()) < 4 or any(k in query.lower() for k in ["hello", "hi", "hey", "narf", "poit", "zort"])
        logging.info(f"[DEBUG] query='{query}' is_casual={is_casual}")

        if is_casual and not mic_active:
            if "pinky" in self.residents:
                p_res = await self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: GREETING] {exit_hint}"})
                # Check for tool call in Pinky response
                return await self.execute_dispatch(p_res.content[0].text, "Pinky (Result)", shutdown_event=shutdown_event)

        # 2. Strategic Routing (The Expert MoE)
        if "pinky" in self.residents:
            await self.broadcast({
                "brain": self.get_oracle_signal("Pinky"),
                "brain_source": "Pinky (Intuition)",
                "channel": "insight"
            })
            
            # Pinky identifies the expert domain
            p_res = await self.residents["pinky"].call_tool("facilitate", {"query": query, "context": f"[SITUATION: STRATEGIC_INTENT] {exit_hint}"})
            interjection = p_res.content[0].text
            
            # Recursive check: if Pinky response itself is a tool call, handle it
            if "{" in interjection:
                # Dispatch tool and return
                return await self.execute_dispatch(interjection, "Pinky (Result)", shutdown_event=shutdown_event)

            selected_expert = self._route_expert_domain(query, interjection)
            logging.info(f"[ROUTER] Expert Domain matched: {selected_expert} (Retry: {retry_count})")

            # 3. Brain Derivation (with Selected Expert Adapter)
            if self.brain_online():
                await self.broadcast({
                    "brain": interjection,
                    "brain_source": "Pinky (Interjection)",
                    "channel": "insight"
                })
                
                if "brain" in self.residents:
                    b_res = await self.monitor_task_with_tics(
                        self.residents["brain"].call_tool("deep_think", {"task": query, "metadata": {"expert_adapter": selected_expert}})
                    )
                    result_text = b_res.content[0].text
                    
                    # Check for tool calls first
                    if "{" in result_text:
                        # Tool call dispatched
                        return await self.execute_dispatch(result_text, "Brain (Result)", shutdown_event=shutdown_event)

                    # 4. Fidelity Gate (The BKM Audit)
                    # Check if response is dense enough for the complexity
                    is_thin = len(result_text.split()) < 20 and len(query.split()) > 4
                    
                    if is_thin:
                        if retry_count == 1:
                            # [FEAT-179] The Hallway Protocol (Agentic-R)
                            logging.warning(f"[FEAT-179] Pivot FAILED. Triggering Hallway Protocol for: {query}")
                            await self.broadcast({
                                "brain": "Expert pivot insufficient... performing deep archival harvest. Poit!",
                                "brain_source": "Pinky (Forensic)",
                                "channel": "insight"
                            })
                            
                            # Execute targeted mass scan
                            try:
                                scan_script = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/mass_scan.py")
                                proc = await asyncio.create_subprocess_exec(
                                    sys.executable, scan_script, "--keyword", query,
                                    stdout=asyncio.subprocess.PIPE,
                                    stderr=asyncio.subprocess.PIPE
                                )
                                stdout, stderr = await proc.communicate()
                                logging.info(f"[HALLWAY] Scan complete. Exit code: {proc.returncode}")
                            except Exception as e:
                                logging.error(f"[HALLWAY] Scan execution failed: {e}")

                            return await self.process_query(query, mic_active, shutdown_event, exit_hint, retry_count=retry_count+1)
                        
                        logging.warning(f"[FEAT-173.2] Fidelity FAILED for {selected_expert}. Triggering Strategic Pivot.")
                        await self.broadcast({
                            "brain": "derivation too thin... swapping glasses and retrying. Poit!",
                            "brain_source": "Pinky (Fidelity)",
                            "channel": "insight"
                        })
                        # Retry with the other primary expert
                        new_expert = "exp_tlm" if "tlm" not in selected_expert else "exp_bkm"
                        return await self.process_query(query, mic_active, shutdown_event, exit_hint, retry_count=retry_count+1)
                    
                    # Passed Fidelity Gate
                    return await self.execute_dispatch(result_text, "Brain (Result)", shutdown_event=shutdown_event)
        
        return await self.execute_dispatch("The Cognitive Hub is out of alignment.", "Pinky (System)", shutdown_event=shutdown_event)
