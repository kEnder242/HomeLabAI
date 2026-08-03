#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Scalpel: Unified Surgical Patching Tool
[FEAT-198] High-Fidelity Replacement Tool for Gemini CLI.

Usage:
1. MCP Mode: Run without arguments (FastMCP stdio).
2. CLI Mode: ./system_scalpel.py <file> <desc> <old_string> <new_string>
"""

import os
import sys
import re
import hashlib
import subprocess
import logging
import asyncio
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
# Use absolute path to the venv ruff to ensure it works across contexts
RUFF_PATH = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/ruff"

# --- FastMCP Server ---
mcp = FastMCP("System Scalpel")

def lint_file(file_path):
    """Detects type and runs appropriate linter. Returns (passed, output)."""
    if file_path.endswith(".py"):
        try:
            # Ignore E501 (Line length) to focus on logic and imports
            res = subprocess.run(
                [RUFF_PATH, "check", file_path, "--select", "E,F,W", "--ignore", "E501"],
                capture_output=True, text=True
            )
            return res.returncode == 0, res.stdout + res.stderr
        except Exception as e:
            return False, f"Linter execution failed: {e}"
    elif file_path.endswith(".js"):
        try:
            # Check if eslint is available in path
            res = subprocess.run(["eslint", file_path, "--quiet"], capture_output=True, text=True)
            return res.returncode == 0, res.stdout + res.stderr
        except Exception:
            return True, "JS Linter (eslint) not found. Skipping."
    elif file_path.endswith(".html"):
        return lint_html_inline_js(file_path)
    return True, "No linter defined for this file type."

def lint_html_inline_js(file_path):
    """Extract inline <script> blocks (no src attr, non-empty) and node --check each.

    Returns (passed, output). Catches the class of error that broke status.html:
    an unbalanced brace inside inline <script> that a page-level regex/sed misses.
    """
    try:
        with open(file_path, "r") as f:
            content = f.read()
    except Exception as e:
        return False, f"HTML read failed: {e}"

    # Match <script> WITHOUT a src= attribute; non-lazy body up to </script>.
    blocks = re.findall(r'<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>', content, re.S | re.I)
    errors = []
    checked = 0
    for i, block in enumerate(blocks):
        if not block.strip():
            continue
        checked += 1
        tmp = f"{file_path}.block{i}.js"
        try:
            with open(tmp, "w") as f:
                f.write(block)
            res = subprocess.run(["node", "--check", tmp], capture_output=True, text=True)
            if res.returncode != 0:
                errors.append(f"<script> block #{i}: {res.stderr.strip()}")
        except Exception as e:
            errors.append(f"<script> block #{i}: check error {e}")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)

    if errors:
        return False, f"HTML inline-JS syntax errors ({checked} checked):\n" + "\n".join(errors)
    return True, f"HTML inline-JS OK ({checked} non-empty inline <script> blocks checked via node --check)."

@mcp.tool()
async def safe_scalpel(target_file: str, old_string: str, new_string: str, description: str) -> str:
    """
    [FEAT-198] The Safe-Scalpel: A lint-gated surgical replacement tool.
    replaces exactly ONE occurrence of old_string with new_string.
    """
    # 1. Path Resolution
    # Handle relative paths from project root
    if not target_file.startswith("/"):
        # Assume relative to Dev_Lab root
        root = os.path.expanduser("~/Dev_Lab")
        target_file = os.path.join(root, target_file)
    
    if not os.path.exists(target_file):
        return f"❌ Error: File not found at {target_file}"

    # 2. Read Content
    try:
        with open(target_file, "r") as f:
            content = f.read()
    except Exception as e:
        return f"❌ Error reading file: {e}"

    # 3. Precision Check
    occurrences = content.count(old_string)
    if occurrences == 0:
        return f"❌ Surgical strike failed: 'old_string' not found in {os.path.basename(target_file)}."
    if occurrences > 1:
        return f"❌ Surgical strike aborted: Multiple occurrences ({occurrences}) found. Provide more context."

    # 4. Stage New Content & Lint (Report-Only, BKM-011)
    orig_passed, orig_output = lint_file(target_file)

    new_content = content.replace(old_string, new_string, 1)

    tmp_path = target_file + ".scalpel_tmp"
    try:
        with open(tmp_path, "w") as f:
            f.write(new_content)
        new_passed, new_output = lint_file(tmp_path)
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return f"❌ Error staging patch: {e}"

    # Lint is REPORT-ONLY: never blocks the apply. Annotate regressions.
    os.replace(tmp_path, target_file)

    if new_passed:
        if orig_passed:
            return f"✅ [{description}] applied to {os.path.basename(target_file)}.\n\n✨ File is lint-clean."
        return f"✅ [{description}] applied to {os.path.basename(target_file)}.\n\n⚠️ Pre-existing lint issues unchanged (baseline):\n{orig_output}"

    # New content failed lint: applied anyway, report with regression tag.
    if orig_passed:
        return f"✅ [{description}] applied to {os.path.basename(target_file)} (lint REPORT-ONLY).\n\n⚠️ LINT FAILURES INTRODUCED (was clean before):\n{new_output}"
    return f"✅ [{description}] applied to {os.path.basename(target_file)} (lint REPORT-ONLY).\n\n⚠️ LINT FAILURES (pre-existing baseline):\n{orig_output}\n\nAdditional/new issues:\n{new_output}"

async def run_cli():
    """Standalone CLI implementation."""
    if len(sys.argv) < 5:
        print("Usage: ./system_scalpel.py <file> <desc> <old_string> <new_string>")
        sys.exit(1)
    
    target_file = sys.argv[1]
    description = sys.argv[2]
    old_string = sys.argv[3]
    new_string = sys.argv[4]
    
    result = await safe_scalpel(target_file, old_string, new_string, description)
    print(result)

if __name__ == "__main__":
    # If arguments provided, run as CLI. Otherwise, run as MCP server.
    if len(sys.argv) > 1:
        asyncio.run(run_cli())
    else:
        asyncio.run(mcp.run_stdio_async())
