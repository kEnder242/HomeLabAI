import aiohttp
import json
import os
import logging
from liger_kernel.transformers import (
    apply_liger_kernel_to_mistral,
    apply_liger_kernel_to_qwen2,
)
import socket
import time
from mcp.server.fastmcp import FastMCP
from infra.montana import reclaim_logger

# Global Paths
LAB_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
CHARACTERIZATION_FILE = os.path.join(FIELD_NOTES_DATA, "vram_characterization.json")
INFRA_CONFIG = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")


def resolve_ip(hostname, default_ip=None):
    """Dynamic resolution of hostnames to IPs with short timeout."""
    try:
        return socket.gethostbyname(hostname)
    except Exception:
        return default_ip


class BicameralNode:
    def __init__(self, name, system_prompt):
        self.name = name.lower()
        reclaim_logger(self.name.upper())
        self.system_prompt = system_prompt
        self.mcp = FastMCP(name)
        self.engine_mode = "AUTO"
        self.lobotomy_active = False

        # [FEAT-084] Neural Persistence: Cache engine resolution
        # to avoid per-query network hits
        self._engine_cache = None
        self._last_probe = 0
        self._probe_ttl = 60  # Seconds

        # Load configs
        self.vram_config = self._load_json(CHARACTERIZATION_FILE)
        self.infra = self._load_json(INFRA_CONFIG)

        # Identity
        node_cfg = self.infra.get("nodes", {}).get(self.name, {})
        self.primary_host = node_cfg.get("primary", "localhost")
        self.lora_name = node_cfg.get("lora_name")

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

        # [SML ALIGNMENT] Remote Sovereign Priority
        # If this is the Brain and it's on a remote host, prioritize the
        # preferred list to prevent Linux-specific tiering (like MEDIUM)
        # from causing failover.
        if self.name == "brain" and self.primary_host != "localhost":
            preferred = [
                "llama3.1:8b",
                "llama3:latest",
                "llama3:8b",
                "dolphin-llama3:8b",
            ]
            for p in preferred:
                if p in available_models:
                    return p

        # 1. Check for direct model override first
        env_mod = os.environ.get(f"{self.name.upper()}_MODEL")

        if env_mod:
            # If it's a known tier, resolve it
            model_map = self.vram_config.get("model_map", {})
            if env_mod in model_map:
                m = model_map[env_mod].get(engine_type.lower())
                # Verify tier resolution exists on host
                if m in available_models or not available_models:
                    return m
                else:
                    logging.warning(
                        f"[{self.name}] Tier {env_mod} resolved to {m} "
                        "but NOT FOUND on host."
                    )

            # If it's a direct model name or resolved tier, verify it exists on host
            # [HARDENING] vLLM paths may not match served IDs.
            if available_models:
                if env_mod in available_models:
                    return env_mod
                
                # [FEAT-145] vLLM Path Trust: If it's an absolute path and we are in VLLM mode,
                # assume the engine is serving this model under a unified ID.
                if engine_type == "VLLM" and env_mod and (env_mod.startswith("/") or "unified-base" in available_models):
                    return available_models[0]

                logging.warning(
                    f"[{self.name}] Environment model {env_mod} "
                    "NOT FOUND on host. Forcing fallback."
                )
            else:
                # No host tags? Trust ENV but expect failure
                return env_mod

        # 2. Preferred high-fidelity list for Brain
        if self.name == "brain":
            # [FEAT-083] Smaller Sovereign: Exclusively target fast 8B models
            # for <10s load times. Mixtral and other large models are
            # explicitly banned to prevent cold-start delays.
            preferred = [
                "llama3.1:8b",
                "llama3:latest",
                "llama3:8b",
                "dolphin-llama3:8b",
            ]
            for p in preferred:
                if p in available_models:
                    return p

        # 3. Fallback to model_map MEDIUM
        medium = (
            self.vram_config.get("model_map", {})
            .get("MEDIUM", {})
            .get(engine_type.lower())
        )
        if available_models and medium in available_models:
            return medium

        # 4. Ultimate Fallback: The first model the host has
        if available_models:
            logging.info(
                f"[{self.name}] No preferred models found. "
                f"Selecting host default: {available_models[0]}"
            )
            return available_models[0]

        return "llama3:latest"

    async def probe_engine(self, force=False):
        """Dynamic engine selection with Federated Failover."""
        # [FEAT-084] Return cached engine if available and TTL not exceeded
        if (
            not force
            and self._engine_cache
            and (time.time() - self._last_probe < self._probe_ttl)
        ):
            return self._engine_cache

        async with aiohttp.ClientSession() as session:
            # 1. Check Primary Host (e.g., KENDER)
            p_host_cfg = self.infra.get("hosts", {}).get(self.primary_host, {})
            p_ip = resolve_ip(self.primary_host, p_host_cfg.get("ip_hint"))

            if p_ip and self.primary_host != "localhost":
                p_url = f"http://{p_ip}:{p_host_cfg.get('ollama_port', 11434)}"
                try:
                    async with session.get(f"{p_url}/api/tags", timeout=5.0) as r:
                        if r.status == 200:
                            data = await r.json()
                            available = [m.get("name") for m in data.get("models", [])]
                            model = self._resolve_best_model(available, "OLLAMA")

                            res = ("OLLAMA", f"{p_url}/api/chat", model)
                            # Only log if the result changed or was empty
                            if res != self._engine_cache:
                                logging.info(
                                    f"[{self.name}] Resolved Primary: {p_ip} -> {model}"
                                )

                            self._engine_cache = res
                            self._last_probe = time.time()
                            return res
                except Exception as e:
                    logging.debug(f"[{self.name}] Primary Host {p_ip} unreachable: {e}")

            # 2. Fallback to localhost (vLLM then Ollama)
            l_host_cfg = self.infra.get("hosts", {}).get("localhost", {})

            # Check vLLM
            v_url = f"http://127.0.0.1:{l_host_cfg.get('vllm_port', 8088)}"
            try:
                async with session.get(f"{v_url}/v1/models", timeout=2.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        available = [m.get("id") for m in data.get("data", [])]
                        model = self._resolve_best_model(available, "VLLM")

                        res = ("VLLM", f"{v_url}/v1/chat/completions", model)
                        if res != self._engine_cache:
                            logging.info(
                                f"[{self.name}] Resolved Local vLLM -> {model}"
                            )

                        self._engine_cache = res
                        self._last_probe = time.time()
                        return res
            except Exception:
                pass

            # Check Local Ollama
            o_url = f"http://127.0.0.1:{l_host_cfg.get('ollama_port', 11434)}"
            try:
                async with session.get(f"{o_url}/api/tags", timeout=1.0) as r:
                    if r.status == 200:
                        data = await r.json()
                        available = [m.get("name") for m in data.get("models", [])]
                        model = self._resolve_best_model(available, "OLLAMA")

                        res = ("OLLAMA", f"{o_url}/api/chat", model)
                        if res != self._engine_cache:
                            logging.info(
                                f"[{self.name}] Resolved Local Ollama -> {model}"
                            )

                        self._engine_cache = res
                        self._last_probe = time.time()
                        return res
            except Exception:
                pass

        return "NONE", None, None

    async def ping_engine(self, force=False):
        """[FEAT-192] Verify and force engine readiness via /api/generate probe."""
        engine, url, model = await self.probe_engine(force=force)
        if engine == "NONE":
            return False, "No engine online."
        
        try:
            async with aiohttp.ClientSession() as session:
                if engine == "OLLAMA":
                    gen_url = url.replace("/api/chat", "/api/generate")
                    payload = {
                        "model": model,
                        "prompt": "ping",
                        "stream": False,
                        "options": {"num_predict": 1}
                    }
                    async with session.post(gen_url, json=payload, timeout=5.0) as r:
                        return r.status == 200, f"Ollama {r.status}"
                elif engine == "VLLM":
                    # Use the models endpoint for a quick health check
                    health_url = url.replace("/v1/chat/completions", "/v1/models")
                    async with session.get(health_url, timeout=5.0) as r:
                        return r.status == 200, f"vLLM {r.status}"
        except Exception as e:
            return False, f"Ping error: {e}"
        return False, "Unknown engine state"

    def get_tool_schemas(self, allowlist=None):
        """
        [FEAT-189] Tool Pruning: Generates OpenAI-compatible tool schemas,
        optionally filtered by an allowlist.
        """
        tools = []
        for tool_obj in self.mcp._tool_manager.list_tools():
            if allowlist and tool_obj.name not in allowlist:
                continue
            tools.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool_obj.name,
                        "description": tool_obj.description or "",
                        "parameters": tool_obj.parameters,
                    },
                }
            )

        core_tools = [
            {
                "type": "function",
                "function": {
                    "name": "ask_brain",
                    "description": "Delegate reasoning to the Left Hemisphere.",
                    "parameters": {
                        "type": "object",
                        "properties": {"task": {"type": "string"}},
                        "required": ["task"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "scribble_note",
                    "description": "Caches a response semantically for future recall.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                            "response": {"type": "string"}
                        },
                        "required": ["query", "response"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "bounce_node",
                    "description": "Trigger a local process restart for this hemisphere.",
                    "parameters": {
                        "type": "object",
                        "properties": {"reason": {"type": "string"}},
                        "required": ["reason"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "reply_to_user",
                    "description": "Provide natural language response.",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            },
        ]
        
        for ct in core_tools:
            if allowlist and ct["function"]["name"] not in allowlist:
                continue
            tools.append(ct)
            
        return tools

    def unify_prompt(self, query, context="", memory="", system_override=None):
        """[FEAT-189] Instruct Template: Uses Llama-3.1 header tokens for raw generation."""
        system = system_override if system_override else self.system_prompt
        
        # [RE-FEAT-121] Physical Identity Grounding
        # Inject hardware reality into the system persona
        hosts = self.infra.get("hosts", {})
        localhost = hosts.get("localhost", {})
        kender = hosts.get("KENDER", {})
        lab_map = (
            "\n[PHYSICAL_LAB_MAP]\n"
            f"- Local Node (This Host): RTX 2080 Ti (11GB VRAM) | IP: {localhost.get('ip_hint', '127.0.0.1')}\n"
            f"- Remote Node (KENDER): RTX 4090 (24GB VRAM) | IP: {kender.get('ip_hint', '192.168.1.26')}\n"
            f"- Current Identity: {self.name.upper()}\n"
        )
        system = f"{lab_map}\n{system}"

        if memory:
            system += f"\n\n[MEMORY]:\n{memory}"
        if context:
            system += f"\n\n[CONTEXT]:\n{context}"

        # Llama-3.1 Instruct Format
        return (
            "<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\n"
            f"{system}<|eot_id|>"
            "<|start_header_id|>user<|end_header_id|>\n\n"
            f"{query}<|eot_id|>"
            "<|start_header_id|>assistant<|end_header_id|>\n\n"
        )

    async def generate_response(
        self,
        query,
        context="",
        memory="",
        system_override=None,
        max_tokens=2048,
        metadata=None,
        disable_tools=False,
    ):
        engine, url, model = await self.probe_engine()
        # [FEAT-031] Liger Optimization
        if engine == "VLLM":
            self._patch_model(model)
        if engine == "NONE":
            return json.dumps(
                {
                    "tool": "reply_to_user",
                    "parameters": {"text": "Egad! Weights offline!"},
                }
            )

        # [FEAT-189] Tool Pruning: derived from metadata
        tool_allowlist = metadata.get("tool_allowlist") if metadata else None

        async with aiohttp.ClientSession() as session:
            try:
                if engine == "VLLM":
                    unified = self.unify_prompt(query, context, memory, system_override)
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": unified}],
                        "max_tokens": max_tokens,
                    }
                    if not disable_tools:
                        payload["tools"] = self.get_tool_schemas(allowlist=tool_allowlist)
                        payload["tool_choice"] = "auto"
                    adapter_name = self.lora_name
                    if metadata and metadata.get("expert_adapter"):
                        adapter_name = metadata.get("expert_adapter")
                        logging.info(f"[{self.name}] [FEAT-174.2] Dynamically selecting expert adapter: {adapter_name}")

                    if adapter_name:
                        # [FEAT-145] Adaptive Unity: Only request LoRA if the adapter is physically present
                        adapter_path = f"/speedy/models/adapters/{adapter_name}"
                        if os.path.exists(adapter_path):
                            payload["lora_request"] = {"name": adapter_name}
                        else:
                            logging.warning(f"[{self.name}] Adapter {adapter_name} missing at {adapter_path}. Falling back to unified base.")
                    async with session.post(url, json=payload, timeout=120) as r:
                        data = await r.json()
                        if "choices" not in data:
                            logging.error(f"[{self.name}] vLLM Error: {data}")
                            self._engine_cache = None  # [FEAT-084] Clear cache on error
                            return json.dumps(
                                {
                                    "tool": "reply_to_user",
                                    "parameters": {"text": f"vLLM Error: {data}"},
                                }
                            )
                        msg = data["choices"][0]["message"]
                        if msg.get("tool_calls"):
                            tc = msg["tool_calls"][0]["function"]
                            return json.dumps(
                                {
                                    "tool": tc["name"],
                                    "parameters": json.loads(tc["arguments"]),
                                }
                            )
                        return msg["content"]
                else:
                    # [STABILITY] Use Chat API by default for all hosts (Local & Remote)
                    chat_url = url.replace("/api/generate", "/api/chat")
                    
                    full_system = (
                        system_override if system_override else self.system_prompt
                    )
                    if memory:
                        full_system += f"\n\n[MEMORY]:\n{memory}"
                    if context:
                        full_system += f"\n\n[RECENT CONTEXT]:\n{context}"

                    messages = [
                        {"role": "system", "content": full_system},
                        {"role": "user", "content": query},
                    ]
                    payload = {
                        "model": model,
                        "messages": messages,
                        "stream": False,
                        "options": {"num_predict": max_tokens},
                    }

                    # [FEAT-078] Neural Trace (Pre-Send)
                    self._mirror_trace("send", payload, chat_url, metadata=metadata)

                    async with session.post(chat_url, json=payload, timeout=120) as r:
                        if r.status != 200:
                            # LEGACY FALLBACK: Downshift to /api/generate
                            logging.warning(f"[{self.name}] Chat API failed ({r.status}). Falling back to Generate.")
                            gen_url = url.replace("/api/chat", "/api/generate")
                            unified = self.unify_prompt(query, context, memory, system_override)
                            gen_payload = {
                                "model": model,
                                "prompt": unified,
                                "stream": False,
                                "options": {"num_predict": max_tokens},
                            }
                            async with session.post(gen_url, json=gen_payload, timeout=120) as r2:
                                data = await r2.json()
                                raw_resp = data.get("response", "").strip()
                        else:
                            data = await r.json()
                            raw_resp = data.get("message", {}).get("content", "").strip()

                        # [FEAT-078] Neural Trace (Post-Recv)
                        self._mirror_trace("recv", data)

                        # [STABILITY] Explicit Error Detection
                        if data.get("error"):
                            logging.error(f"[{self.name}] Ollama Error: {data.get('error')}")
                            self._engine_cache = None  # [FEAT-084] Clear cache on error
                            return "INTERNAL_QUALITY_FALLBACK"

                        logging.info(f"[{self.name}] RAW OLLAMA RESP: '{raw_resp[:50]}...'")

                        # [FEAT-077] Quality-Gate: If response is empty
                        if not raw_resp or raw_resp in ["...", ".", ""]:
                            logging.warning(f"[{self.name}] Host returned empty. Triggering internal quality fallback.")
                            return "INTERNAL_QUALITY_FALLBACK"
                        return raw_resp
            except Exception as e:
                self._engine_cache = None  # [FEAT-084] Clear cache on error
                return json.dumps(
                    {
                        "tool": "reply_to_user",
                        "parameters": {"text": f"Error: {e}"},
                    }
                )

    def _mirror_trace(self, phase, data, url=None, metadata=None):
        """[FEAT-078] Neural Trace: Persists black-box payloads for auditability."""
        try:
            # Absolute path hardening for trace logs
            lab_root = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )
            log_dir = os.path.join(lab_root, "logs")
            os.makedirs(log_dir, exist_ok=True)

            log_path = os.path.join(log_dir, f"trace_{self.name}.json")

            mode = "w" if phase == "send" else "a"
            entry = {
                "phase": phase,
                "timestamp": time.time(),
                "data": data,
                "metadata": metadata,
            }
            if url:
                entry["url"] = url

            with open(log_path, mode) as f:
                f.write(json.dumps(entry, indent=2) + "\n")
        except Exception:
            pass

    async def call_remote_tool(self, target_node: str, tool_name: str, parameters: dict) -> str:
        """
        [FEAT-196] Cross-Hemispheric Calling: Allows a node to request a tool
        from another resident node via the Hub's WebSocket relay.
        """
        logging.info(f"[{self.name}] Requesting remote tool: {target_node}.{tool_name}")
        # Placeholder for future implementation: Currently Hub handles 
        # cross-node calls if specifically wired. For now, we return 
        # a structural prompt to the LLM to 'ask_brain' or 'ask_archive'
        return json.dumps({
            "error": "Cross-node direct tool calling via MCP is in DESIGN. Please use 'ask_brain' for delegation.",
            "suggestion": f"I cannot reach {target_node} directly. I should provide my derivation to the user."
        })

    def run(self):
        self.mcp.run()
