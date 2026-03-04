import asyncio
import json
import logging
import re
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
        self.is_brain_online = brain_online_callback
        self.get_oracle_signal = get_oracle_signal_callback
        self.monitor_task_with_tics = monitor_task_with_tics_callback
        self.recent_interactions = []
        reclaim_logger("COGNITIVE")

    async def check_intent_is_casual(self, text):
        casual_indicators = ["hello", "hi", "hey", "how are you", "pinky", "anyone home", "zort", "narf"]
        strat_indicators = ["architecture", "bottleneck", "optimization", "complex", "root cause", "race condition", "unstable", "design", "calculate", "math", "pi", "analysis", "history", "laboratory", "simulation"]
        
        text_low = text.lower().strip()
        if "?" in text_low or any(k in text_low for k in strat_indicators):
            return False
        if len(text_low.split()) < 3:
            return True
        return any(k in text_low for k in casual_indicators)

    async def execute_dispatch(self, raw_text, source, context_flags=None, oracle_category=None, sources=None, historical_sources=None, shutdown_event=None):
        logging.info(f"[DEBUG] Dispatch: source='{source}' text='{raw_text[:30]}...'")

        if "Brain" in source:
            banter_pattern = r"\b(narf|poit|zort|egad|trotro)\b"
            raw_text = re.sub(banter_pattern, "", raw_text, flags=re.IGNORECASE).strip()
            raw_text = re.sub(r"^[,\.\!\?\s\"\'\d]+", "", raw_text).strip()
            raw_text = re.sub(r"\*[^*]+\*", "", raw_text).strip()

        if "{" not in raw_text:
            target_channel = "insight" if "Brain" in source else "chat"
            await self.broadcast({
                "brain": raw_text,
                "brain_source": source,
                "channel": target_channel,
                "oracle_category": oracle_category,
                "sources": sources or historical_sources,
            })
            return True

        try:
            # [FEAT-121] Robust JSON Extraction: Handle banter-wrapped payloads
            data = raw_text
            if "{" in raw_text:
                match = re.search(r"(\{.*\})", raw_text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                    except Exception:
                        pass

            tool = data.get("tool") if isinstance(data, dict) else None
            params = data.get("parameters", {}) if isinstance(data, dict) else {}

            if tool == "close_lab":
                await self.broadcast({
                    "brain": "Initiating Lab Closure. Goodnight.",
                    "brain_source": "System",
                    "type": "shutdown",
                })
                if shutdown_event:
                    shutdown_event.set()
                return True

            known_tools = ["reply_to_user", "ask_brain", "deep_think", "list_cabinet", "read_document", "peek_related_notes", "write_draft", "generate_bkm", "build_semantic_map", "peek_strategic_map", "discuss_offline", "select_file", "notify_file_open", "get_lab_health", "vram_vibe_check", "access_personal_history", "build_cv_summary"]

            if tool == "select_file":
                fname = params.get("filename")
                await self.broadcast({"type": "file_content_request", "filename": fname})
                return True

            if tool == "reply_to_user" or (isinstance(data, dict) and "reply_to_user" in data):
                reply = params.get("text") or data.get("reply_to_user") or raw_text
                target_channel = "insight" if "Brain" in source else "chat"
                await self.broadcast({
                    "brain": str(reply),
                    "brain_source": source,
                    "channel": target_channel,
                    "oracle_category": oracle_category,
                    "sources": sources or historical_sources,
                })
                return True

            # [FEAT-145] Generic Node Tool Execution
            if tool in known_tools:
                # Find which node has the tool (prioritize the source node)
                target_node = None
                if source.lower() in self.residents:
                    target_node = self.residents[source.lower()]
                else:
                    # Search for any node that might have it (heuristic)
                    for name in ["pinky", "archive", "brain", "architect"]:
                        if name in self.residents:
                            target_node = self.residents[name]
                            break
                
                if target_node:
                    try:
                        res = await target_node.call_tool(tool, params)
                        # Re-dispatch the result to the UI or another node
                        return await self.execute_dispatch(res.content[0].text, f"{source} (Result)", shutdown_event=shutdown_event)
                    except Exception as e:
                        logging.error(f"[HUB] Tool execution failed: {tool} on {source}. Error: {e}")

            # Hallucination Shunt (Prevent infinite loops)
            if tool and tool not in known_tools and "Shunt" not in source:
                logging.warning(f"[SHUNT] Hallucinated tool '{tool}'.")
                if "pinky" in self.residents:
                    res = await self.residents["pinky"].call_tool("facilitate", {"query": f"I tried to use '{tool}' but it failed.", "context": ""})
                    return await self.execute_dispatch(res.content[0].text, "Pinky (Shunt)", shutdown_event=shutdown_event)

        except Exception as e:
            logging.error(f"[DISPATCH] Error: {e}")
            await self.broadcast({"brain": raw_text, "brain_source": source})
            return False

    async def process_query(self, query, mic_active=False, shutdown_event=None, exit_hint=""):
        logging.info(f"[USER] Intercom Query: {query}")
        historical_context = ""
        historical_sources = []

        # [FEAT-117] RAG Recall
        year_match = re.search(r"\b(199[0-9]|20[0-2][0-9])\b", query)
        if year_match and "archive" in self.residents:
            year = year_match.group(1)
            try:
                res_context = await self.residents["archive"].call_tool("get_context", {"query": f"Validation events from {year}"})
                rag_data = json.loads(res_context.content[0].text)
                historical_context = rag_data.get("text", "")
                historical_sources = rag_data.get("sources", [])
            except Exception as e:
                logging.error(f"[AMYGDALA] Recall failed: {e}")

        is_casual = await self.check_intent_is_casual(query)
        is_strategic = not is_casual or mic_active

        # [FEAT-153] The Resonant Chamber: Prepare Oracle Signal for "Overhearing"
        oracle_info = ""
        if is_strategic and self.is_brain_online():
            oracle_cat = "RETRIEVING" if historical_context else "HANDSHAKE"
            oracle_info = self.get_oracle_signal(oracle_cat)

        # Parallel Dispatch Map
        dispatch_tasks = []
        
        # [FEAT-157] Personality Unification: High-Fidelity Technical Personas
        pinky_persona = (
            "[PERSONA: Pinky]\n"
            "Role: Physicality Auditor / Narrative Foil.\n"
            "Style: Intuitive and alert. Ground the Brain's derivations in hardware reality (thermals, VRAM, silicon limits).\n"
            "Invariants: Keep 'Narf!' and 'Poit!' interjections. NO roleplay asterisks or physical descriptions.\n"
        )
        brain_persona = (
            "[PERSONA: The Brain]\n"
            "Role: The Sovereign Architect.\n"
            "Identity: High-authority technical strategist.\n"
            "Style: Brevity is authority. Focus on structure, logic, and root cause analysis. No cartoonish references.\n"
        )

        if "pinky" in self.residents:
            # [FEAT-153] Inject Oracle intent and [FEAT-154] Exit Hints
            pinky_ctx = f"{pinky_persona}\n[STRATEGIC_INTENT: {oracle_info}]" if oracle_info else pinky_persona
            if exit_hint:
                pinky_ctx += f"\n{exit_hint}"
            
            if is_strategic and self.is_brain_online():
                pinky_ctx += "\n[MODE: COLLABORATIVE]"
            
            t_pinky = asyncio.create_task(self.residents["pinky"].call_tool("facilitate", {"query": query, "context": pinky_ctx}))
            dispatch_tasks.append((t_pinky, "Pinky"))

        if "brain" in self.residents and (is_strategic or "brain" in query.lower()):
            if self.is_brain_online():
                # [FEAT-153] Brain receives its own signal context
                ctx = "\n".join(self.recent_interactions)
                t_brain = asyncio.create_task(self.monitor_task_with_tics(
                    self.residents["brain"].call_tool("deep_think", {
                        "task": query,
                        "context": f"{brain_persona}\n{ctx}\n[SIGNAL: {oracle_info}]\n[GROUNDING TRUTH FOR SYNTHESIS]:\n{historical_context}",
                        "metadata": {"sources": historical_sources}
                    })
                ))
                dispatch_tasks.append((t_brain, "Brain"))
            else:
                # [FEAT-157] Grounded Shadow Protocol: Clinical technical failover
                shadow_context = (
                    "[MODE: SHADOW_PROTOCOL]\n"
                    "The Sovereign Architect is offline. You are the Shadow Brain.\n"
                    "Role: Clinical technical derivation. No banter. No interjections.\n"
                    "Goal: Fulfill the technical task using local weights with lead-engineer precision."
                )
                t_shadow = asyncio.create_task(self.residents["pinky"].call_tool("facilitate", {
                    "query": query, 
                    "context": f"{shadow_context}\n{historical_context}"
                }))
                dispatch_tasks.append((t_shadow, "Brain (Shadow)"))

        if dispatch_tasks:
            self.recent_interactions.append(f"User: {query}")
            if len(self.recent_interactions) > 50:
                self.recent_interactions.pop(0)
            
            # [PHASE 2] Turn Bundling: Collect all responses
            pending = {t for t, s in dispatch_tasks}
            task_to_source = {t: s for t, s in dispatch_tasks}
            bundled_results = []

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
                                logging.error(f"[TRIAGE] Node failed: {e}")
            except asyncio.TimeoutError:
                logging.error("[HUB] Turn Bundling TIMEOUT after 120s. Sending partial bundle.")
                for t in pending: t.cancel()
                if not bundled_results:
                    await self.broadcast({"brain": "Egad! The Lab's hemispheres are out of sync! Narf!", "brain_source": "Pinky"})

            # Execute unified dispatch for the bundle
            for result in bundled_results:
                await self.execute_dispatch(
                    result["text"], 
                    result["source"], 
                    oracle_category=oracle_info if "Brain" in result["source"] else None,
                    historical_sources=historical_sources, 
                    shutdown_event=shutdown_event
                )
        return True
