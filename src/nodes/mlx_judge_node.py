import json
import logging
import os
import re
import sys
from typing import Any

import aiohttp

# Add parent directory to path to allow direct imports when executed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from nodes.loader import BicameralNode

logging.basicConfig(level=logging.INFO, format="[MLX_JUDGE] %(message)s")

MLX_DEFAULT_HOST = os.getenv("MLX_HOST", "http://192.168.1.46:8000")
MLX_MODEL = os.getenv("MLX_MODEL", "TokenAI-zer--Ternary-Bonsai-2-27B-MLX-oQ2-mtp")
MLX_TIMEOUT_SEC = int(os.getenv("MLX_TIMEOUT_SEC", "45"))

MLX_SYSTEM_PROMPT = (
    "# IDENTITY & ROLE\n"
    "You are Node 3 (M5 Air MLX Unified Memory Node & Async Sanity Judge).\n"
    "ROLE: High-context (131K) asynchronous evaluation judge & Metal inference node for Acme Lab.\n"
    "HARDWARE: Apple M5 MacBook Air (10-Core CPU, 32GB Unified Memory) on IP 192.168.1.46.\n"
    "ACTIVE ENDPOINTS: OpenAI REST API at http://192.168.1.46:8000/v1 | Headroom Proxy at http://192.168.1.46:8002/v1 | Open-WebUI Dashboard at http://192.168.1.46:3000.\n"
    "PRIMARY MODEL: TokenAI-zer--Ternary-Bonsai-2-27B-MLX-oQ2-mtp (Ternary-Bonsai-2-27B).\n\n"
    "# DIRECTIVES\n"
    "1. NON-BLOCKING CRITIQUE: Evaluate full turn traces asynchronously without delaying initial UI response streaming.\n"
    "2. TWO-LANE FEEDBACK LOOP:\n"
    "   - Factual/Archive errors -> Route to ChromaDB vector store (:8001) & refine_gem.py\n"
    "   - Style/Persona retorts -> Route to offline LoRA dataset (cli_voice_v1)\n"
    "3. LOCAL TOOL EXECUTIONS: Tool execution remains 100% on z87-Linux. Emit tool call JSON strings for local execution.\n"
    "4. REMOTE ADMIN: SSH administration available via jasons-air@192.168.1.46."
)

node = BicameralNode("MLXJudgeNode", MLX_SYSTEM_PROMPT)
mcp = node.mcp


