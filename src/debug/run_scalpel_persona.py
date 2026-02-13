import sys
import os
from atomic_patcher import apply_batch_refinement

target_pinky = "HomeLabAI/src/nodes/pinky_node.py"

edits_pinky = [
    {
        "old": "- POKE BRAIN: If the user explicitly asks for 'Brain', tries to talk \\n    \"to him, or asks a question that requires archival evidence, \\n    \"use 'ask_brain()'. ",
        "new": "- DELEGATION: If the user asks for 'Brain' or tries to talk to him, you MUST use 'ask_brain()'.",
        "desc": "Simplify Pinky Brain Delegation"
    }
]

apply_batch_refinement(target_pinky, edits_pinky)
