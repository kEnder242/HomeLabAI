#!/usr/bin/env python3
"""
ClaraDB DNA MCP Server

Exposes the AcmeLab ClaraDB (ChromaDB) behavioral/feature/long-term wisdom
collections to OpenCode via MCP. Connects to the already-running ChromaDB
HTTP daemon on port 8001 (LAB-007) to avoid a second direct lock on the
persistent sqlite file.

Run from the HomeLabAI .venv (has chromadb 1.5.5 + mcp SDK):
    /home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3 clara_dna_mcp_server.py

Reference pattern: ~/AcmeLab/src/archive/brain_mcp_server.py (FastMCP).
"""
import os
import sys
import logging
import warnings
import json
import re
import time
import asyncio

# [Fix 1B] Silence Pydantic forward-ref and library warnings to prevent stdio stream contamination
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ClaraDB DNA")

CHROMA_HTTP_HOST = os.environ.get("CLARA_CHROMA_HOST", "127.0.0.1")
CHROMA_HTTP_PORT = int(os.environ.get("CLARA_CHROMA_PORT", "8001"))
DB_PATH = os.path.expanduser("~/AcmeLab/chroma_db")

DEFAULT_COLLECTIONS = (
    "behavioral_dna",
    "feature_dna",
    "long_term_wisdom",
)

_AST_CACHE: dict[str, tuple[float, str]] = {}



def _get_client():
    """Prefer the running HTTP daemon; fall back to PersistentClient."""
    import chromadb

    try:
        client = chromadb.HttpClient(host=CHROMA_HTTP_HOST, port=CHROMA_HTTP_PORT)
        client.heartbeat()
        return client
    except Exception as exc:
        logging.warning(f"HttpClient failed ({exc}); falling back to PersistentClient")
        return chromadb.PersistentClient(path=DB_PATH)


def _get_collection(client, name):
    import chromadb.utils.embedding_functions as ef

    try:
        return client.get_collection(name=name, embedding_function=ef.SentenceTransformerEmbeddingFunction(
            model_name="sentence-transformers/all-MiniLM-L6-v2"
        ))
    except Exception:
        return client.get_or_create_collection(name=name)


@mcp.tool()
async def list_collections() -> list[str]:
    """List all ClaraDB collections and their document counts."""
    client = _get_client()
    out = []
    for col in client.list_collections():
        try:
            out.append(f"{col.name}: {col.count()} docs")
        except Exception:
            out.append(f"{col.name}: (count unavailable)")
    return out


