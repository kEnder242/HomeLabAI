#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
System Scalpel MCP Server
[FEAT-198] High-Fidelity Surgical Patching Tool for Gemini CLI.

Provides the 'safe_scalpel' tool with integrated lint-reporting.
"""

import os
import subprocess
import logging
from mcp.server.fastmcp import FastMCP

# --- Configuration ---
RUFF_PATH = "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/ruff"

# --- FastMCP Server ---
mcp = FastMCP("System Scalpel")

def lint_file(file_path):
    """Detects type and runs appropriate linter. Returns (passed, output)."""
    if file_path.endswith(".py"):
        # Ignore E501 (Line length) to focus on logic and imports
        try:
            res = subprocess.run(
                [RUFF_PATH, "check", file_path, "--select", "E,F,W", "--ignore", "E501"],
                capture_output=True, text=True
            )
            return res.returncode == 0, res.stdout + res.stderr
        except Exception as e:
            return False, f"Linter execution failed: {e}"
    elif file_path.endswith(".js"):
        try:
            res = subprocess.run(["eslint", file_path, "--quiet"], capture_output=True, text=True)
            return res.returncode == 0, res.stdout + res.stderr
        except Exception as e:
            return False, f"Linter execution failed: {e}"
    return True, "No linter defined for this file type."

@mcp.tool()
async def safe_scalpel(target_file: str, old_string: str, new_string: str, description: str) -> str:
    """
    [FEAT-198] The Safe-Scalpel: A lint-gated surgical replacement tool.
    replaces exactly ONE occurrence of old_string with new_string.
    Returns status and any linting warnings.
    """
    # 1. Path Resolution
    if not target_file.startswith("/"):
        target_file = os.path.join(os.path.expanduser("~/Dev_Lab"), target_file)
    
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
        return f"❌ Surgical strike aborted: Multiple occurrences ({occurrences}) found. Provide more context to ensure unique replacement."

    # 4. Apply Replacement
    new_content = content.replace(old_string, new_string, 1)
    
    try:
        with open(target_file, "w") as f:
            f.write(new_content)
    except Exception as e:
        return f"❌ Error writing file: {e}"

    # 5. Post-Operation Linting
    passed, lint_output = lint_file(target_file)
    
    status_msg = f"✅ [{description}] applied successfully."
    if not passed:
        return f"{status_msg}\n\n⚠️ LINT WARNINGS DETECTED:\n{lint_output}"
    
    return f"{status_msg}\n\n✨ File is lint-clean."

if __name__ == "__main__":
    import asyncio
    asyncio.run(mcp.run_stdio_async())
