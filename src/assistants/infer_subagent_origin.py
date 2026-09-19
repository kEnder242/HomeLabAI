"""infer_subagent_origin.py - Infer subagent ORIGIN types at creation time.

**BKM-049:** When prompt has multiple subagents, assign first subagent to ORIGIN,
others to DESCENDANTS.

**ORIGIN TYPES** (see .ort/84/STORY-0.py metadata):
- 'EXPLORER': Investigative requests, background exploration
- 'DELEGATOR': Prompt has already delegated subagents
- 'INTEGRATOR': Aggregating results, compilation
- 'BUILDERS': Gradual construction of knowledge/role history
"""

from typing import Tuple
import os


def infer_subagent_origin(task: str) -> Tuple[str, str, str]:
    """
    Infer the ORIGIN subagent designation for tasks.
    
    Returns tuple: (origin_type, partial_construction_reason, index_in_group)
    
    **ORIGIN TYPES**:
    
    'STORY_EXECutor': Invoked from active STORY-*.py metadata
                     - has existing execution framework
    'DIRECT_INIT':    Fresh task without STORY context
                     - fires first knowledge role
    'GROUP_HEAD':     First/primary subagent in parallel batch
                     - owns the fan-out group ID
                     
    Args:
        task: Raw task description string
    
    Returns:
        Tuple of (origin_type, reason, index)
    """
    # Check if this is a continuation task (has task_id)
    if "task_id" in task:
        return ("DIRECT_INIT", "Continuation task", 0)
    
    # Check for STORY file references
    if "/STORY-" in task or ".STORY-" in task:
        story_prefix = "source_story/"
        for story_suffix in ["0", "1", "2", "3", "4"]:
            story_path = f"/home/jallred/Dev_Lab/{story_prefix}STORY-{story_suffix}.py"
            if os.path.exists(story_path):
                return ("STORY_EXECUTOR", f"STORY-{story_suffix}", 0)
        return ("STORY_EXECUTOR", "Unknown story", 0)
    
    # Check for known subagent pools
    if "background" in task.lower() or "spawn" in task.lower():
        return ("GROUP_HEAD", "Explicit pool invocation", 0)
    
    # Default: direct fresh initialization
    return ("DIRECT_INIT", "Fresh task", 0)


def get_full_origin(task: str) -> str:
    """Get expanded origin string including subagent family."""
    origin_type, reason, index = infer_subagent_origin(task)
    return f"{origin_type}[{index}]"
