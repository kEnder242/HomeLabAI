import asyncio
import aiohttp
import json
import logging
import os
import sys
from mcp.server.fastmcp import FastMCP

# Global Paths
FIELD_NOTES_DATA = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
CHARACTERIZATION_FILE = os.path.join(
    FIELD_NOTES_DATA, "vram_characterization.json"
)


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
            except Exception: pass
        return {}

    async def probe_engine(self):
        """Standardized engine selection logic with Tier awareness."""
        env_engine = os.environ.get(f"{self.name.upper()}_ENGINE")
        env_tier_or_model = os.environ.get(f"{self.name.upper()}_MODEL")
        
        # Resolve Tier if applicable
        model_map = self.vram_config.get("model_map", {})
        
        def resolve(engine_type):
            if env_tier_or_model in model_map:
                return model_map[env_tier_or_model].get(engine_type.lower())
            return env_tier_or_model if env_tier_or_model else model_map.get("MEDIUM", {}).get(engine_type.lower())

        if env_engine:
            if env_engine.upper() == "VLLM":
                return "VLLM", self.vllm_url, resolve("VLLM")
            elif env_engine.upper() == "OLLAMA":
                return "OLLAMA", self.ollama_url, resolve("OLLAMA")

        async with aiohttp.ClientSession() as session:
            try:
                v_url = "http://127.0.0.1:8088/v1/models"
                async with session.get(v_url, timeout=1) as resp:
                    if resp.status == 200:
                        return "VLLM", self.vllm_url, resolve("VLLM")
            except Exception:
                pass
            try:
                o_url = "http://127.0.0.1:11434/api/tags"
                async with session.get(o_url, timeout=1) as resp:
                    if resp.status == 200:
                        return "OLLAMA", self.ollama_url, resolve("OLLAMA")
            except Exception:
                pass
        return "NONE", None, None

    def unify_prompt(self, query, context="", memory=""):
        """Implements the Unified User Pattern for vLLM compatibility."""
        # Get list of physical tools from the MCP instance
        tools = [t.name for t in self.mcp._tool_manager.list_tools()]
        tool_list = ", ".join(tools)

        prompt = self.system_prompt
        if context:
            prompt += f"\n[RECENT CONTEXT]:\n{context}\n"

        unified = (
            f"[SYSTEM]: {prompt}\n\n"
            f"AVAILABLE TOOLS: {tool_list}, ask_brain, reply_to_user\n"
            "RULE: You MUST ONLY use one of the tools listed above.\n\n"
            f"MEMORY:\n{memory}\n\n"
            f"QUERY:\n{query}\n\n"
            "DECISION (JSON):"
        )
        return unified

    async def generate_response(self, query, context="", memory=""):
        """Standardized reasoning entry point with lobotomy awareness."""
        engine, url, model = await self.probe_engine()

        if self.lobotomy_active:
            model = self.fallback_model
            engine = "OLLAMA"
            url = self.ollama_url

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
                        "max_tokens": 512, "temperature": 0.2
                    }
                    async with session.post(url, json=payload, timeout=30) as resp:
                        data = await resp.json()
                        if "choices" in data:
                            return data["choices"][0]["message"]["content"]
                        err_msg = f"SYSTEM_ERROR: vLLM error {resp.status}"
                        return json.dumps({
                            "tool": "reply_to_user",
                            "parameters": {"text": err_msg, "mood": "panic"}
                        })
                else:
                    payload = {
                        "model": model, "prompt": unified,
                        "stream": False, "format": "json",
                        "options": {"num_predict": 512, "temperature": 0.2}
                    }
                    async with session.post(url, json=payload, timeout=30) as resp:
                        data = await resp.json()
                        return data.get("response", "")
        except Exception as e:
            return json.dumps({
                "tool": "reply_to_user",
                "parameters": {"text": f"Connection Failed: {e}", "mood": "panic"}
            })

    def run(self):
        self.mcp.run()