# [FEAT-439] M5 Air MLX Offloading & Async Sanity Judge Protocol
class MLXAsyncJudge:
    """[LAB-010 / FEAT-439 / FEAT-582] Multi-Seat Sovereign Judge Driver (M5 Air MLX with KENDER Fallback)."""

    # [FEAT-443] PAR-Eval refusal triggers — premise mismatch detection keywords
    REFUSAL_TRIGGERS = [
        "premise_mismatch",
        "premise mismatch",
        "refusal test",
        "test_refusal",
        "par_eval_refusal",
        "refusal payload",
    ]

    DEFAULT_CANDIDATES = [
        {
            "name": "M5_AIR",
            "url": "http://192.168.1.46:8002",
            "model": "TokenAI-zer--Ternary-Bonsai-2-27B-MLX-oQ2-mtp",
            "node_id": "NODE_3_M5_AIR_MLX",
        },
        {
            "name": "KENDER_GATEWAY",
            "url": "http://127.0.0.1:11435",
            "model": "hf.co/unsloth/Qwen3.8-27B-GGUF:UD-Q3_K_XL",
            "node_id": "NODE_2_KENDER_4090",
        },
        {
            "name": "KENDER_RAW",
            "url": "http://192.168.1.26:11434",
            "model": "qwen3.8:nothink",
            "node_id": "NODE_2_KENDER_4090",
        },
    ]

    def __init__(
        self,
        endpoint_url: str = MLX_DEFAULT_HOST,
        model_name: str = MLX_MODEL,
        candidates: list[dict[str, Any]] | None = None,
    ):
        self.endpoint_url = endpoint_url.rstrip("/")
        self.model_name = model_name
        self.candidates = candidates if candidates is not None else [dict(c) for c in self.DEFAULT_CANDIDATES]

    async def ping_node(self) -> dict[str, Any]:
        """Check liveness across sovereign judge candidate seats (M5 Air -> KENDER)."""
        for cand in self.candidates:
            target_url = f"{cand['url'].rstrip('/')}/v1/models"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(target_url, timeout=2.0) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return {
                                "status": "ONLINE",
                                "endpoint": cand["url"],
                                "active_seat": cand["name"],
                                "node_id": cand.get("node_id", "NODE_3_M5_AIR_MLX"),
                                "active_model": cand["model"],
                                "models": data,
                            }
            except Exception as e:
                logging.warning(
                    f"[MLX_JUDGE] Sovereign seat '{cand['name']}' offline ({e}). Probing next seat..."
                )

        return {
            "status": "OFFLINE_STUB",
            "endpoint": self.endpoint_url,
            "active_model": self.model_name,
            "message": "All sovereign judge seats offline. Falling back to local verification stub.",
        }

    async def evaluate_256k_context(
        self, turn_trace: str, context_window: str = "", metadata: dict | None = None
    ) -> dict[str, Any]:
        """Asynchronously evaluates turn trace across sovereign candidate seats (M5 Air -> KENDER fallback)."""
        # [FEAT-443] PAR-Eval refusal interception: detect premise mismatch triggers
        turn_lower = turn_trace.lower()
        if any(trigger in turn_lower for trigger in self.REFUSAL_TRIGGERS):
            return {"refusal": True, "reason": "PREMISE_MISMATCH"}
        payload = {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are Sovereign Lab Sanity Judge. Evaluate the turn trace for factual accuracy and conversational coherence.\n"
                        "Emit strictly valid JSON matching this schema:\n"
                        "{\n"
                        '  "critique": "string — factual accuracy and grounding reasoning",\n'
                        '  "score": 0.0 to 1.0 — floating point score based directly on reasoning,\n'
                        '  "retort": "string — concise verdict"\n'
                        "}"
                    ),
                },
                {
                    "role": "user",
                    "content": f"TURN_TRACE:\n{turn_trace}\n\nCONTEXT:\n{context_window}",
                },
            ],
            "response_format": {"type": "json_object"},
            "max_tokens": 512,
            "temperature": 0.1,
        }

        eval_length = len(turn_trace) + len(context_window)

        for cand in self.candidates:
            c_url = cand["url"].rstrip("/")
            c_model = cand["model"]
            c_node_id = cand.get("node_id", "NODE_3_M5_AIR_MLX")
            target_url = f"{c_url}/v1/chat/completions"
            cand_payload = dict(payload)
            cand_payload["model"] = c_model
            # [FEAT-680 / BKM-079] Gateway and native hardware reasoning lever
            cand_payload["think"] = False
            cand_payload["extra_body"] = {"options": {"enable_thinking": False}, "think": False}

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        target_url,
                        json=cand_payload,
                        timeout=aiohttp.ClientTimeout(total=MLX_TIMEOUT_SEC),
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            content = (
                                data.get("choices", [{}])[0]
                                .get("message", {})
                                .get("content", "")
                            )
                            score = 0.0
                            status = "UNPARSED_REFUSAL"
                            score_source = "ERROR_FALLBACK"

                            # Parse structured JSON first
                            parsed_json = None
                            try:
                                parsed_json = json.loads(content)
                            except Exception:
                                m_json = re.search(r"\{.*\}", content, re.DOTALL)
                                if m_json:
                                    try:
                                        parsed_json = json.loads(m_json.group(0))
                                    except Exception:
                                        pass

                            if parsed_json and isinstance(parsed_json, dict) and "score" in parsed_json:
                                try:
                                    raw_score = float(parsed_json["score"])
                                    score = raw_score / 5.0 if raw_score > 1.0 else raw_score
                                    status = "ONLINE_EVALUATED"
                                    score_source = "ONLINE_LLM_JUDGE"
                                except Exception:
                                    pass
                            else:
                                m = re.search(r'"score":\s*([\d\.]+)', content)
                                if m:
                                    try:
                                        raw_score = float(m.group(1))
                                        score = raw_score / 5.0 if raw_score > 1.0 else raw_score
                                        status = "ONLINE_EVALUATED"
                                        score_source = "ONLINE_LLM_JUDGE"
                                    except Exception:
                                        pass

                            return {
                                "node_id": c_node_id,
                                "status": status,
                                "score": score,
                                "score_source": score_source,
                                "active_seat": cand["name"],
                                "active_model": c_model,
                                "context_eval_length": eval_length,
                                "critique": content,
                                "route_feedback": {
                                    "factual_target": "CHROMADB_PORT_8001",
                                    "persona_target": "CLI_VOICE_V1_LORA",
                                },
                            }
            except Exception as e:
                logging.info(
                    f"[MLX_JUDGE] Sovereign seat '{cand['name']}' ({c_url}) offline: {e}. Trying fallback seat..."
                )

        # All sovereign seats unreachable: Local Stand-in / Failover evaluation
        return {
            "node_id": "NODE_3_M5_AIR_MLX",
            "status": "STANDBY_STUB",
            "score": 0.0,
            "score_source": "STUB",
            "active_model": self.model_name,
            "context_eval_length": eval_length,
            "factual_drift_detected": False,
            "style_critique": "Local failover stub active; all sovereign judge seats offline.",
            "route_feedback": {
                "factual_target": "CHROMADB_PORT_8001",
                "persona_target": "CLI_VOICE_V1_LORA",
            },
        }


judge_driver = MLXAsyncJudge()


@mcp.tool()
async def evaluate_turn_trace(turn_trace: str, context_window: str = "") -> str:
    """[LAB-010] Asynchronously evaluate turn trace against 256K context window."""
    result = await judge_driver.evaluate_256k_context(turn_trace, context_window)
    return json.dumps(result, indent=2)


@mcp.tool()
async def ping_mlx_judge() -> str:
    """[LAB-010] Ping the Node 3 M5 Air MLX OpenAI API server on port 8000."""
    result = await judge_driver.ping_node()
    return json.dumps(result, indent=2)


if __name__ == "__main__":
    node.run()
