import aiohttp
import json
import os
import logging
import time
from liger_kernel.transformers import (
    apply_liger_kernel_to_mistral,
    apply_liger_kernel_to_qwen2,
)
from mcp.server.fastmcp import FastMCP

# Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

        # [FEAT-240] Phase 1: Protocol Alignment
        # Register the Native Sampling bridge in the constructor to avoid race conditions
        @self.mcp.tool()
        async def native_sample(query: str, context: str = "", tools: list = None, behavioral_guidance: str = "") -> str:
            """
            The standard MCP Sampling bridge. Bypasses wrappers to talk to the model weights.
            """
            system_override = self.system_prompt
            if behavioral_guidance:
                system_override += f"\n\n[BEHAVIORAL_GUIDANCE]:\n{behavioral_guidance}"

            if tools:
                tool_desc = "\n".join([f"- {t}" for t in tools])
                system_override += f"\n\n[HUB_TOOLS]: You have access to these steering tools via the Hub:\n{tool_desc}"
            
            # [FEAT-233] Internal Streaming: Exhaust the generator and return the block
            full_response = ""
            async for token in self.generate_response(query, context, system_override=system_override):
                full_response += token
            return full_response

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
                if m in available_models or not available_models:
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

    async def ping_engine(self, force=False):
        """[FEAT-192] Checks if the backend engine is responsive with TTL throttling."""
        if not force and self._engine_cache:
            ttl = self._probe_ttl_failure if self._engine_cache.get("type") == "NONE" else self._probe_ttl_success
            if (time.time() - self._last_probe < ttl):
                return True, "Cached"

        engine_type = "VLLM" if self.primary_host == "localhost" else "OLLAMA"
        base_url = f"http://{self.primary_host}:8088" if engine_type == "VLLM" else f"http://{self.primary_host}:11434"
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
            self._engine_cache = {"type": "NONE"}
            self._last_probe = time.time()
            return False, f"Connection failed: {e}"

    async def generate_response(self, query, context="", metadata=None, system_override=None, max_tokens=1000, disable_tools=False):
        """Standard interface for LLM calls across the bicameral mind (Async Generator)."""
        if not self._engine_cache or (time.time() - self._last_probe > self._probe_ttl_success):
            ok, msg = await self.ping_engine()
            if not ok:
                yield f"Error: {msg}"
                return

        engine = self._engine_cache
        if engine.get("type") == "NONE":
            yield "Error: No engine online."
            return

        system_prompt = system_override or self.system_prompt
        if context:
            system_prompt += f"\n\n[SITUATIONAL_CONTEXT]:\n{context}"

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

    async def _stream_vllm(self, url, payload):
        """[FEAT-233] vLLM token generator."""
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=120) as r:
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

    async def _stream_ollama(self, url, payload):
        """[FEAT-233] Ollama token generator."""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, timeout=120) as r:
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
            mode = "w" if phase == "send" else "a"
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
