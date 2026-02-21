import aiohttp
import json
import os
import logging
import socket
import time
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

    def _resolve_best_model(self, available_models, engine_type):
        """[FEAT-080] Dynamic selection based on host capability."""
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
                    logging.warning(f"[{self.name}] Tier {env_mod} resolved to {m} but NOT FOUND on host.")
            
            # If it's a direct model name or resolved tier, verify it exists on host
            # [HARDENING] If we have available_models, we MUST match one.
            if available_models:
                if env_mod in available_models:
                    return env_mod
                else:
                    logging.warning(f"[{self.name}] Environment model {env_mod} NOT FOUND on host. Forcing fallback.")
            else:
                # No host tags? Trust ENV but expect failure
                return env_mod

        # 2. Preferred high-fidelity list for Brain
        if self.name == "brain":
            # [FEAT-083] Smaller Sovereign: Exclusively target fast 8B models for <10s load times.
            # Mixtral and other large models are explicitly banned to prevent cold-start delays.
            preferred = ["llama3.1:8b", "llama3:latest", "llama3:8b", "dolphin-llama3:8b"]
            for p in preferred:
                if p in available_models:
                    return p

        # 3. Fallback to model_map MEDIUM
        medium = self.vram_config.get("model_map", {}).get("MEDIUM", {}).get(engine_type.lower())
        if available_models and medium in available_models:
            return medium
            
        # 4. Ultimate Fallback: The first model the host has
        if available_models:
            logging.info(f"[{self.name}] No preferred models found. Selecting host default: {available_models[0]}")
            return available_models[0]
            
        return "llama3:latest"

    async def probe_engine(self):
        """Dynamic engine selection with Federated Failover."""
        async with aiohttp.ClientSession() as session:
            # 1. Check Primary Host (e.g., KENDER)
            p_host_cfg = self.infra.get("hosts", {}).get(self.primary_host, {})
            p_ip = resolve_ip(self.primary_host, p_host_cfg.get("ip_hint"))

            if p_ip and self.primary_host != "localhost":
                p_url = f"http://{p_ip}:{p_host_cfg.get('ollama_port', 11434)}"
                try:
                    async with session.get(f"{p_url}/api/tags", timeout=1.0) as r:
                        if r.status == 200:
                            data = await r.json()
                            available = [m.get("name") for m in data.get("models", [])]
                            model = self._resolve_best_model(available, "OLLAMA")
                            logging.info(f"[{self.name}] Routing to Primary: {p_ip} (Model: {model})")
                            return ("OLLAMA", f"{p_url}/api/chat", model)
                except Exception as e:
                    logging.warning(f"[{self.name}] Primary Host {p_ip} unreachable: {e}")

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
                        logging.info(f"[{self.name}] vLLM detected on localhost (Model: {model}).")
                        return ("VLLM", f"{v_url}/v1/chat/completions", model)
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
                        logging.info(f"[{self.name}] Ollama detected on localhost (Model: {model}).")
                        return ("OLLAMA", f"{o_url}/api/chat", model)
            except Exception:
                pass

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
        # Removing bracketed tags which may confuse some model templates on remote hosts
        full_prompt = f"System: {self.system_prompt}"
        if memory:
            full_prompt += f"\n\nMemory: {memory}"
        if context:
            full_prompt += f"\n\nRecent Context: {context}"
        
        return f"{full_prompt}\n\nUser: {query}\n\nAssistant:"

    async def generate_response(self, query, context="", memory=""):
        engine, url, model = await self.probe_engine()
        if engine == "NONE":
            return json.dumps({
                "tool": "reply_to_user",
                "parameters": {"text": "Egad! Weights offline!"},
            })

        async with aiohttp.ClientSession() as session:
            try:
                if engine == "VLLM":
                    unified = self.unify_prompt(query, context, memory)
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
                    # [STABILITY] Target-Aware Routing
                    # Remote hosts (Windows) often have older/different templates.
                    # Use raw /api/generate for remote, /api/chat for local.
                    is_remote = "127.0.0.1" not in url and "localhost" not in url
                    
                    if is_remote:
                        # Revert to Raw Prompt for Remote (Robustness)
                        gen_url = url.replace("/api/chat", "/api/generate")
                        unified = self.unify_prompt(query, context, memory)
                        payload = {
                            "model": model,
                            "prompt": unified,
                            "stream": False
                        }
                        
                        # [FEAT-078] Forensic Mirroring (Pre-Send)
                        self._mirror_forensics("send", payload, gen_url)

                        async with session.post(gen_url, json=payload, timeout=60) as r:
                            data = await r.json()
                            
                            # [FEAT-078] Forensic Mirroring (Post-Recv)
                            self._mirror_forensics("recv", data)

                            # [STABILITY] Explicit Error Detection
                            if data.get("error"):
                                logging.error(f"[{self.name}] Remote Ollama Error: {data.get('error')}")
                                return "INTERNAL_QUALITY_FALLBACK"

                            raw_resp = data.get("response", "").strip()
                            logging.info(f"[{self.name}] RAW OLLAMA RESP (Remote): '{raw_resp[:50]}...'")
                            
                            # [FEAT-077] Quality-Gate: If remote response is empty/dots, return sentinel for failover
                            if not raw_resp or raw_resp == "..." or raw_resp == ".":
                                logging.warning(f"[{self.name}] Remote host returned empty/dots. Triggering internal quality fallback.")
                                return "INTERNAL_QUALITY_FALLBACK"
                            return raw_resp
                    else:
                        # Use Chat API for Local (Alignment)
                        chat_url = url.replace("/api/generate", "/api/chat")
                        full_system = self.system_prompt
                        if memory:
                            full_system += f"\n\n[MEMORY]:\n{memory}"
                        if context:
                            full_system += f"\n\n[RECENT CONTEXT]:\n{context}"
                        
                        messages = [
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": query}
                        ]
                        payload = {
                            "model": model,
                            "messages": messages,
                            "stream": False
                        }

                        # [FEAT-078] Forensic Mirroring (Pre-Send)
                        self._mirror_forensics("send", payload, chat_url)

                        async with session.post(chat_url, json=payload, timeout=60) as r:
                            data = await r.json()

                            # [FEAT-078] Forensic Mirroring (Post-Recv)
                            self._mirror_forensics("recv", data)

                            if data.get("error"):
                                logging.error(f"[{self.name}] Local Ollama Error: {data.get('error')}")
                                return "INTERNAL_QUALITY_FALLBACK"

                            raw_resp = data.get("message", {}).get("content", "")
                            logging.info(f"[{self.name}] RAW OLLAMA RESP (Local): '{raw_resp[:50]}...'")
                            return raw_resp
            except Exception as e:
                return json.dumps({
                    "tool": "reply_to_user",
                    "parameters": {"text": f"Error: {e}"},
                })

    def _mirror_forensics(self, phase, data, url=None):
        """[FEAT-078] Internal helper to write black-box data to logs."""
        try:
            # Absolute path hardening for forensic logs
            lab_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_dir = os.path.join(lab_root, "logs")
            os.makedirs(log_dir, exist_ok=True)
            
            log_path = os.path.join(log_dir, f"forensic_{self.name}.json")
            
            mode = "w" if phase == "send" else "a"
            entry = {"phase": phase, "timestamp": time.time(), "data": data}
            if url:
                entry["url"] = url
            
            with open(log_path, mode) as f:
                f.write(json.dumps(entry, indent=2) + "\n")
        except Exception:
            pass

    def run(self):
        self.mcp.run()
