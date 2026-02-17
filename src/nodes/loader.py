import aiohttp
import json
import os
import logging
import socket
from mcp.server.fastmcp import FastMCP

# Global Paths
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
        self.system_prompt = system_prompt
        self.mcp = FastMCP(name)
        self.engine_mode = "AUTO"
        self.lobotomy_active = False

        # Load configs
        self.vram_config = self._load_json(CHARACTERIZATION_FILE)
        self.infra = self._load_json(INFRA_CONFIG)

        # Identity
        node_cfg = self.infra.get("nodes", {}).get(self.name, {})
        self.primary_host = node_cfg.get("primary", "localhost")
        self.lora_name = node_cfg.get("lora_name")

    def _load_json(self, path):
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def probe_engine(self):
        """Dynamic engine selection with Federated Failover."""
        model_map = self.vram_config.get("model_map", {})

        def resolve_model(engine_type):
            # Check for direct model override first
            env_mod = os.environ.get(f"{self.name.upper()}_MODEL")
            if env_mod:
                if env_mod in model_map:
                    m = model_map.get(env_mod, {}).get(engine_type.lower())
                else:
                    m = env_mod
                return m
            return model_map.get("MEDIUM", {}).get(engine_type.lower())

        # 0. High-Priority Invariants
        # If USE_BRAIN_VLLM is set in environment, force it.
        if os.environ.get("USE_BRAIN_VLLM") == "1":
            l_host_cfg = self.infra.get("hosts", {}).get("localhost", {})
            v_url = f"http://127.0.0.1:{l_host_cfg.get('vllm_port', 8088)}/v1/chat/completions"
            # Explicitly force the model name to unified-base for VLLM
            return ("VLLM", v_url, "unified-base")

        async with aiohttp.ClientSession() as session:
            # 1. Check Primary Host (e.g., KENDER)
            p_host_cfg = self.infra.get("hosts", {}).get(self.primary_host, {})
            p_ip = resolve_ip(self.primary_host, p_host_cfg.get("ip_hint"))

            if p_ip and self.primary_host != "localhost":
                p_url = f"http://{p_ip}:{p_host_cfg.get('ollama_port', 11434)}"
                try:
                    async with session.get(f"{p_url}/api/tags", timeout=1.0) as r:
                        if r.status == 200:
                            logging.info(f"[{self.name}] Routing to Primary: {p_ip}")
                            return (
                                "OLLAMA",
                                f"{p_url}/api/generate",
                                resolve_model("OLLAMA"),
                            )
                except Exception as e:
                    logging.warning(f"[{self.name}] Primary Host {p_ip} unreachable: {e}")

            # 2. Fallback to localhost (vLLM then Ollama)
            l_host_cfg = self.infra.get("hosts", {}).get("localhost", {})
            
            # Check vLLM
            v_url = f"http://127.0.0.1:{l_host_cfg.get('vllm_port', 8088)}"
            try:
                async with session.get(f"{v_url}/v1/models", timeout=2.0) as r:
                    if r.status == 200:
                        logging.info(f"[{self.name}] vLLM detected on localhost.")
                        return (
                            "VLLM",
                            f"{v_url}/v1/chat/completions",
                            resolve_model("VLLM"),
                        )
                    else:
                        logging.warning(f"[{self.name}] vLLM probe returned {r.status}")
            except Exception as e:
                logging.debug(f"[{self.name}] vLLM probe failed: {e}")

            # Check Local Ollama
            o_url = f"http://127.0.0.1:{l_host_cfg.get('ollama_port', 11434)}"
            try:
                async with session.get(f"{o_url}/api/tags", timeout=1.0) as r:
                    if r.status == 200:
                        logging.info(f"[{self.name}] Ollama detected on localhost.")
                        return (
                            "OLLAMA",
                            f"{o_url}/api/generate",
                            resolve_model("OLLAMA"),
                        )
            except Exception as e:
                logging.debug(f"[{self.name}] Ollama probe failed: {e}")

        return "NONE", None, None

    def get_tool_schemas(self):
        """Generates OpenAI-compatible tool schemas."""
        tools = []
        for tool_obj in self.mcp._tool_manager.list_tools():
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_obj.name,
                    "description": tool_obj.description or "",
                    "parameters": tool_obj.parameters,
                },
            })

        tools.extend([
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
                    "name": "reply_to_user",
                    "description": "Provide natural language response.",
                    "parameters": {
                        "type": "object",
                        "properties": {"text": {"type": "string"}},
                        "required": ["text"],
                    },
                },
            },
        ])
        return tools

    def unify_prompt(self, query, context="", memory=""):
        prompt = self.system_prompt
        if context:
            prompt += f"\n[RECENT CONTEXT]:\n{context}\n"
        return f"[SYSTEM]: {prompt}\n\nMEMORY:\n{memory}\n\nQUERY:\n{query}"

    async def generate_response(self, query, context="", memory=""):
        engine, url, model = await self.probe_engine()
        if engine == "NONE":
            return json.dumps({
                "tool": "reply_to_user",
                "parameters": {"text": "Egad! Weights offline!"},
            })

        unified = self.unify_prompt(query, context, memory)
        async with aiohttp.ClientSession() as session:
            try:
                if engine == "VLLM":
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": unified}],
                        "tools": self.get_tool_schemas(),
                        "tool_choice": "auto",
                        "max_tokens": 512,
                    }
                    async with session.post(url, json=payload, timeout=60) as r:
                        data = await r.json()
                        if "choices" not in data:
                            logging.error(f"[{self.name}] vLLM Error: {data}")
                            return json.dumps({
                                "tool": "reply_to_user",
                                "parameters": {"text": f"vLLM Error: {data}"}
                            })
                        msg = data["choices"][0]["message"]
                        if msg.get("tool_calls"):
                            tc = msg["tool_calls"][0]["function"]
                            return json.dumps({
                                "tool": tc["name"],
                                "parameters": json.loads(tc["arguments"]),
                            })
                        return msg["content"]
                else:
                    payload = {
                        "model": model, "prompt": unified,
                        "stream": False, "format": "json"
                    }
                    async with session.post(url, json=payload, timeout=60) as r:
                        data = await r.json()
                        return data.get("response", "")
            except Exception as e:
                return json.dumps({
                    "tool": "reply_to_user",
                    "parameters": {"text": f"Error: {e}"},
                })

    def run(self):
        self.mcp.run()
