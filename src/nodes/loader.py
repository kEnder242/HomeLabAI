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

        # Default Models
        self.vllm_model = "/home/jallred/AcmeLab/models/mistral-7b-awq"
        self.ollama_model = "llama3.1:8b"
        self.fallback_model = "tinyllama"

    async def probe_engine(self):
        """Standardized engine selection logic."""
        env_engine = os.environ.get(f"{self.name.upper()}_ENGINE")
        if env_engine:
            if env_engine.upper() == "VLLM":
                return "VLLM", self.vllm_url, self.vllm_model
            elif env_engine.upper() == "OLLAMA":
                return "OLLAMA", self.ollama_url, self.ollama_model

        async with aiohttp.ClientSession() as session:
            try:
                v_url = "http://127.0.0.1:8088/v1/models"
                async with session.get(v_url, timeout=1) as resp:
                    if resp.status == 200:
                        return "VLLM", self.vllm_url, self.vllm_model
            except Exception:
                pass
            try:
                o_url = "http://127.0.0.1:11434/api/tags"
                async with session.get(o_url, timeout=1) as resp:
                    if resp.status == 200:
                        return "OLLAMA", self.ollama_url, self.ollama_model
            except Exception:
                pass
        return "NONE", None, None

    def unify_prompt(self, query, context="", memory=""):
        """Implements the Unified User Pattern for vLLM compatibility."""
        prompt = self.system_prompt
        if context:
            prompt += f"\n[RECENT CONTEXT]:\n{context}\n"

        unified = (
            f"[SYSTEM]: {prompt}\n\n"
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
