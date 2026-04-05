import aiohttp
import json
import os
import logging
import time
import socket
from liger_kernel.transformers import (
    apply_liger_kernel_to_mistral,
    apply_liger_kernel_to_qwen2,
)
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
            except ValueError:
                pass

        # [FEAT-220] Silicon Handshake: Consume session token and tag process title
        self.session_token = "LOCAL_ONLY"
        if "--session" in sys.argv:
            try:
                idx = sys.argv.index("--session")
                if idx + 1 < len(sys.argv):
                    self.session_token = sys.argv[idx + 1]
            except ValueError: pass
            
        title = f"[{name.upper()}:{self.session_token}]"
        try:
            import setproctitle
            setproctitle.setproctitle(title)
        except ImportError:
            sys.argv[0] = title

        self.name = name.lower()
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

        @self.mcp.tool()
        async def think(query: str, context: str = "", tools: list = None, behavioral_guidance: str = "", internal: bool = False) -> str:
            """
            [FEAT-240.2] The Relay Pattern: Standard-compliant 'Thinking' turn.
            If the model needs steering (e.g. 'ask_brain'), it uses a SamplingRequest to the Hub.
            """
            system_override = self.system_prompt
            if behavioral_guidance:
                system_override += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{behavioral_guidance}"

            # [REVISION-17.9] Relay: Tools provided by the Hub are now part of the Sampling context.
            # The model will respond natively, and if it wants to use a Hub-provided tool, 
            # it will output an [ACTION: UPLINK] tag or standard tool call that we handle via Sampling.
            
            full_response = ""
            # Only broadcast tokens if NOT an internal logic turn
            stream_source = self.name if not internal else None
            async for token in self.generate_response(query, context, system_override=system_override, source_name=stream_source):
                full_response += token
                
            # [FEAT-240.2] Sampling Bridge: Check if the response contains a steering request
            if "[ACTION: UPLINK]" in full_response or "ask_brain" in full_response:
                logging.info(f"[{self.name}] Relay: Steering intent detected. Initiating SamplingRequest...")
                # In a full MCP implementation, this would be self.mcp.get_context().request_sampling(...)
                # For now, we return the intent to the Hub to be processed by the Hub's dispatcher.
                
            return full_response

    async def create_message(self, query: str, context: str = "", tools: list = None, behavioral_guidance: str = ""):
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
        
        return self.generate_response(query, context, system_override=system_override, source_name=self.name)

    def _patch_model(self, model_id):
        """[FEAT-031] Apply fused CUDA kernels for VRAM efficiency."""
        try:
            m_id = str(model_id).lower()
            if "mistral" in m_id or "mixtral" in m_id:
                logging.info(f"[{self.name}] Applying Liger-Mistral patches.")
                apply_liger_kernel_to_mistral()
            elif "qwen" in m_id:
                logging.info(f"[{self.name}] Applying Liger-Qwen patches.")
                apply_liger_kernel_to_qwen2()
        except Exception as e:
            logging.error(f"[{self.name}] Liger patch failed: {e}")

    def _load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _resolve_best_model(self, available_models, engine_type):
        """[FEAT-080] Dynamic selection based on host capability."""
        if self.name == "brain" and self.primary_host != "localhost":
            preferred = ["llama3.1:8b", "llama3:latest", "llama3:8b", "dolphin-llama3:8b"]
            for p in preferred:
                if p in available_models:
                    return p

        env_mod = os.environ.get(f"{self.name.upper()}_MODEL")
        if env_mod:
            model_map = self.vram_config.get("model_map", {})
            if env_mod in model_map:
                m = model_map[env_mod].get(engine_type.lower())
                if m in available_models or not available_models or (engine_type == "VLLM" and m.startswith("/")):
                    return m
                else:
                    logging.warning(f"[{self.name}] Tier {env_mod} resolved to {m} but NOT FOUND on host.")

            if available_models:
                for am in available_models:
                    if env_mod in am:
                        return am
                if engine_type == "VLLM" and env_mod and (env_mod.startswith("/") or "unified-base" in available_models):
                    return "unified-base" if "unified-base" in available_models else available_models[0]
                logging.warning(f"[{self.name}] Environment model {env_mod} NOT FOUND on host. Forcing fallback.")
            else:
                return env_mod

        if self.name == "brain":
            preferred = ["llama3.1:8b", "llama3:latest", "llama3:8b", "dolphin-llama3:8b"]
            for p in preferred:
                if p in available_models:
                    return p

        if "unified-base" in available_models:
            return "unified-base"

        medium = self.vram_config.get("model_map", {}).get("MEDIUM", {}).get(engine_type.lower())
        return medium or "llama3.2:3b"

    def _resolve_primary_host(self):
        """[FEAT-255.7] Dynamic Resolution: Maps hostname to IP with infra.json fallback."""
        if self.primary_host == "localhost":
            return "127.0.0.1"
        
        if self.primary_host == "KENDER":
            # [HARDENING] Direct IP bypass for known Windows host
            return "192.168.1.26"

        try:
            # Try dynamic DNS resolution
            return socket.gethostbyname(self.primary_host)
        except Exception:
            # Fallback to ip_hint from infrastructure.json
            host_cfg = self.infra.get("hosts", {}).get(self.primary_host, {})
            return host_cfg.get("ip_hint", self.primary_host)

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
                except Exception: pass
            
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
                    
                    target = self._resolve_best_model(available, engine_type)
                    self._engine_cache = {"url": f"{base_url}/v1/chat/completions" if engine_type == "VLLM" else f"{base_url}/api/chat", "model": target, "type": engine_type}
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

    async def generate_response(self, query, context="", metadata=None, system_override=None, max_tokens=1000, disable_tools=False, source_name=None):
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
                    if f_val > 0.3: stance = "Standard"
                    if f_val > 0.6: stance = "Deep"
                    if f_val > 0.8: stance = "Sovereign"
                    masked = masked.replace(fuel_match.group(0), f"Resonance: {stance}")
            except Exception: pass
            
            masked = masked.replace("ROUTE:", "Flow:").replace("ROLE:", "Identity:")
            user_context += f"[SYSTEM_DESIGN_STANCE]:\n{masked}\n\n"
            
        # Detect guidance jammed into system_override by wrappers
        if system_override and "[BEHAVIORAL_GUIDANCE]:" in system_override:
            parts = system_override.split("[BEHAVIORAL_GUIDANCE]:")
            system_prompt = parts[0].strip()
            user_context += f"[GUIDANCE_FRAME]:\n{parts[1].strip()}\n\n"

        if user_context:
            query = f"{user_context}---\n\n{query}"

        if engine["type"] == "VLLM":
            payload = {
                "model": engine["model"],
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                "max_tokens": max_tokens,
                "temperature": 0.2,
                "stream": True
            }
            if self.lora_name:
                payload["model"] = self.lora_name
        else:
            payload = {
                "model": engine["model"],
                "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": query}],
                "stream": True,
                "options": {"temperature": 0.2, "num_predict": max_tokens}
            }

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

    async def _broadcast_token(self, token, source):
        """Helper to POST tokens to the Hub's stream_ingest endpoint."""
        try:
            # Note: We use a short timeout to prevent blocking generation
            async with aiohttp.ClientSession() as session:
                payload = {
                    "type": "brain",
                    "brain": token,
                    "brain_source": source,
                    "final": False
                }
                async with session.post("http://localhost:8765/stream_ingest", json=payload, timeout=0.5) as r:
                    pass
        except Exception:
            pass

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
            except Exception as e:
                self._engine_cache = None  # [FEAT-084] Clear cache on error
                logging.error(f"[{self.name}] Stream failed: {e}")

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
