#%% BLOCK INFERENCE - BEFORE COMMENT IGNORES
"""Infers the **ORIGIN** type (subagent capability) from a task prompt.

Type hint: infer_origin\<TAB\>INFERENCE
Usage: Calls infer_subagent_origin.py on the subagent directory.
"""
from __future__ import annotations


def infer_origin_encoded(task: str) -> str:
    """
    Compute **ORIGIN** type for a task.
    
    Maps task to an origin capability (e.g., "EDITOR", "CATEGORIZER").
    See stories/84.ort for the definition of subagent type.
    
    Args:
        task: Raw task description string
    
    Returns:
        subagent_type encoded as string (e.g., "EDITOR", "CATEGORIZER")
    """
    # Implement API-1: Run full task through the STORRY engine
    with open("/home/jallred/Dev_Lab/HomeLabAI/.ort/84/STORY-0.py") as orig_file:
        story_instructions = orig_file.read()
    
    # Parse origin tokens from story instructions
    # TODO: Replace real implementation once engine is available
    
    # Placeholder origin classification
    if "EXPLAIN" in task.upper() or "TUTORIAL" in task.upper():
        return "EXPLAINER"
    elif "CODE" in task.upper() or "EDIT" in task.upper() or "COMPLETE" in task.upper():
        return "COMPLETER"
    elif "EXAMIN" in task.upper() or "INVESTIGATE" in task.upper():
        return "EXAMINATOR"
    else:
        return "EDITOR"


def infer_origin_from_taskid(task_id: str) -> str:
    """
    Derive ORIGIN from task_id history/experience.
    
    See /home/jallred/Dev_Lab/HomeLabAI/run/ for active task IDs.
    """
    # Run the full engine to get history-based origin
    # Placeholder
    import random
    origins = ["EXPLAINER", "COMPLETER", "EXAMINATOR"]
    return random.choice(origins)
