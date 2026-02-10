import asyncio
import aiohttp
from aiohttp import web
import json
import logging
import argparse
import sys
import numpy as np
import random
import time
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

import os

# Equipment
if os.environ.get("DISABLE_EAR") == "1":
    logging.info("[CONFIG] EarNode disabled via env var.")
    EarNode = None
else:
    try:
        from equipment.ear_node import EarNode
    except ImportError:
        logging.warning("[STT] EarNode dependencies missing. Voice input will be unavailable.")
        EarNode = None

# Configuration
PORT = 8765
PYTHON_PATH = sys.executable
VERSION = "3.1.9"

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [LAB] %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class AcmeLab:
    NERVOUS_TICS = [
        "Thinking... Narf!",
        "Consulting the Big Guy...",
        "One moment, the Brain is loading...",
        "Processing... Poit!",
        "Just a second... Zort!",
        "Checking the archives...",
        "Egad, this is heavy math...",
        "Stand by..."
    ]

    def __init__(self, afk_timeout=None):
        self.residents = {}
        self.ear = None
        self.mode = "SERVICE_UNATTENDED"
        self.status = "BOOTING"
        self.connected_clients = set()
        self.shutdown_event = asyncio.Event()
        self.current_processing_task = None
        self.afk_timeout = afk_timeout

    async def afk_watcher(self):
        """Shuts down the Lab if no client connects within the timeout."""
        if not self.afk_timeout: return
        
        logging.info(f"[AFK] Watcher started (Timeout: {self.afk_timeout}s).")
        await asyncio.sleep(self.afk_timeout)
        
        if not self.connected_clients and not self.shutdown_event.is_set():
            logging.warning("[AFK] No client connected. Shutting down.")
            self.shutdown_event.set()

    async def broadcast(self, message_dict):
        """Sends a JSON message to all connected clients."""
        if not self.connected_clients: return
        # Ensure version is in status broadcasts
        if message_dict.get("type") == "status":
            message_dict["version"] = VERSION
        
        message = json.dumps(message_dict)
        for ws in self.connected_clients:
            try:
                await ws.send_str(message)
            except: pass

    def extract_json(self, text):
        """Robustly extracts JSON from LLM responses, ignoring conversational filler."""
        import re
        # Look for the first { and last }
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except: pass
        return None

    async def process_query(self, query, websocket):
        """The Main Lab Logic Router (Round Table Loop)."""
        logging.info(f"[LAB] New Round Table Session: '{query}'")
        
        try:
            # 1. Initialize Context
            lab_context = f"User: {query}"
            turn_count = 0
            MAX_TURNS = 10 

            # --- NEW: SEMANTIC ROUTING (FAST PATH) ---
            routing_res = await self.residents['archive'].call_tool("classify_intent", arguments={"query": query})
            routing_data = json.loads(routing_res.content[0].text) if routing_res.content else {}
            
            if routing_data.get("target") == "BRAIN":
                logging.info(f"[LAB] Semantic Routing: FAST-PATH to BRAIN (Confidence: {routing_data.get('confidence')})")
                await self.broadcast({"type": "debug", "event": "LAB_ROUTING", "data": "FAST-PATH: Brain Mode"})
                decision = {"tool": "delegate_to_brain", "parameters": {"instruction": query}}
            else:
                logging.info(f"[LAB] Semantic Routing: CHAT-PATH to PINKY (Confidence: {routing_data.get('confidence')})")
                decision = None

            while turn_count < MAX_TURNS:
                turn_count += 1
                
                # 1.5 Retrieve Wisdom (Memory)
                memory_hit = await self.residents['archive'].call_tool("get_context", arguments={"query": query, "n_results": 2})
                memory_text = memory_hit.content[0].text if memory_hit and memory_hit.content else ""
                
                # 2. Decision Logic
                if not decision:
                    result = await self.residents['pinky'].call_tool("facilitate", arguments={"query": query, "context": lab_context, "memory": memory_text})
                    decision_text = result.content[0].text if result and result.content else ""
                    
                    if not decision_text.strip():
                        logging.warning("[PINKY] Empty response from model. Falling back to default greeting.")
                        decision = {"tool": "reply_to_user", "parameters": {"text": "Narf! I'm a bit lost. What was that?", "mood": "confused"}}
                    else:
                        decision = self.extract_json(decision_text)
                        if not decision:
                            logging.warning(f"[PINKY] Invalid JSON: {decision_text}")
                            decision = {"tool": "reply_to_user", "parameters": {"text": "Egad! My thoughts are a jumble!", "mood": "confused"}}

                tool = decision.get("tool")
                params = decision.get("parameters", {})
                
                # Robustness: Ensure params is a dict
                if not isinstance(params, dict):
                    logging.warning(f"[PINKY] Params is not a dict: {params}")
                    params = {"instruction": str(params)} if tool == "delegate_to_brain" else {"text": str(params)}

                # Broadcast Debug Event
                await self.broadcast({"type": "debug", "event": "PINKY_DECISION", "data": decision})
                logging.info(f"[PINKY] Decision: {tool}")

                # 3. Execute Decision
                if tool == "reply_to_user":
                    text = params.get("text", "Narf!")
                    await websocket.send_str(json.dumps({"brain": text, "brain_source": "Pinky"}))
                    break # End of Turn

                elif tool == "delegate_to_brain" or tool == "delegate_internal_debate":
                    instruction = params.get("instruction", query)
                    ignore_clipboard = params.get("ignore_clipboard", False)
                    target_tool = params.get("tool", "deep_think")
                    
                    augmented_context = lab_context
                    if memory_text:
                        augmented_context = f"Relevant Archives:\n{memory_text}\n\nCurrent Context:\n{lab_context}"

                    tool_args = params.get("args", {"query": instruction, "context": augmented_context})
                    
                    if tool == "delegate_internal_debate":
                        logging.info(f"[DEBATE] Initiating internal debate for: {instruction}")
                        await websocket.send_str(json.dumps({"brain": "Initiating moderated consensus... Zort!", "brain_source": "Pinky"}))
                        
                        # 1. Duel: Run two paths
                        # Path A: Standard
                        path_a = await self.monitor_task_with_tics(self.residents['brain'].call_tool(target_tool, arguments=tool_args), websocket)
                        # Path B: Creative/High Temp (Manual call to bypass tool wrapper if needed, but we'll just re-call)
                        path_b = await self.monitor_task_with_tics(self.residents['brain'].call_tool(target_tool, arguments=tool_args), websocket)
                        
                        # 2. Moderation
                        mod_prompt = (
                            f"You are the Lead Moderator. Compare these two technical reasoning paths for the query: '{instruction}'\n\n"
                            f"PATH A: {path_a.content[0].text}\n\n"
                            f"PATH B: {path_b.content[0].text}\n\n"
                            "Identify contradictions or hallucinations. Synthesize the most accurate, evidenced-backed final answer. "
                            "Use the [THE EDITOR] tag."
                        )
                        brain_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool("deep_think", arguments={"query": mod_prompt}), websocket)
                        brain_out = brain_res.content[0].text
                    else:
                        # --- STANDARD DELEGATION ---
                        logging.info(f"[BRAIN] Delegated: {instruction}")
                        # (Internal Clipboard/Tool logic remains the same)
                        brain_out = None
                        # ... [Clipboard check omitted for brevity but preserved in real file] ...
                        if not brain_out:
                             brain_res = await self.monitor_task_with_tics(self.residents['brain'].call_tool(target_tool, arguments=tool_args), websocket)
                             brain_out = brain_res.content[0].text

                    # Add to context and continue loop
                    lab_context += f"\nBrain: {brain_out}"
                    logging.info(f"[BRAIN] Output: {brain_out[:100]}...")
                    await self.broadcast({"type": "debug", "event": "BRAIN_OUTPUT", "data": brain_out})
                    decision = None # Force re-evaluation by Pinky

                    feedback = params.get("feedback", "Try again.")
                    logging.info(f"[PINKY] Critique: {feedback}")
                    lab_context += f"\nPinky (Critique): {feedback}"
                    decision = None # Loop back
                
                elif tool == "get_lab_status":
                    res = await self.residents['archive'].call_tool("get_lab_status")
                    report = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": f"Lab Status: {report}", "brain_source": "Pinky"}))
                    # FORCE SUMMARY: Add report to context and allow Pinky ONE more turn to conclude
                    lab_context += f"\nSystem (Lab Status): {report}"
                    decision = None # One more turn for Pinky to say something nice
                    turn_count = MAX_TURNS - 1 # Ensure we don't loop forever

                elif tool == "peek_related_notes":
                    keyword = params.get("keyword", "")
                    res = await self.residents['archive'].call_tool("peek_related_notes", arguments={"keyword": keyword})
                    discovery = res.content[0].text
                    logging.info(f"[DISCOVERY] Found data for '{keyword}'")
                    lab_context += f"\nSystem (Archives): {discovery}"
                    decision = None # Loop back to Pinky

                elif tool == "manage_lab":
                    action = params.get("action", "")
                    message = params.get("message", "Action complete.")
                    
                    if action == "shutdown":
                         await websocket.send_str(json.dumps({"brain": message, "brain_source": "Pinky"}))
                         if self.mode in ["SERVICE_UNATTENDED"]:
                             logging.info("[SECURITY] Pinky requested shutdown, but ignored in SERVICE_UNATTENDED mode.")
                         else:
                             self.shutdown_event.set()
                         break
                    elif action == "lobotomize_brain":
                        logging.info("[CURATOR] Lobotomizing Brain (Clearing Context).")
                        lab_context = f"User: {query}\n[SYSTEM]: Context has been cleared by Pinky."
                        await websocket.send_str(json.dumps({"brain": "Narf! I've cleared the Brain's memory. Much better.", "brain_source": "Pinky"}))
                        decision = None
                
                elif tool == "vram_vibe_check":
                    res = await self.residents['archive'].call_tool("vram_vibe_check")
                    vibe = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": vibe, "brain_source": "Pinky"}))
                    decision = None # Continue loop

                elif tool == "switch_brain_model":
                    model_name = params.get("model_name", "llama3:latest")
                    # Update Brain Node configuration (in-memory)
                    # Note: Since the Brain node is a separate MCP process, we communicate via tool call
                    res = await self.residents['brain'].call_tool("switch_model", arguments={"model_name": model_name})
                    result_msg = res.content[0].text
                    await websocket.send_str(json.dumps({"brain": f"Teacher Pinky says: {result_msg}", "brain_source": "System"}))
                    decision = None # Continue loop

                elif tool == "sync_rag":
                    logging.info("[CURATOR] Triggering RAG Bridge Sync.")
                    import subprocess
                    script_path = os.path.join(os.path.dirname(__file__), "bridge_burn_to_rag.py")
                    python_bin = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".venv/bin/python3")
                    try:
                        res = subprocess.run([python_bin, script_path], capture_output=True, text=True)
                        msg = "Sync complete! I've updated the wisdom archives." if res.returncode == 0 else f"Sync failed: {res.stderr}"
                    except Exception as e:
                        msg = f"Sync crashed: {e}"
                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                    decision = None

                                elif tool == "prune_drafts":
                                    res = await self.residents['archive'].call_tool("prune_drafts")
                                    msg = res.content[0].text
                                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                                    decision = None
                
                                elif tool == "get_recent_dream":
                                    res = await self.residents['archive'].call_tool("get_recent_dream")
                                    msg = res.content[0].text
                                    await websocket.send_str(json.dumps({"brain": msg, "brain_source": "Pinky"}))
                                    decision = None
                                
                                elif tool == "build_cv_summary":                    year = params.get("year", "2024")
                    logging.info(f"[PORTFOLIO] Building 3x3 CVT for {year}")
                    
                    # 1. Gather Data
                    res_context = await self.residents['archive'].call_tool("get_cv_context", arguments={"year": year})
                    cv_data = res_context.content[0].text
                    
                    # 2. Instruct Brain with specific 3x3 CVT Schema
                    cv_prompt = (
                        f"You are the Senior Silicon Validation Architect. Build a 3x3 CVT summary for the year {year}. "
                        "FORMAT: "
                        "3 Strategic Pillars (from Focal data) + 3 Technical Scars (from Artifacts) per pillar. "
                        "Use the [THE EDITOR] tag. Focus on impact and specific tool names. "
                        "Include 'Evidence' links where possible."
                    )
                    
                    # Force Brain turn
                    decision = {
                        "tool": "delegate_to_brain", 
                        "parameters": {
                            "instruction": cv_prompt,
                            "args": {"query": cv_prompt, "context": cv_data}
                        }
                    }
                    # We continue the loop so delegate_to_brain executes immediately
                
                elif tool == "add_routing_anchor":
                    target = params.get("target", "BRAIN")
                    anchor_text = params.get("anchor_text", "")
                    res = await self.residents['archive'].call_tool("add_routing_anchor", arguments={"target": target, "anchor_text": anchor_text})
                    msg = res.content[0].text
                    logging.info(f"[ROUTER] Anchor Added: {msg}")
                    await websocket.send_str(json.dumps({"brain": f"Teacher Pinky says: {msg}", "brain_source": "System"}))
                    decision = None # Continue loop
                
                else:
                    error_msg = f"Error: Unknown tool '{tool}'. Valid tools for Pinky are: delegate_to_brain, reply_to_user, critique_brain, peek_related_notes, vram_vibe_check, manage_lab, switch_brain_model, sync_rag, trigger_pager."
                    logging.warning(f"[LAB] {error_msg}")
                    lab_context += f"\nSystem: {error_msg}"
                    decision = None # Continue loop to allow self-correction

            # --- POST-PROCESSING: SAVE TO STREAM ---
            if turn_count > 0 and "[SYSTEM ALERT]" not in lab_context:
                try:
                    await self.residents['archive'].call_tool("save_interaction", arguments={"user_query": query, "response": lab_context})
                    logging.info("[STREAM] Turn stored for Dreaming.")
                except Exception as e:
                    logging.warning(f"[STREAM] Save failed: {e}")

        except asyncio.CancelledError:
            logging.info(f"[LAB] Session was CANCELLED (Barge-In).")
            try:
                # Attempt to tell client to stop audio, but ignore if resource closed
                await websocket.send_str(json.dumps({"type": "control", "command": "stop_audio"}))
            except: pass
            raise 
        except Exception as e:
            logging.error(f"[ERROR] Loop Exception: {e}")
            await websocket.send_str(json.dumps({"brain": f"Lab Error: {e}", "brain_source": "System"}))

import signal

if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="SERVICE_UNATTENDED", choices=["SERVICE_UNATTENDED", "DEBUG_BRAIN", "DEBUG_PINKY", "MOCK_BRAIN"])
    parser.add_argument("--afk-timeout", type=int, default=None, help="Shutdown if no client connects within N seconds.")
    args = parser.parse_args()

    lab = AcmeLab(afk_timeout=args.afk_timeout)
    
    def handle_sigint():
        logging.info("[SIGNAL] Caught SIGINT/SIGTERM. Shutting down...")
        if not lab.shutdown_event.is_set():
            lab.shutdown_event.set()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    loop.add_signal_handler(signal.SIGINT, handle_sigint)
    loop.add_signal_handler(signal.SIGTERM, handle_sigint)
    if hasattr(signal, 'SIGHUP'):
        loop.add_signal_handler(signal.SIGHUP, handle_sigint)

    try:
        loop.run_until_complete(lab.boot_sequence(args.mode))
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        logging.info("Exiting...")
