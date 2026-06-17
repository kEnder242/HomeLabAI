import aiohttp
import asyncio
import json
import os
import logging
import time
import socket
import threading
import queue
import requests
from mcp.server.fastmcp import FastMCP

# Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CHARACTERIZATION_FILE = os.path.expanduser(
    "~/Dev_Lab/Portfolio_Dev/field_notes/data/vram_characterization.json"
)
INFRA_CONFIG = os.path.join(LAB_DIR, "config", "infrastructure.json")
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")


class BicameralNode:
    """
    [FEAT-145] Bicameral Node: Standardized MCP wrapper for local/remote LLM nodes.
    Supports Multi-LoRA, Liger-Kernels, and Silicon Health reporting.
    """

    def __init__(self, name, system_prompt):
        # [FEAT-253] Dynamic Role Discovery: Support --role override for shadow failover
        import sys
        if "--role" in sys.argv:
            try:
                idx = sys.argv.index("--role")
                if idx + 1 < len(sys.argv):
                    name = sys.argv[idx + 1]
                    # [FIX] Pop consumed args to prevent MCP crash
                    sys.argv.pop(idx + 1)
                    sys.argv.pop(idx)
            except ValueError:
                pass

        # [FEAT-220] Silicon Handshake: Consume session token and tag process title
        self.session_token = "LOCAL_ONLY"
        if "--session" in sys.argv:
            try:
                idx = sys.argv.index("--session")
                if idx + 1 < len(sys.argv):
                    self.session_token = sys.argv[idx + 1]
                    # [FIX] Pop consumed args to prevent MCP crash
                    sys.argv.pop(idx + 1)
                    sys.argv.pop(idx)
            except ValueError:
                pass
            
        title = f"[{name.upper()}:{self.session_token}]"
        try:
            import setproctitle
            setproctitle.setproctitle(title)
        except ImportError:
            sys.argv[0] = title

        self.name = name.lower()

        # [FEAT-210] Optimized kernels (Lazy Load)
        if os.environ.get("DISABLE_EAR") != "1":
            try:
                from liger_kernel.transformers import apply_liger_kernel_to_qwen2
                apply_liger_kernel_to_qwen2()
                logging.debug(f"[{self.name}] Liger kernels applied.")
            except Exception as e:
                logging.warning(f"[{self.name}] Liger application failed: {e}")

        self.system_prompt = system_prompt
        self.mcp = FastMCP(name)
        self._last_brain_prime = 0
        self.brain_online = True
        self._engine_cache = None
        self._last_probe = 0
        self._probe_ttl_success = 300  # 5 Minutes [FEAT-206]
        self._probe_ttl_failure = 15   # 15 Seconds [FEAT-206]

        # Load configs
        self.vram_config = self._load_json(CHARACTERIZATION_FILE)
        self.infra = self._load_json(INFRA_CONFIG)

        # Identity
        node_cfg = self.infra.get("nodes", {}).get(self.name, {})
        self.primary_host = node_cfg.get("primary", "localhost")
        self.lora_name = node_cfg.get("lora_name")

        # [Task 6.1] Physics: Single Telemetry Relay Thread
        self.telemetry_queue = queue.Queue()
        self._start_telemetry_relay()

        @self.mcp.tool()
        async def think(query: str, context: str = "", tools: list = None, behavioral_guidance: str = "", internal: bool = False, temperature: float = 0.0, repetition_penalty: float = 1.0, use_lora: bool = True, response_format: dict = None, request_id: str = "default") -> str:
            """
            [FEAT-240.2] The Relay Pattern: Standard-compliant 'Thinking' turn.
            Supports real-time token yielding to the Hub for internal waterfall streaming.
            """
            system_override = self.system_prompt
            if behavioral_guidance:
                system_override += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{behavioral_guidance}"

            full_response = ""
            # [FEAT-233] Internal Waterfall: Only broadcast tokens to UI if NOT internal.
            # Internal turns (Triage/Intuition) are overheard via the Hub's stream_ingest.
            stream_source = self.name if not internal else None
            
            # [FEAT-307] Sanitary Filter: Redirect turn-level noise to stderr
            # This is critical to prevent logs from breaking the stdio MCP transport.
            import sys
            from contextlib import redirect_stdout
            with redirect_stdout(sys.stderr):
                # Pass sampling parameters for small model stability
                # [FEAT-339] Use LoRA by default, but allow override for stability
                async for token in self.generate_response(query, context, system_override=system_override, source_name=stream_source, temperature=temperature, repetition_penalty=repetition_penalty, use_lora=use_lora, tools=tools, response_format=response_format):
                    full_response += token
                    if stream_source:
                        self._broadcast_token(token, stream_source, request_id=request_id)
                
                # [FEAT-233.7] Signal completion
                if stream_source:
                    self._broadcast_token("", stream_source, final=True, request_id=request_id)
                
            return full_response

    async def create_message(self, query: str, context: str = "", tools: list = None, behavioral_guidance: str = "", response_format: dict = None, request_id: str = "default"):
        """
        [FEAT-240.2] Native Sampling Bridge (Streaming).
        Returns an async generator of tokens.
        """
        system_override = self.system_prompt
        if behavioral_guidance:
            system_override += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{behavioral_guidance}"

        if tools:
            tool_desc = "\n".join([f"- {t}" for t in tools])
            system_override += f"\n\n[HUB_TOOLS]: You have access to these steering tools via the Hub:\n{tool_desc}"
        
        return self.generate_response(query, context, system_override=system_override, source_name=self.name, response_format=response_format)

    def _load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _resolve_best_model(self, available_models, engine_type, running_model=None):
        """[FEAT-080] Dynamic selection based on host capability."""
        # [FEAT-320] Adaptive Priority: If a model is already running on remote Ollama, use it.
        if running_model and self.name in ["brain", "thought"] and self.primary_host != "localhost":
            logging.info(f"[{self.name}] Adaptive Priority: Adopting running model '{running_model}'")
            return running_model

        # [FEAT-339] Tier Resolution: Default to UNIFIED if no environment override
        env_mod = os.environ.get(f"{self.name.upper()}_MODEL") or "UNIFIED"
        
        model_map = self.vram_config.get("model_map", {})
        if env_mod in model_map:
            m = model_map[env_mod].get(engine_type.lower())
            # Path matching for VLLM
            if engine_type == "VLLM":
                if m in available_models or "unified-base" in available_models:
                    return m
            elif m in available_models or not available_models:
                return m
            
            logging.warning(f"[{self.name}] Tier {env_mod} ({m}) NOT FOUND on host. Available: {available_models}")

        if available_models:
            # Fallback to serving name if found
            if "unified-base" in available_models:
                return "unified-base"
            
            # [FIX] Filter out non-chat models (embeddings) from fallback
            chat_candidates = [m for m in available_models if not any(x in m.lower() for x in ["nomic", "embed", "bert", "ranker"])]
            if chat_candidates:
                # Prefer known high-fidelity models for Sovereign
                for fav in ["llama3.1:8b", "llama3.2:3b", "gemma"]:
                    for c in chat_candidates:
                        if fav in c.lower():
                            return c
                return chat_candidates[0]
            
            # If ONLY non-chat models exist, return None to trigger downshift
            return None

        return "llama3.2:3b"

    def _resolve_primary_host(self):
        """[FEAT-255.7] Dynamic Resolution with [FEAT-265] Discovery."""
        if self.primary_host in ["localhost", "127.0.0.1", "z87-Linux"]:
            target = "127.0.0.1"
            logging.info(f"[{self.name}] Resolved primary host to local: {target}")
            return target
        
        # [Task 6.5] Dynamic Discovery for Sovereign IP
        host_cfg = self.infra.get("hosts", {}).get(self.primary_host, {})
        ip_hint = host_cfg.get("ip_hint")
        if ip_hint:
            logging.info(f"[{self.name}] Using dynamic IP hint for {self.primary_host}: {ip_hint}")
            return ip_hint

        try:
            # Try dynamic DNS resolution
            res = socket.gethostbyname(self.primary_host)
            logging.info(f"[{self.name}] Resolved {self.primary_host} to: {res}")
            return res
        except Exception:
            return "127.0.0.1"

    async def ping_engine(self, force=False):
        """[FEAT-192] Checks if the backend engine is responsive with TTL throttling."""
        if not force and self._engine_cache:
            ttl = self._probe_ttl_failure if self._engine_cache.get("type") == "NONE" else self._probe_ttl_success
            if (time.time() - self._last_probe < ttl):
                return True, "Cached"

        # [FEAT-255.1] Dynamic Registry: Sync engine type with status.json
        resolved_ip = self._resolve_primary_host()
        
        if self.primary_host == "localhost":
            engine_type = os.environ.get("LAB_MODE", "VLLM")
            status_path = os.path.join(LAB_DIR, "status.json")
            if os.path.exists(status_path):
                try:
                    with open(status_path, "r") as f:
                        status = json.load(f)
                        engine_type = status.get("mode", engine_type)
                except Exception:
                    pass
            
            port = 8088 if engine_type == "VLLM" else 11434
            base_url = f"http://{resolved_ip}:{port}"
        else:
            engine_type = "OLLAMA"
            base_url = f"http://{resolved_ip}:11434"
        
        models_url = f"{base_url}/v1/models" if engine_type == "VLLM" else f"{base_url}/api/tags"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(models_url, timeout=5) as r:
                    if r.status != 200:
                        self._engine_cache = {"type": "NONE"}
                        self._last_probe = time.time()
                        return False, f"Engine {engine_type} unreachable (Status {r.status})"
                    data = await r.json()
                    
                    available = []
                    if engine_type == "VLLM":
                        available = [m["id"] for m in data.get("data", [])]
                    else:
                        available = [m["name"] for m in data.get("models", [])]
                    
                    # [FEAT-320] Adaptive Model Selection: Check what's actually running
                    running_model = None
                    if engine_type == "OLLAMA" and self.primary_host != "localhost":
                        try:
                            ps_url = f"{base_url}/api/ps"
                            async with session.get(ps_url, timeout=2) as ps_r:
                                if ps_r.status == 200:
                                    ps_data = await ps_r.json()
                                    models = ps_data.get("models", [])
                                    if models:
                                        running_model = models[0].get("name")
                                        logging.info(f"[{self.name}] Adaptive Link: Adopting active model '{running_model}' on {self.primary_host}")
                        except Exception:
                            pass

                    target = self._resolve_best_model(available, engine_type, running_model=running_model)
                    
                    # [FEAT-339] Model Alias Resolution: Map paths to short IDs
                    # If target is a path, try to find a short ID in 'available' that matches the root
                    if target.startswith("/") and available:
                        # Exact path match in available models (vLLM sometimes does this)
                        if target in available:
                            pass 
                        else:
                            # Try to match by basename or served model names
                            for am in available:
                                if am == "unified-base" or am in target:
                                    logging.info(f"[{self.name}] Alias Resolved: {target} -> {am}")
                                    target = am
                                    break

                    self._engine_cache = {
                        "url": f"{base_url}/v1/chat/completions" if engine_type == "VLLM" else f"{base_url}/api/chat", 
                        "model": target, 
                        "type": engine_type,
                        "available": available
                    }
                    self._last_probe = time.time()
                    return True, f"Online: {target} ({engine_type})"
        except Exception as e:
            # [FEAT-255.3] Handshake Resilience: Tolerate ZMQ/Transfer errors during boot
            err_msg = str(e).lower()
            if any(k in err_msg for k in ["transfer", "reset", "disconnected", "incomplete", "refused", "eof"]):
                # [FEAT-255.6] Exponential Backoff: Give the larynx time to clear its throat
                wait_time = getattr(self, "_handshake_backoff", 2)
                logging.warning(f"[{self.name}] Larynx is warming... (Retrying in {wait_time}s: {e})")
                await asyncio.sleep(wait_time)
                self._handshake_backoff = min(wait_time * 2, 10) # Cap at 10s
                return False, "WARMING"
            
            self._handshake_backoff = 2 # Reset on fatal error

            # [FEAT-255.4] Reactive Discovery: Flush session and cache on error
            self._engine_cache = None
            self._last_probe = 0 
            if hasattr(self, "_session") and self._session:
                await self._session.close()
                self._session = None
            return False, f"Connection failed: {e}"

    async def generate_response(self, query, context="", metadata=None, system_override=None, max_tokens=1000, disable_tools=False, source_name=None, temperature=0.2, repetition_penalty=1.0, use_lora=True, tools=None, response_format=None):
        """Standard interface for LLM calls across the bicameral mind (Async Generator)."""
        if not self._engine_cache or (time.time() - self._last_probe > self._probe_ttl_success):
            ok, msg = await self.ping_engine()
            if not ok:
                if msg == "WARMING":
                    yield "[SYSTEM]: Larynx is warming... Narf!"
                else:
                    yield f"Error: {msg}"
                return

        engine = self._engine_cache
        if engine.get("type") == "NONE":
            yield "Error: No engine online."
            return

        system_prompt = system_override or self.system_prompt
        
        # [FEAT-254.2] Metadata Displacement: Context shifts from system to user
        # This prevents 3B models from confusing system data with their core identity.
        user_context = ""
        if context:
            # [MASKING] Convert technical metrics into qualitative design stances
            # This prevents the model from citing "Fuel: 0.80" in its response.
            masked = context
            try:
                # Extract numerical fuel if present
                import re
                fuel_match = re.search(r"FUEL: ([\d\.]+)", context)
                if fuel_match:
                    f_val = float(fuel_match.group(1))
                    stance = "Surface"
                    if f_val > 0.3:
                        stance = "Standard"
                    if f_val > 0.6:
                        stance = "Deep"
                    if f_val > 0.8:
                        stance = "Sovereign"
                    masked = masked.replace(fuel_match.group(0), f"Resonance: {stance}")
            except Exception:
                pass
            
            masked = masked.replace("ROUTE:", "Flow:").replace("ROLE:", "Identity:")
            user_context += f"[SYSTEM_DESIGN_STANCE]:\n{masked}\n\n"
            
        # Detect guidance jammed into system_override by wrappers
        if system_override and "[BEHAVIORAL_GUIDANCE]:" in system_override:
            parts = system_override.split("[BEHAVIORAL_GUIDANCE]:")
            system_prompt = parts[0].strip()
            user_context += f"[GUIDANCE_FRAME]:\n{parts[1].strip()}\n\n"

        if user_context:
            # [Task 20.5] Append context to end to preserve prefix hash
            query = f"{query}\n\n---\n[DYNAMIC_CONTEXT]:\n{user_context}"

        if engine["type"] == "VLLM":
            payload = {
                "model": engine["model"],
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                "max_tokens": max_tokens,
                "temperature": temperature,
                "repetition_penalty": repetition_penalty,
                "stream": True
            }
            if self.lora_name and use_lora:
                # [FEAT-339] Adaptive LoRA: Verify availability before requesting
                if self.lora_name in engine.get("available", []):
                    payload["model"] = self.lora_name
                else:
                    logging.warning(f"[{self.name}] LoRA '{self.lora_name}' not active on vLLM. Falling back to base: {engine['model']}")
                
            # [Task 9.2] Enforce explicit JSON schema if provided
            if response_format:
                payload["response_format"] = response_format
            # [Task 19.7.1] Guided JSON Tool Calling (Option B)
            elif tools and not disable_tools:
                payload["response_format"] = {
                    "type": "json_schema",
                    "json_schema": {
                        "name": "tool_call",
                        "schema": {
                            "type": "object",
                            "properties": {
                                "thought": {"type": "string", "description": "Your persona interjection (e.g., Narf!) and thought process."},
                                "tool_name": {"type": "string", "description": "The name of the tool to use"},
                                "arguments": {"type": "object", "description": "Arguments for the tool"}
                            },
                            "required": ["thought"]
                        }
                    }
                }
        else:
            payload = {
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                "stream": True,
                "options": {"temperature": temperature, "num_predict": max_tokens, "repeat_penalty": repetition_penalty}
            }
            # [FEAT-344] Ollama Niceness: Only send model if explicitly configured.
            # If null/empty, Ollama uses the currently resident model.
            if engine.get("model"):
                payload["model"] = engine["model"]

        self._mirror_trace("send", payload, url=engine["url"], metadata=metadata)

        full_response = ""
        try:
            if engine["type"] == "VLLM":
                async for token in self._stream_vllm(engine["url"], payload):
                    full_response += token
                    yield token
            else:
                async for token in self._stream_ollama(engine["url"], payload):
                    full_response += token
                    yield token
            
            self._mirror_trace("recv", full_response)
        except Exception as e:
            logging.error(f"[{self.name}] Generation failed: {e}")
            yield f"Egad! Logic failure: {e}"

    def _start_telemetry_relay(self):
        """[FEAT-233.2] Dedicated thread for non-blocking token delivery."""
        def _relay_worker():
            while True:
                item = self.telemetry_queue.get()
                if item is None: break
                try:
                    # In V5, Foyer is at 8765
                    requests.post("http://localhost:8765/stream_ingest", json=item, timeout=0.5)
                except Exception: pass
                self.telemetry_queue.task_done()
        threading.Thread(target=_relay_worker, daemon=True).start()

    def _broadcast_token(self, token, source_name, final=False, request_id="default"):
        """Threaded fire-and-forget relay via persistent worker."""
        payload = {
            "text": token, 
            "source": source_name, 
            "final": final,
            "request_id": request_id
        }
        self.telemetry_queue.put(payload)

    async def _stream_vllm(self, url, payload):
        """[FEAT-233] vLLM token generator."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=120) as r:
                    if r.status != 200:
                        err = await r.text()
                        logging.error(f"[{self.name}] vLLM Error {r.status}: {err}")
                        yield f"Error: vLLM returned {r.status}"
                        return

                    async for line in r.content:
                        if line:
                            decoded = line.decode('utf-8').strip()
                            if decoded.startswith("data: "):
                                if "[DONE]" in decoded:
                                    break
                                try:
                                    data = json.loads(decoded[6:])
                                    token = data["choices"][0]["delta"].get("content", "")
                                    if token:
                                        yield token
                                except Exception:
                                    continue
            except aiohttp.ClientPayloadError as pe:
                logging.error(f"[{self.name}] Payload Error (vLLM Crash?): {pe}")
                yield f"Error: Engine communication broken ({pe})"
            except Exception as e:
                logging.error(f"[{self.name}] vLLM Connection failed: {e}")
                yield f"Error: vLLM connection failed: {e}" 

    async def _stream_ollama(self, url, payload):
        """[FEAT-233] Ollama token generator."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=120) as r:
                    if r.status != 200:
                        err = await r.text()
                        logging.error(f"[{self.name}] Ollama Error {r.status}: {err}")
                        yield f"Error: Ollama returned {r.status}"
                        return
                    async for line in r.content:
                        if line:
                            try:
                                data = json.loads(line.decode('utf-8'))
                                token = data.get("message", {}).get("content", "")
                                if token:
                                    yield token
                                if data.get("done"):
                                    break
                            except Exception:
                                continue
            except aiohttp.ClientPayloadError as pe:
                self._engine_cache = None
                logging.error(f"[{self.name}] Payload Error (Ollama Crash?): {pe}")
                yield f"Error: Engine communication broken ({pe})"
            except Exception as e:
                self._engine_cache = None  # [FEAT-084] Clear cache on error
                logging.error(f"[{self.name}] Stream failed: {e}")
                yield f"Error: Stream failed: {e}"

    def _mirror_trace(self, phase, data, url=None, metadata=None):
        """[FEAT-078] Neural Trace: Persists black-box payloads for auditability."""
        try:
            lab_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_dir = os.path.join(lab_root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"trace_{self.name}.json")
            mode = "a"
            entry = {"phase": phase, "timestamp": time.time(), "data": data, "metadata": metadata}
            if url:
                entry["url"] = url
            with open(log_path, mode) as f:
                f.write(json.dumps(entry, indent=2) + "\n")
        except Exception:
            pass

    async def call_remote_tool(self, target_node: str, tool_name: str, parameters: dict) -> str:
        logging.info(f"[{self.name}] Requesting remote tool: {target_node}.{tool_name}")
        return json.dumps({
            "error": "Cross-node tool calling is in DESIGN. Use 'ask_brain' for delegation.",
            "suggestion": f"I cannot reach {target_node} directly."
        })

    def run(self):
        self.mcp.run()