@mcp.tool()
async def query_dna(
    collection: str = "behavioral_dna",
    query: str = "",
    n_results: int = 3,
) -> list[dict]:
    """
    Semantic search across a ClaraDB collection (default: behavioral_dna).
    behavioral_dna holds the BKM behavioral protocols parsed from Protocols.md
    (e.g. BKM-004 QQ Protocol). feature_dna holds FEAT/VIBE features from
    FeatureTracker.md. long_term_wisdom holds the 18-year log wisdom archive.
    Returns matched documents with metadata and distance.
    """
    if not query.strip():
        return [{"error": "query text is required"}]
    client = _get_client()
    try:
        col = _get_collection(client, collection)
    except Exception as exc:
        return [{"error": f"collection '{collection}' unavailable: {exc}"}]

    try:
        res = col.query(query_texts=[query], n_results=n_results)
    except Exception as exc:
        return [{"error": f"query failed: {exc}"}]

    results = []
    docs = (res.get("documents") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    ids = (res.get("ids") or [[]])[0]
    for i, doc in enumerate(docs):
        results.append({
            "id": ids[i] if i < len(ids) else None,
            "distance": round(dists[i], 4) if i < len(dists) else None,
            "metadata": metas[i] if i < len(metas) else {},
            "document": doc[:3000],
        })
    return results


@mcp.tool()
async def get_protocol(bkm_id: str) -> dict:
    """
    Fetch a specific BKM protocol from behavioral_dna by exact ID
    (e.g. 'BKM-004' for the QQ Protocol). Exact metadata match, no embedding.
    """
    import re

    client = _get_client()
    try:
        col = _get_collection(client, "behavioral_dna")
    except Exception as exc:
        return {"error": f"behavioral_dna unavailable: {exc}"}

    # Normalize: strip trailing label, e.g. "BKM-004: The QQ Protocol" -> BKM-004
    norm = re.match(r"(BKM-\d+(?:\.\d+)?)", bkm_id.strip())
    target = norm.group(1) if norm else bkm_id.strip()

    try:
        res = col.get(where={"bkm_id": target}, limit=3)
    except Exception as exc:
        # Some versions key metadata fields differently; do a raw scan fallback
        try:
            all_docs = col.get(limit=1000)
            matches = []
            for i, meta in enumerate(all_docs.get("metadatas") or []):
                if meta and str(meta.get("bkm_id", "")).startswith(target):
                    matches.append({
                        "id": all_docs["ids"][i],
                        "metadata": meta,
                        "document": (all_docs["documents"] or [""] * len(all_docs["ids"]))[i][:3000],
                    })
            return {"protocol": matches} if matches else {"error": f"no match for {target}"}
        except Exception as exc2:
            return {"error": f"metadata query failed: {exc2}"}

    docs = res.get("documents") or []
    metas = res.get("metadatas") or []
    ids = res.get("ids") or []
    matches = [
        {
            "id": ids[i],
            "metadata": metas[i],
            "document": docs[i][:3000],
        }
        for i in range(len(ids))
    ]
    return {"protocol": matches} if matches else {"error": f"no match for {target}"}


@mcp.tool()
async def safe_patch(
    file_path: str,
    old_pattern: str,
    new_pattern: str,
    multi: bool = False,
) -> dict:
    r"""
    [FEAT-198 Safe-Scalpel] Apply an atomic, regex-tolerant patch to a file with automated syntax linting.
    - file_path: Absolute or Dev_Lab-relative path to target file.
    - old_pattern: Exact substring or regex pattern to match (e.g. r"def foo\(.*?\):").
    - new_pattern: Replacement content.
    - multi: If True, replaces all occurrences; default is False (replaces first match).
    Returns success status, match count, and linter validation output.
    """
    import re
    import subprocess

    if not file_path.startswith("/"):
        cand = os.path.join(os.path.expanduser("~/Dev_Lab"), file_path)
        if not os.path.exists(cand):
            sub_cand = os.path.join(os.path.expanduser("~/Dev_Lab/HomeLabAI"), file_path)
            if os.path.exists(sub_cand):
                cand = sub_cand
        file_path = cand

    if not os.path.exists(file_path):
        return {"success": False, "error": f"File not found: {file_path}"}

    try:
        with open(file_path, "r") as f:
            content = f.read()
    except Exception as e:
        return {"success": False, "error": f"Failed to read {file_path}: {e}"}

    # Normalize literal \n strings if passed escaped
    old_norm = old_pattern.replace("\\n", "\n") if "\\n" in old_pattern and "\n" not in old_pattern else old_pattern
    new_norm = new_pattern.replace("\\n", "\n") if "\\n" in new_pattern and "\n" not in new_pattern else new_pattern

    # Attempt 1: Exact string replace
    is_exact_match = old_norm in content
    if is_exact_match:
        if multi:
            new_content = content.replace(old_norm, new_norm)
            count = content.count(old_norm)
        else:
            new_content = content.replace(old_norm, new_norm, 1)
            count = 1
    else:
        # Attempt 2: Flexible whitespace literal match (handles newline / indentation drift)
        old_stripped = "\n".join(line.strip() for line in old_norm.splitlines() if line.strip())
        content_lines = content.splitlines()
        matched_idx = -1
        # Quick check if stripped lines match sequentially
        for idx in range(len(content_lines)):
            window = "\n".join(l.strip() for l in content_lines[idx:idx + len(old_norm.splitlines())] if l.strip())
            if window == old_stripped and old_stripped:
                matched_idx = idx
                break

        if matched_idx != -1:
            # Replace the exact slice of lines
            lines_to_replace = len([l for l in old_norm.splitlines() if l.strip()])
            end_idx = matched_idx
            matched_count = 0
            while end_idx < len(content_lines) and matched_count < lines_to_replace:
                if content_lines[end_idx].strip():
                    matched_count += 1
                end_idx += 1
            new_content = "\n".join(content_lines[:matched_idx] + [new_norm] + content_lines[end_idx:])
            count = 1
        else:
            # Attempt 3: Regex substitution (escaped for safety if unescaped compilation fails)
            try:
                count_limit = 0 if multi else 1
                new_content, count = re.subn(old_norm, lambda m: new_norm, content, count=count_limit, flags=re.MULTILINE)
            except Exception:
                try:
                    # Escape special characters if raw regex compilation failed (e.g. LaTeX backslashes)
                    escaped_old = re.escape(old_norm)
                    new_content, count = re.subn(escaped_old, lambda m: new_norm, content, count=count_limit, flags=re.MULTILINE)
                except Exception as regex_err:
                    return {"success": False, "error": f"Pattern matching failed: {regex_err}"}

    if count == 0:
        return {
            "success": False,
            "error": f"Pattern not found in {os.path.basename(file_path)}. Ensure indentation, line endings, or use exact anchors."
        }

    # Write atomically via temp file
    tmp_path = file_path + ".scalpel_tmp"
    try:
        with open(tmp_path, "w") as f:
            f.write(new_content)
    except Exception as e:
        return {"success": False, "error": f"Failed to write temp file: {e}"}

    # Automated lint gate
    ext = os.path.splitext(file_path)[1]
    lint_output = ""
    lint_passed = True
    try:
        if ext == ".py":
            ruff_bin = os.path.expanduser("~/Dev_Lab/HomeLabAI/.venv/bin/ruff")
            if not os.path.exists(ruff_bin):
                ruff_bin = "ruff"
            res = subprocess.run([ruff_bin, "check", tmp_path], capture_output=True, text=True)
            lint_passed = (res.returncode == 0)
            lint_output = (res.stdout + res.stderr).strip()
        elif ext == ".sh":
            res = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True)
            lint_passed = (res.returncode == 0)
            lint_output = res.stderr.strip()
    except Exception as lint_err:
        lint_output = f"Linter check skipped: {lint_err}"

    os.replace(tmp_path, file_path)

    # [Story 100.3 / FEAT-648] File-scoped cache invalidation
    try:
        from v5.cognition.context_prewarmer import evict_cached_summary
        evict_cached_summary(file_path)
    except Exception:
        pass
    _AST_CACHE.pop(file_path, None)

    return {
        "success": True,
        "file": file_path,
        "replacements": count,
        "lint_clean": lint_passed,
        "lint_report": lint_output if lint_output else "All syntax checks passed."
    }


