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
    return True, "No linter defined for this file type."

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

    # 4. Apply Replacement
    new_content = content.replace(old_string, new_string, 1)
    
    try:
        with open(target_file, "w") as f:
            f.write(new_content)
    except Exception as e:
        return f"❌ Error writing file: {e}"

    # 5. Post-Operation Linting
    passed, lint_output = lint_file(target_file)
    
    status_msg = f"✅ [{description}] applied to {os.path.basename(target_file)}."
    if not passed:
        return f"{status_msg}\n\n⚠️ LINT WARNINGS DETECTED:\n{lint_output}"
    
    return f"{status_msg}\n\n✨ File is lint-clean."

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
