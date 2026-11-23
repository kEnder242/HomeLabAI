# Copyright 2025-2026 Jason Allred
# SPDX-License-Identifier: Apache-2.0
"""
[Story 113.86] Heterogeneous Silicon Endpoint Polymorphism
Provides a unified abstract interface for heterogeneous silicon backends:
- OpenAI-compatible (M5 Air oMLX :8000, Local vLLM :8088, Kender Gateway :11435)
- Ollama-native (Kender Raw :11434)
"""
from abc import ABC, abstractmethod
import asyncio
import logging
from typing import Any, Optional
import aiohttp

logger = logging.getLogger("SILICON_ENDPOINTS")


class SiliconEndpoint(ABC):
    """Abstract interface for heterogeneous model inference engines."""

    def __init__(self, host: str, port: int, model: str, name: str = "endpoint"):
        self.host = host
        self.port = port
        self.model = model
        self.name = name

    @abstractmethod
    def get_health_url(self) -> str:
        """Returns the discovery / health probe URL."""
        pass

    @abstractmethod
    def get_completions_url(self) -> str:
        """Returns the chat completions API URL."""
        pass

    @abstractmethod
    def parse_models_response(self, data: dict[str, Any]) -> list[str]:
        """Extracts available model IDs from the discovery response."""
        pass

    async def check_health(self, timeout_sec: float = 2.0) -> bool:
        """TCP connect probe followed by HTTP discovery check."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=timeout_sec
            )
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
        except Exception as e:
            logger.debug(f"[{self.name}] TCP ping to {self.host}:{self.port} failed: {e}")
            return False

        url = self.get_health_url()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=timeout_sec)
                ) as resp:
                    if resp.status != 200:
                        return False
                    data = await resp.json()
                    models = self.parse_models_response(data)
                    return len(models) > 0
        except Exception as e:
            logger.debug(f"[{self.name}] Health probe to {url} failed: {e}")
            return False


class OpenAISiliconEndpoint(SiliconEndpoint):
    """OpenAI-compatible driver (used by M5 Air oMLX :8000, Local vLLM :8088)."""

    def get_health_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1/models"

    def get_completions_url(self) -> str:
        return f"http://{self.host}:{self.port}/v1/chat/completions"

    def parse_models_response(self, data: dict[str, Any]) -> list[str]:
        # OpenAI returns {"data": [{"id": "model_name"}, ...]}
        items = data.get("data", [])
        models = [item.get("id") for item in items if isinstance(item, dict) and item.get("id")]
        # Fallback if top-level list
        if not models and isinstance(items, list):
            for it in items:
                if isinstance(it, str):
                    models.append(it)
        return models


class OllamaSiliconEndpoint(SiliconEndpoint):
    """Ollama-native driver (used by Kender :11434)."""

    def get_health_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/tags"

    def get_completions_url(self) -> str:
        return f"http://{self.host}:{self.port}/api/chat"

    def parse_models_response(self, data: dict[str, Any]) -> list[str]:
        # Ollama returns {"models": [{"name": "model_name"}, ...]}
        items = data.get("models", [])
        return [item.get("name") for item in items if isinstance(item, dict) and item.get("name")]


def create_endpoint(
    host: str, port: int, model: str, protocol: str = "OPENAI", name: str = "endpoint"
) -> SiliconEndpoint:
    """Factory helper to build the appropriate SiliconEndpoint."""
    proto = str(protocol).upper()
    if proto in ("OLLAMA", "OLLAMA_RAW"):
        return OllamaSiliconEndpoint(host, port, model, name=name)
    return OpenAISiliconEndpoint(host, port, model, name=name)