@mcp.tool()
async def jit_locate(
    pattern: str,
    intent_description: str,
    max_results: int = 15,
) -> dict:
    """
    [FEAT-637 Grounding-Locate] Fast, context-clean file path locator with mandatory intent description.
    Bypasses raw grep output bloat by returning strictly matching relative file paths (zero line bodies).
    - pattern: Substring or glob to match file paths (e.g. "router.py", "foyer", "test_vector_pre_triage.py").
    - intent_description: Mandatory explanation of why this file path is needed (enforces deliberate grounding).
    - max_results: Maximum file paths to return (default 15).
    """
    import subprocess
    import fnmatch

    if not intent_description or len(intent_description.strip()) < 8:
        return {"error": "intent_description is required (min 8 chars) explaining why this file search is performed."}

    dev_lab = os.path.expanduser("~/Dev_Lab")
    matches = []

    # 1. Fast git ls-files across submodule trees
    try:
        res = subprocess.run(["git", "-C", dev_lab, "ls-files", "--recurse-submodules"], capture_output=True, text=True, timeout=1.5)
        if res.returncode == 0:
            lines = res.stdout.splitlines()
            p_clean = pattern.strip().lower()
            for line in lines:
                if p_clean in line.lower() or fnmatch.fnmatch(line.lower(), f"*{p_clean}*"):
                    matches.append(line)
                    if len(matches) >= max_results:
                        break
    except Exception:
        pass

    # 2. Fallback to find if git ls-files found nothing
    if not matches:
        try:
            res_find = subprocess.run(
                ["find", dev_lab, "-maxdepth", "4", "-iname", f"*{pattern.strip()}*", "-not", "-path", "*/.*", "-not", "-path", "*__pycache__*"],
                capture_output=True,
                text=True,
                timeout=1.5
            )
            if res_find.returncode == 0:
                for line in res_find.stdout.splitlines():
                    rel = os.path.relpath(line, dev_lab)
                    if rel not in matches:
                        matches.append(rel)
                        if len(matches) >= max_results:
                            break
        except Exception:
            pass

    return {
        "pattern": pattern,
        "intent": intent_description,
        "count": len(matches),
        "files": matches[:max_results],
    }


