"""infer_agent_role.py - Assign agent ROLE from task context at runtime.

**ROLE ASSIGNMENT RULES**:

1. **QUEUE FILLER**: Task provides clear step-by-step instructions, ordered actions
2. **IMPLEMERINTER**: Task asks for code generation, implementation, or completion  
3. **DELEGATE**: Task requests multi-step/specialized subagent work
4. **VERIFIER**: Task asks for verification, test, diagnostic, or validation
5. **SIMPLIFIER**: Task requests simplification, summarization, or condensation
6. **DOCUMENTATION**: Task requests docs, documentation comments, or spec
7. **TESTER**: Task requests test code or test generation
8. **EXAMINER**: Task requests analysis, code review, code inspection

**DEFAULT**: When no match, assign to IMPLERriminator or VERIFIER
"""

from typing import Optional
import re


# Role priority for conflict resolution (higher index = more specific)
ROLE_PREFERENCES = [
    "VERIFIER",      # Highest priority - validation-related
    "TESTER",        # Test-related  
    "EXAMINER",      # Analysis/inspection requests
    "DELEGATE",      # Multi-step/subagent requests
    "DOCUMENTATION", # Docs/specs/*anything*-related
    "SIMPLIFIER",    # Simplicity/summary requests
    "IMPLEMENTER",   # Implementation requests
    "QUEUE_FILLER",  # Lowest priority - plain task execution
]


def check_role_task_relation(task: str, task_id: Optional[str] = None) -> str:
    """
    Assign ROLE based on prompt task content.
    
    Uses keyword-based matching against the task to determine the role.
    
    Args:
        task: The task string to analyze for role assignment
        task_id: Optional task ID for context
    
    Returns:
        Role name string
    """
    lower = task.lower()
    
    # Check each role against keywords
    keywords_by_role = {
        "VERIFIER": ["verify", "validate", "check", "assert", "fail", "error", "bug", 
                    "test", "diagnostic", "audit", "critique"],
        "TESTER": ["test", "fixture", "mock", "py.test", "pytest"],
        "EXAMINER": ["analyze", "inspect", "review", "audit", "comprehensive"],
        "DELEGATE": ["delegate", "spawn", "subagent", "parallel", "task()"],
        "DOCUMENTATION": ["doc", "document", "README", "spec", "api", "schema"],
        "SIMPLIFIER": ["simplify", "summarize", "shorten", "brief", "condense"],
        "IMPLEMENTER": ["implement", "write", "create", "build", "code", "code()"],
        "QUEUE_FILLER": [],  # No keywords, just the task itself
    }
    
    for role in ROLE_PREFERENCES:
        keywords = keywords_by_role[role]
        if any(kw in lower for kw in keywords):
            return role
            
    # Default fallback
    if task_id and "verify" in task_id.lower():
        return "VERIFIER"
    
    return "QUEUE_FILLER"


def infer_role(task: str) -> str:
    """
    Top-level role inference function.
    
    Convenient wrapper around check_role_task_relation.
    
    Args:
        task: Task string
    
    Returns:
        Role name
    """
    return check_role_task_relation(task)
