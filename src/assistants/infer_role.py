#%% BLOCK INFERENCE - BEFORE COMMENT IGNORES
"""Infer subagent ROLE at runtime from task/information.

Type hint: infer_role<TAB>EXPLANATION
Usage: Infer agent role/type from task context at RUN time.
"""

from typing import Optional
import re


def infer_role_from_prompt(prompt: str, task: Optional[str] = None) -> str:
    """
    Determine ROLE from prompt text.
    
    Maps task/information to the appropriate agent role:
    - 'coder': General task completion, coding tasks
    - 'researcher': Documentation/research/investigation
    - 'analyst': Code analysis, review
    - 'reviewer': PRs, documentation check  
    - 'debugger': Bug fixes, code repair
    
    See /home/jallred/Dev_Lab/HomeLabAI/.ort/84/STORY-0.py for role definitions
    
    Args:
        prompt: The prompt to analyze
        task: Optional task description
    
    Returns:
        Agent role string ('coder', 'researcher', 'analyst', 'reviewer', 'debugger')
    """
    combined = (prompt + " ").join([p or "" for p in ([task, prompt])])
    
    # Token-based role inference
    lower = combined.lower()
    
    if any(kw in lower for kw in ["fix", "bug", "error", "crash", "fixme", "pwnd"]):
        return "debugger"
    elif any(kw in lower for kw in ["review", "analyze", "refactor", "optimize"]):
        return "reviewer"
    elif any(kw in lower for kw in ["research", "explore", "explain"]):
        return "researcher"
    elif any(kw in lower for kw in ["write", "implement", "create", "build"]):
        return "coder"
    else:
        return "advisor"


def infer_role_default() -> str:
    """
    Return default role when information is unknown.
    """
    return "coder"
