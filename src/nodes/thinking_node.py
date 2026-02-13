import json
import logging
import sys
from typing import Dict, List, Optional

from mcp.server.fastmcp import FastMCP

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [THINKING] %(levelname)s - %(message)s',
    stream=sys.stderr
)

mcp = FastMCP("Sequential Thinking")

# In-memory state for active thinking sessions
thought_history: List[Dict] = []


@mcp.tool()
def sequential_thinking(
    thought: str,
    thought_number: int,
    total_thoughts: int,
    next_thought_needed: bool,
    is_revision: Optional[bool] = False,
    revises_thought_number: Optional[int] = None
) -> str:
    """
    A tool for structured, multi-step reasoning.
    thought: The current thinking content.
    thought_number: Current step in the sequence.
    total_thoughts: Estimated total steps.
    next_thought_needed: True if more thinking is required.
    is_revision: True if this revises a previous step.
    revises_thought_number: The step number being revised.
    """
    entry = {
        "step": thought_number,
        "content": thought,
        "is_revision": is_revision,
        "revises": revises_thought_number
    }

    thought_history.append(entry)

    status = f"Thought {thought_number}/{total_thoughts}"
    if is_revision:
        status += f" (Revision of {revises_thought_number})"

    logging.info(f"[LOGIC] {status}: {thought[:50]}...")

    response = {
        "status": status,
        "next_needed": next_thought_needed,
        "history_count": len(thought_history)
    }

    return json.dumps(response)


@mcp.tool()
def clear_thoughts() -> str:
    """Resets the current thinking history."""
    global thought_history
    count = len(thought_history)
    thought_history = []
    return f"Thinking history cleared. Purged {count} thoughts."


if __name__ == "__main__":
    mcp.run()