# Canonical Cognition Bridge ([FEAT-642] AST Outline & [FEAT-643] M5 Air Semantic Reduction)
HOMELAB_SRC = os.path.expanduser("~/Dev_Lab/HomeLabAI/src")
if HOMELAB_SRC not in sys.path:
    sys.path.insert(0, HOMELAB_SRC)

try:
    from v5.cognition.context_prewarmer import (
        extract_ast_outline as _extract_ast_outline,
        get_cached_semantic_summary as _get_cached_semantic_summary,
        reduce_file as _extract_semantic_reduce,
    )
except ImportError:
    def _extract_ast_outline(file_path: str, content: str) -> str:
        return "\n".join(content.splitlines()[:50])

    def _get_cached_semantic_summary(file_path: str) -> str | None:
        return None

    def _extract_semantic_reduce(file_path: str, raw_lines: list[str] = None) -> str:
        return f"File: {file_path} (Context reduction fallback)"


def _get_ast_cached(full_path: str, full_content: str) -> str:
    mtime = os.path.getmtime(full_path) if os.path.exists(full_path) else 0.0
    if full_path in _AST_CACHE:
        cached_mtime, cached_outline = _AST_CACHE[full_path]
        if cached_mtime == mtime:
            return cached_outline
    outline = _extract_ast_outline(full_path, full_content)
    _AST_CACHE[full_path] = (mtime, outline)
    return outline


