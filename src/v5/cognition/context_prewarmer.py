#!/usr/bin/env python3
"""
context_prewarmer.py — [FEAT-642 / FEAT-643] Canonical AST & Neural Semantic Pre-Warmer.

Canonical engine for:
1. Dynamic Python/JS AST structural outline extraction (<10ms, <350 tokens).
2. Parallel Neural Map-Reduce reduction on M5 Air via Headroom port 8002.
3. Centralized CLaRa context cache management (/tmp/clara_context_cache.json).
"""

import ast
import concurrent.futures
import json
import os
import sys
import time
import urllib.request
import urllib.error

CONTEXT_CACHE_DIR = os.environ.get("JIT_CACHE_DIR", os.path.expanduser("~/Dev_Lab/.jit_cache"))
CONTEXT_CACHE_PATH = os.path.join(CONTEXT_CACHE_DIR, "clara_context_cache.json")
SUB_INFERENCE_LEDGER_PATH = os.path.join(CONTEXT_CACHE_DIR, "sub_inference_ledger.jsonl")
M5_AIR_HEADROOM_URL = "http://192.168.1.46:8002/v1/chat/completions"
M5_AIR_MODEL = "TokenAI-zer--Ternary-Bonsai-2-27B-MLX-oQ2-mtp"


def record_sub_inference_receipt(engine: str, file_path: str, prompt_tokens: int, completion_tokens: int) -> None:
    """[Story 100.4 / FEAT-648] Record sub-inference compute receipt to .jit_cache/sub_inference_ledger.jsonl."""
    try:
        os.makedirs(CONTEXT_CACHE_DIR, exist_ok=True)
        record = {
            "timestamp": time.time(),
            "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "engine": engine,
            "target_file": file_path,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        }
        with open(SUB_INFERENCE_LEDGER_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


def extract_ast_outline(file_path: str, content: str) -> str:
    """[FEAT-642] Extract lightweight AST blueprint without function bodies (<350 tokens)."""
    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".py":
        try:
            tree = ast.parse(content)
            lines = []
            doc = ast.get_docstring(tree)
            if doc:
                lines.append(f"# Module: {doc.strip().splitlines()[0]}")
            for node in tree.body:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    dec = [f"@{ast.unparse(d)}" for d in node.decorator_list]
                    dec_str = (" ".join(dec) + " ") if dec else ""
                    args_str = ast.unparse(node.args)
                    ret_str = f" -> {ast.unparse(node.returns)}" if node.returns else ""
                    lines.append(f"{dec_str}def {node.name}({args_str}){ret_str}: ... (L{node.lineno}-L{node.end_lineno})")
                elif isinstance(node, ast.ClassDef):
                    bases = ", ".join(ast.unparse(b) for b in node.bases)
                    base_str = f"({bases})" if bases else ""
                    lines.append(f"\nclass {node.name}{base_str}: (L{node.lineno}-L{node.end_lineno})")
                    for sub in node.body:
                        if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            sub_args = ast.unparse(sub.args)
                            sub_ret = f" -> {ast.unparse(sub.returns)}" if sub.returns else ""
                            lines.append(f"    def {sub.name}({sub_args}){sub_ret}: ... (L{sub.lineno}-L{sub.end_lineno})")
            return "\n".join(lines) if lines else content[:800]
        except Exception as e:
            return f"# AST Parse Fallback ({e}):\n" + "\n".join(content.splitlines()[:50])

    elif ext in (".js", ".ts"):
        lines = []
        for idx, line in enumerate(content.splitlines(), start=1):
            s = line.strip()
            if s.startswith(("function ", "async function ", "class ", "export class ", "export function ", "const ", "let ")) and ("(" in s or "class" in s):
                lines.append(f"{s[:100]} (L{idx})")
        return "\n".join(lines[:60]) if lines else "\n".join(content.splitlines()[:40])

    elif ext in (".md", ".markdown"):
        lines = []
        for idx, line in enumerate(content.splitlines(), start=1):
            if line.strip().startswith(("#", "##", "###", "####", "[FEAT-", "[BKM-", "[WIS-", "[INS-")):
                lines.append(f"{line.strip()[:100]} (L{idx})")
        return "\n".join(lines[:80]) if lines else "\n".join(content.splitlines()[:50])

    else:
        return "\n".join(content.splitlines()[:60])


def reduce_file_via_m5_air(file_path: str, raw_lines: list[str], max_chars: int = 6000, timeout: float = 45.0) -> str | None:
    """[FEAT-643] Query M5 Air via Headroom port 8002 for neural semantic code reduction."""
    try:
        full_text = "".join(raw_lines)
        snippet = full_text[:max_chars]
        payload = {
            "model": M5_AIR_MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a code reduction engine. Summarize the key classes, state constants, lock paths, lifecycle hooks, and architectural mechanisms of this file in under 120 words."
                },
                {
                    "role": "user",
                    "content": f"File: {file_path} ({len(raw_lines)} lines)\n{snippet}"
                }
            ],
            "max_tokens": 160,
            "temperature": 0.1
        }
        req = urllib.request.Request(
            M5_AIR_HEADROOM_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.load(resp)
            content = res["choices"][0]["message"]["content"].strip()

            # [Story 100.4] Sub-inference audit receipt
            usage = res.get("usage", {})
            p_tok = usage.get("prompt_tokens") or max(1, len(snippet) // 4)
            c_tok = usage.get("completion_tokens") or max(1, len(content) // 4)
            record_sub_inference_receipt("m5_air", file_path, p_tok, c_tok)
            return content
    except Exception:
        return None


def get_cached_semantic_summary(file_path: str) -> str | None:
    """Read cached semantic summary from persistent .jit_cache/clara_context_cache.json with mtime validation."""
    if not os.path.exists(CONTEXT_CACHE_PATH):
        return None
    try:
        with open(CONTEXT_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        clean_path = file_path.strip().lstrip("./")
        base = os.path.basename(clean_path)

        dev_lab = os.path.expanduser("~/Dev_Lab")
        full_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(dev_lab, file_path))
        disk_mtime = os.path.getmtime(full_path) if os.path.exists(full_path) else None

        for k, v in cache.items():
            if k.strip().lstrip("./") == clean_path or os.path.basename(k) == base or clean_path in k:
                if isinstance(v, dict):
                    cached_mtime = v.get("mtime")
                    if disk_mtime is not None and cached_mtime is not None and disk_mtime > cached_mtime:
                        return None
                    return v.get("summary", "")
                elif isinstance(v, str):
                    return v
    except Exception:
        pass
    return None


def write_cached_semantic_summary(file_path: str, summary: str, mtime: float | None = None) -> None:
    """Store semantic summary in persistent .jit_cache/clara_context_cache.json with mtime."""
    try:
        os.makedirs(CONTEXT_CACHE_DIR, exist_ok=True)
        cache = {}
        if os.path.exists(CONTEXT_CACHE_PATH):
            with open(CONTEXT_CACHE_PATH, "r", encoding="utf-8") as f:
                cache = json.load(f)
        clean_path = file_path.strip().lstrip("./")
        base = os.path.basename(clean_path)

        if mtime is None:
            dev_lab = os.path.expanduser("~/Dev_Lab")
            full_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(dev_lab, file_path))
            mtime = os.path.getmtime(full_path) if os.path.exists(full_path) else time.time()

        entry = {
            "summary": summary,
            "mtime": mtime,
            "cached_at": time.time(),
        }
        cache[clean_path] = entry
        cache[base] = entry
        tmp_path = CONTEXT_CACHE_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        os.replace(tmp_path, CONTEXT_CACHE_PATH)
    except Exception:
        pass


def evict_cached_summary(file_path: str) -> bool:
    """[Story 100.3 / FEAT-648] File-scoped cache invalidation when a target file is modified."""
    if not os.path.exists(CONTEXT_CACHE_PATH):
        return False
    try:
        with open(CONTEXT_CACHE_PATH, "r", encoding="utf-8") as f:
            cache = json.load(f)
        clean_path = file_path.strip().lstrip("./")
        base = os.path.basename(clean_path)
        popped = False
        for k in list(cache.keys()):
            if k.strip().lstrip("./") == clean_path or os.path.basename(k) == base or clean_path in k:
                cache.pop(k, None)
                popped = True
        if popped:
            tmp_path = CONTEXT_CACHE_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(cache, f, indent=2)
            os.replace(tmp_path, CONTEXT_CACHE_PATH)
        return popped
    except Exception:
        return False


def reduce_file(file_path: str, force: bool = False, timeout: float = 45.0) -> str:
    """
    Generate or retrieve semantic digest for a file.
    If cached and not force, returns cached.
    Otherwise queries M5 Air via port 8002, falling back to deterministic anchor extraction.
    """
    if not force:
        cached = get_cached_semantic_summary(file_path)
        if cached:
            return cached

    # Resolve absolute path if relative
    dev_lab = os.path.expanduser("~/Dev_Lab")
    full_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(dev_lab, file_path))

    if not os.path.exists(full_path):
        return f"File not found: {file_path}"

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
    except Exception as e:
        return f"Failed to read {file_path}: {e}"

    total_lines = len(raw_lines)

    # 1. Attempt M5 Air Neural Map-Reduce via Headroom port 8002
    neural_res = reduce_file_via_m5_air(file_path, raw_lines, timeout=timeout)
    if neural_res:
        summary = f"File: {file_path}\n[M5 AIR NEURAL REDUCTION]\n{neural_res}"
    else:
        # 2. Deterministic anchor fallback
        findings = []
        for idx, line in enumerate(raw_lines, start=1):
            s = line.strip()
            if not s or s.startswith("#") or s.startswith("//"):
                continue
            if any(k in s for k in ("lock", "LOCK", "state", "STATE", "status", "STATUS", "@app.", "@router.", "async def handle", "def check_", "def cleanup", "def reap")):
                if len(s) < 120:
                    findings.append(f"L{idx}: {s}")
            elif s.startswith(("class ", "export class ")) and ":" in s:
                findings.append(f"L{idx}: {s}")

        summary = f"File: {file_path} ({total_lines} lines)\n"
        if findings:
            summary += "Key Semantic Anchors:\n" + "\n".join(f"  * {f}" for f in findings[:12])
        else:
            summary += f"Target module ({total_lines} lines). Read via clara-dna_read(start_line, end_line) for exact logic."

    write_cached_semantic_summary(file_path, summary)
    return summary


def prewarm_files(file_paths: list[str], max_workers: int = 4, force: bool = False, timeout: float = 45.0) -> dict[str, str]:
    """
    [FEAT-643] Parallel Semantic Pre-Warm across M5 Air using ThreadPoolExecutor.
    Pre-warms all target files concurrently in ~5-8s total.
    """
    results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_file = {
            executor.submit(reduce_file, fp, force, timeout): fp
            for fp in file_paths
            if fp and fp.strip()
        }
        for future in concurrent.futures.as_completed(future_to_file):
            fp = future_to_file[future]
            try:
                summary = future.result()
                results[fp] = summary
            except Exception as e:
                results[fp] = f"Pre-warm failed: {e}"
    return results


WARM_SESSIONS_PATH = "/tmp/active_warm_sessions.json"


def register_warm_session(session_id: str, story_id: str, model: str = "unknown") -> None:
    """[FEAT-648] Persist warm OpenCode REST session ID for adjacent story resumption."""
    try:
        data = {}
        if os.path.exists(WARM_SESSIONS_PATH):
            with open(WARM_SESSIONS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
        data[session_id] = {
            "story_id": story_id,
            "model": model,
            "created_ts": time.time(),
            "last_used_ts": time.time(),
        }
        with open(WARM_SESSIONS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


def get_warm_session(story_id: str | None = None) -> str | None:
    """[FEAT-648] Retrieve a warm session ID, optionally filtered by story_id."""
    if not os.path.exists(WARM_SESSIONS_PATH):
        return None
    try:
        with open(WARM_SESSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not data:
            return None
        # If story_id specified, find matching session
        if story_id:
            for sid, info in data.items():
                if info.get("story_id") == story_id:
                    info["last_used_ts"] = time.time()
                    _save_warm_sessions(data)
                    return sid
        # Otherwise return most recently used session
        latest = max(data.items(), key=lambda kv: kv[1].get("last_used_ts", 0))
        latest[1]["last_used_ts"] = time.time()
        _save_warm_sessions(data)
        return latest[0]
    except Exception:
        return None


def _load_warm_sessions() -> dict:
    """Internal helper to read the warm session registry from disk."""
    if not os.path.exists(WARM_SESSIONS_PATH):
        return {}
    try:
        with open(WARM_SESSIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_warm_sessions(data: dict) -> None:
    """Internal helper to atomically write warm sessions."""
    try:
        tmp_path = WARM_SESSIONS_PATH + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, WARM_SESSIONS_PATH)
    except Exception:
        pass


def clear_warm_session(session_id: str) -> None:
    """[FEAT-648] Remove a warm session from the registry by session ID."""
    data = _load_warm_sessions()
    if session_id in data:
        del data[session_id]
        _save_warm_sessions(data)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 context_prewarmer.py <file1> [<file2> ...]")
        sys.exit(1)

    targets = sys.argv[1:]
    print(f"[*] Pre-warming {len(targets)} files via M5 Air (port 8002)...")
    res = prewarm_files(targets, force=True)
    for path, digest in res.items():
        print(f"\n--- {path} ---")
        print(digest)
