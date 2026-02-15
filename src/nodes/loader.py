import aiohttp
import json
import os
import re
import logging
from mcp.server.fastmcp import FastMCP

# Global Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
CHARACTERIZATION_FILE = os.path.join(
    FIELD_NOTES_DATA, "vram_characterization.json"
)

# 4090 Awareness: Define remote Windows endpoint
WINDOWS_OLLAMA_URL = "http://192.168.1.15:11434/api/generate"
WINDOWS_TAGS_URL = "http://192.168.1.15:11434/api/tags"

class BicameralNode:
    def __init__(self, name, system_prompt,
                 vllm_url="http://127.0.0.1:8088/v1/chat/completions",
                 ollama_url="http://127.0.0.1:11434/api/generate"):
        self.name = name
        self.system_prompt = system_prompt
        self.vllm_url = vllm_url
        self.ollama_url = ollama_url
        self.mcp = FastMCP(name)
        self.engine_mode = "AUTO"
        self.lobotomy_active = False
        self.vram_config = self._load_vram_config()

    def _load_vram_config(self):
        if os.path.exists(CHARACTERIZATION_FILE):
            try:
                with open(CHARACTERIZATION_FILE, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    async def probe_engine(self):
        """Standardized engine selection logic including 4090 Awareness."""
        env_engine = os.environ.get(f"{self.name.upper()}_ENGINE")
        env_tier_or_mod = os.environ.get(f"{self.name.upper()}_MODEL")
        model_map = self.vram_config.get("model_map", {})

        def resolve(engine_type):
            if env_tier_or_mod in model_map:
                return model_map[env_tier_or_mod].get(engine_type.lower())
            return env_tier_or_mod if env_tier_or_mod else model_map.get(
                "MEDIUM", {}
            ).get(engine_type.lower())

        if env_engine:
            if env_engine.upper() == "VLLM":
                return "VLLM", self.vllm_url, resolve("VLLM")
            elif env_engine.upper() == "OLLAMA":
                return "OLLAMA", self.ollama_url, resolve("OLLAMA")
            elif env_engine.upper() == "4090":
                return "4090", WINDOWS_OLLAMA_URL, resolve("OLLAMA")

        async with aiohttp.ClientSession() as session:
            # 1. Check vLLM (Linux 2080Ti)
            try:
                async with session.get(
                    "http://127.0.0.1:8088/v1/models", timeout=0.5
                ) as resp:
                    if resp.status == 200:
                        return "VLLM", self.vllm_url, resolve("VLLM")
            except Exception:
                pass
            # 2. Check 4090 (Windows Remote)
            try:
                async with session.get(WINDOWS_TAGS_URL, timeout=0.5) as resp:
                    if resp.status == 200:
                        logging.info(f"[{self.name}] 4090 Detected. Routing to Windows.")
                        return "4090", WINDOWS_OLLAMA_URL, resolve("OLLAMA")
            except Exception:
                pass
            # 3. Check Local Ollama (Linux Fallback)
            try:
                async with session.get(
                    "http://127.0.0.1:11434/api/tags", timeout=0.5
                ) as resp:
                    if resp.status == 200:
                        return "OLLAMA", self.ollama_url, resolve("OLLAMA")
            except Exception:
                pass
        return "NONE", None, None

    def get_tool_schemas(self):
        """Generates OpenAI-compatible tool schemas from FastMCP registry."""
        tools = []
        for tool_obj in self.mcp._tool_manager.list_tools():
            schema = tool_obj.parameters
            tools.append({
                "type": "function",
                "function": {
                    "name": tool_obj.name,
                    "description": tool_obj.description or "",
                    "parameters": schema
                }
            })

        tools.append({
            "type": "function",
            "function": {
                "name": "ask_brain",
                "description": "Delegate reasoning to the Left Hemisphere.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "The specific reasoning task."
                        }
                    },
                    "required": ["task"]
                }
            }
        })
        tools.append({
            "type": "function",
            "function": {
                "name": "reply_to_user",
                "description": "Provide natural language response.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The response content."
                        }
                    },
                    "required": ["text"]
                }
            }
        })
        return tools

    def unify_prompt(self, query, context="", memory=""):
        """Unified User Pattern for vLLM compatibility."""
        prompt = self.system_prompt
        if context:
            prompt += f"\n[RECENT CONTEXT]:\n{context}\n"
        return (
            f"[SYSTEM]: {prompt}\n\n"
            f"MEMORY:\n{memory}\n\n"
            f"QUERY:\n{query}"
        )

    async def generate_response(self, query, context="", memory=""):
        """Standardized reasoning entry point."""
        engine, url, model = await self.probe_engine()
        if self.lobotomy_active:
            engine, url = "OLLAMA", self.ollama_url
        if engine == "NONE":
            err = "Egad! I am disconnected from my weights!"
            return json.dumps({
                "tool": "reply_to_user",
                "parameters": {"text": err, "mood": "panic"}
            })

        unified = self.unify_prompt(query, context, memory)
        try:
            async with aiohttp.ClientSession() as session:
                if engine == "VLLM":
                    payload = {
                        "model": model,
                        "messages": [{"role": "user", "content": unified}],
                        "tools": self.get_tool_schemas(),
                        "tool_choice": "auto",
                        "max_tokens": 512, "temperature": 0.2
                    }
                    async with session.post(url, json=payload, timeout=30) as r:
                        data = await r.json()
                        if "choices" in data:
                            msg = data["choices"][0]["message"]
                            if msg.get("tool_calls"):
                                tc = msg["tool_calls"][0]["function"]
                                return json.dumps({
                                    "tool": tc["name"],
                                    "parameters": json.loads(tc["arguments"])
                                })
                            return msg["content"]
                        return json.dumps({
                            "tool": "reply_to_user",
                            "parameters": {"text": "vLLM Error", "mood": "panic"}
                        })
                else:
                    # Ollama (format: json)
                    payload = {
                        "model": model, "prompt": unified,
                        "stream": False, "format": "json",
                        "options": {"num_predict": 512, "temperature": 0.1}
                    }
                    async with session.post(url, json=payload, timeout=30) as r:
                        data = await r.json()
                        raw_out = data.get("response", "")
                        # Fallback parsing for Ollama non-native tool calling
                        try:
                            # Try to see if it's already JSON
                            json.loads(raw_out)
                            return raw_out
                        except Exception:
                            # If not, it might be raw text, let dispatcher handle it
                            return raw_out
        except Exception as e:
            return json.dumps({
                "tool": "reply_to_user",
                "parameters": {"text": f"Error: {e}", "mood": "panic"}
            })

    def run(self):
        self.mcp.run()
