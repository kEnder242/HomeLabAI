#!/usr/bin/env python3
"""
Ollama Thinking Stripper & OpenAI Compatibility Proxy
Listens on 127.0.0.1:11435 and forwards requests to Node KENDER (192.168.1.26:11434).

Key responsibilities:
1. Strips reasoning/thought blocks so local models never enter reasoning loops or emit <think> tags.
2. Intercepts `/v1/chat/completions` (streaming SSE and non-streaming):
   - Strips `"reasoning"` field from delta/message objects.
   - Discards chunks that contain ONLY reasoning tokens, preventing empty token thrashing.
3. Forwards all other endpoints (/v1/models, /api/*) directly to Ollama.
"""

import json
import logging
import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import uvicorn

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("kender-proxy")

OLLAMA_UPSTREAM = "http://192.168.1.26:11434"

app = FastAPI(title="Kender Ollama Thought-Stripping Proxy")
client = httpx.AsyncClient(base_url=OLLAMA_UPSTREAM, timeout=httpx.Timeout(300.0, connect=10.0))


@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()


@app.post("/v1/chat/completions")
async def chat_completions(request: Request):
    body = await request.json()
    is_stream = body.get("stream", False)

    req_headers = dict(request.headers)
    req_headers.pop("host", None)
    req_headers.pop("content-length", None)

    if not is_stream:
        # Non-streaming request
        resp = await client.post("/v1/chat/completions", json=body, headers=req_headers)
        if resp.status_code != 200:
            return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))

        data = resp.json()
        for choice in data.get("choices", []):
            msg = choice.get("message", {})
            if "reasoning" in msg:
                del msg["reasoning"]
            if "reasoning_content" in msg:
                del msg["reasoning_content"]

        return Response(content=json.dumps(data), media_type="application/json")

    # Streaming request
    async def event_generator():
        async with client.stream("POST", "/v1/chat/completions", json=body, headers=req_headers) as upstream_resp:
            async for raw_line in upstream_resp.aiter_lines():
                if not raw_line:
                    yield b"\n"
                    continue

                if not raw_line.startswith("data: "):
                    yield (raw_line + "\n").encode("utf-8")
                    continue

                data_str = raw_line[6:].strip()
                if data_str == "[DONE]":
                    yield b"data: [DONE]\n\n"
                    continue

                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    has_content = False
                    for choice in choices:
                        delta = choice.get("delta", {})
                        if "reasoning" in delta:
                            del delta["reasoning"]
                        if "reasoning_content" in delta:
                            del delta["reasoning_content"]
                        if delta.get("content") or delta.get("tool_calls") or choice.get("finish_reason"):
                            has_content = True

                    # Only yield if there's real content/tool_calls/finish_reason
                    if has_content:
                        yield f"data: {json.dumps(chunk)}\n\n".encode("utf-8")
                except Exception:
                    yield (raw_line + "\n\n").encode("utf-8")

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "HEAD"])
async def passthrough(request: Request, path: str):
    method = request.method
    url = f"/{path}"
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    body = await request.body()

    resp = await client.request(method, url, headers=headers, content=body, params=request.query_params)
    return Response(content=resp.content, status_code=resp.status_code, headers=dict(resp.headers))


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=11435, log_level="warning")