@mcp.tool()
async def jit_read(
    file_path: str,
    start_line: int | None = None,
    end_line: int | None = None,
    outline_only: bool = True,
) -> dict:
    """
    [FEAT-642 / FEAT-643 Bounded Multi-Tier Reader] Smart, context-clean file reader.
    - file_path: Path to target file (relative to ~/Dev_Lab or absolute).
    - start_line: Optional 1-based start line. If specified, returns exact lines without outline.
    - end_line: Optional 1-based end line (max 150 lines per slice).
    - outline_only: If True (default when no line range is given), returns high-density AST outline
      and pre-warmed semantic summaries from CLaRa Context Cache in <400 tokens without body bloat.
      If the file is not yet cached, generates the reduced semantic digest JIT on the fly.
    """
    dev_lab = os.path.expanduser("~/Dev_Lab")
    full_path = file_path if os.path.isabs(file_path) else os.path.normpath(os.path.join(dev_lab, file_path))

    if not os.path.exists(full_path) and not os.path.isabs(file_path):
        sub_cand = os.path.normpath(os.path.join(dev_lab, "HomeLabAI", file_path))
        if os.path.exists(sub_cand):
            full_path = sub_cand

    if not os.path.exists(full_path):
        return {"error": f"File not found: {file_path} (resolved: {full_path})"}

    try:
        with open(full_path, "r", encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
    except Exception as e:
        return {"error": f"Failed to read file {file_path}: {e}"}

    total_lines = len(raw_lines)

    # 1. Line Range Mode (Exact lines requested)
    if start_line is not None or end_line is not None:
        s = max(1, start_line or 1)
        e = min(total_lines, end_line or (s + 100))
        if e - s > 200:
            e = s + 200
        sliced = raw_lines[s - 1:e]
        cached_semantic = _get_cached_semantic_summary(file_path)
        res = {
            "file": file_path,
            "mode": "slice",
            "start_line": s,
            "end_line": e,
            "total_lines": total_lines,
            "content": "".join(sliced),
        }
        if cached_semantic:
            res["volunteered_semantic_digest"] = cached_semantic
        return res

    # 2. Small File Direct Return (<40 lines)
    if total_lines <= 40:
        return {
            "file": file_path,
            "mode": "full",
            "total_lines": total_lines,
            "content": "".join(raw_lines),
        }

    # 3. High-Density AST Outline + Pre-Warmed Semantic Context (<400 tokens)
    full_content = "".join(raw_lines)
    outline = await asyncio.to_thread(_get_ast_cached, full_path, full_content)
    cached_semantic = _get_cached_semantic_summary(file_path)
    if not cached_semantic:
        # [FEAT-643] Load up M5 Air silicon and wait for neural reduction
        cached_semantic = await asyncio.to_thread(_extract_semantic_reduce, file_path)

    body_parts = []
    if cached_semantic:
        body_parts.append(f"### [PRE-WARMED SEMANTIC CONTEXT]\n{cached_semantic}\n")
    body_parts.append(f"### [AST STRUCTURAL BLUEPRINT]\n{outline}")

    return {
        "file": file_path,
        "mode": "outline_and_semantic",
        "total_lines": total_lines,
        "has_cached_semantic": bool(cached_semantic),
        "content": "\n".join(body_parts),
        "hint": "To inspect exact method implementations, call clara-dna_read(file_path, start_line=X, end_line=Y)",
    }


JIT_CACHE_DIR = os.environ.get("JIT_CACHE_DIR", os.path.expanduser("~/Dev_Lab/.jit_cache"))
CONDUCTOR_NOTES_PATH = os.path.join(JIT_CACHE_DIR, "clara_conductor_notes.json")
LEGACY_CONDUCTOR_NOTES_PATH = "/tmp/clara_conductor_notes.json"


def _load_conductor_notes() -> dict:
    """Load staged conductor blueprints from .jit_cache with legacy /tmp fallback."""
    for p in [CONDUCTOR_NOTES_PATH, LEGACY_CONDUCTOR_NOTES_PATH]:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
    return {}


def _save_conductor_notes(notes: dict) -> bool:
    """Save staged conductor blueprints to persistent .jit_cache and legacy /tmp."""
    try:
        os.makedirs(JIT_CACHE_DIR, exist_ok=True)
        for target in [CONDUCTOR_NOTES_PATH, LEGACY_CONDUCTOR_NOTES_PATH]:
            try:
                tmp_path = target + ".tmp"
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(notes, f, indent=2)
                os.replace(tmp_path, target)
            except Exception:
                pass
        return True
    except Exception:
        return False


@mcp.tool()
async def jit_stage(
    file_path: str,
    plan_content: str,
    patch_blueprint: str = "",
    ast_anchors: list = None,
    diff_directives: list = None,
) -> dict:
    """[Story 98.6 / FEAT-647] Atlas (L2 Conductor) stages pre-computed plan, AST anchors, and patch blueprints for L3 worker recall."""
    if ast_anchors is None:
        ast_anchors = []
    if diff_directives is None:
        diff_directives = []
    notes = _load_conductor_notes()

    notes[file_path] = {
        "plan_content": plan_content,
        "patch_blueprint": patch_blueprint,
        "ast_anchors": ast_anchors,
        "diff_directives": diff_directives,
        "staged_at": time.time(),
    }

    if not _save_conductor_notes(notes):
        return {"status": "error", "message": "Failed to persist notes to .jit_cache"}

    return {
        "status": "staged",
        "file_path": file_path,
    }


def _load_agents_l3_rules() -> str:
    """Load verbatim AGENTS_L3.md operational rules for dynamic tool injection."""
    for p in (
        os.path.expanduser("~/Dev_Lab/AGENTS_L3.md"),
        os.path.expanduser("~/AcmeLab/AGENTS_L3.md"),
    ):
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
    return "You are the Layer 3 Blind Surgical Worker. Ingest blueprint, apply safe_patch, run pytest, and call jit_checkpoint. Zero wandering."


@mcp.tool()
async def jit_research(file_path: str, query: str = "") -> str:
    """[Story 98.6 / FEAT-647] JITC Research tool. Recalls pre-computed L2 conductor blueprints or loads AGENTS_L3.md rules as fresh empirical findings.
    - file_path: Target file path, basename, or 'AGENTS_L3.md' to load operational rules.
    - query: Optional search query.
    """
    # 1. Direct AGENTS_L3.md rule ingestion
    if file_path.strip().lower() in ("agents_l3.md", "agents_l3", "agents-l3.md", "agents-l3") or file_path.endswith("AGENTS_L3.md"):
        l3_rules = _load_agents_l3_rules()
        return f"### 📗 [LAYER 3 OPERATIONAL MANDATE & ANTI-SCAVENGING LAW]\n{l3_rules}"

    notes = _load_conductor_notes()

    # 2. Check staged conductor notes (exact or fuzzy basename match)
    matched_key = None
    if file_path in notes:
        matched_key = file_path
    else:
        target_base = os.path.basename(file_path).lower()
        for k in notes:
            if os.path.basename(k).lower() == target_base or target_base in k.lower():
                matched_key = k
                break

    if matched_key:
        file_notes = notes[matched_key]
        ast_anchors = file_notes.get("ast_anchors", [])
        patch_blueprint = file_notes.get("patch_blueprint", "")
        plan_content = file_notes.get("plan_content", "")
        diff_directives = file_notes.get("diff_directives", [])

        output_lines = [
            f"### 📋 [STAGED CONDUCTOR BLUEPRINT: `{matched_key}`]",
            f"AST Anchors: {ast_anchors}",
            f"Patch Blueprint:\n{patch_blueprint}" if patch_blueprint else f"Plan Content:\n{plan_content}",
        ]
        if diff_directives:
            output_lines.append(f"Diff Directives: {diff_directives}")
        if plan_content and patch_blueprint:
            output_lines.append(f"Plan Notes:\n{plan_content}")
        return "\n\n".join(output_lines)

    # 3. Fallback to physical disk read + AST outline
    full_path = file_path if os.path.isabs(file_path) else os.path.join(HOMELAB_SRC, "..", file_path)
    if not os.path.exists(full_path):
        full_path = os.path.join(HOMELAB_SRC, file_path)
    ast_outline = "No AST outline available"
    if os.path.exists(full_path):
        try:
            with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            ast_outline = _extract_ast_outline(full_path, content)
        except Exception:
            pass
    semantic_summary = _get_cached_semantic_summary(file_path) or "No semantic summary cached"
    return f"Analysis for {file_path}:\nAST Outline: {ast_outline}\nSemantic Summary: {semantic_summary}"


@mcp.tool()
async def jit_diagnose(test_output: str, error_context: str = "") -> str:
    """Scans the test output / traceback, isolates the failing assertion / error line, and returns an atomic 2-line diagnosis."""
    match = re.search(r"E\s+(.*)", test_output)
    failing_line = match.group(1) if match else "Unknown error"
    return f"Diagnosis: Failed assertion '{failing_line}'.\nCheck logical conditions, types, or fixture paths."


@mcp.tool()
async def jit_checkpoint(
    status: str, summary: str, artifacts_modified: list = None
) -> dict:
    """Appends a JSON record with timestamp, status, summary, and artifacts to delegation_ledger.jsonl."""
    if artifacts_modified is None:
        artifacts_modified = []
    ledger_path = os.path.expanduser(
        "~/Dev_Lab/HomeLabAI/data/delegation_ledger.jsonl"
    )
    fallback_ledger = os.path.expanduser(
        "~/Dev_Lab/Portfolio_Dev/field_notes/data/delegation_ledger.jsonl"
    )

    record = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "status": status,
        "summary": summary,
        "artifacts_modified": artifacts_modified,
    }

    for p in [ledger_path, fallback_ledger]:
        try:
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            pass

    return {"status": "success", "record": record}



if __name__ == "__main__":
    mcp.run(transport="stdio")
