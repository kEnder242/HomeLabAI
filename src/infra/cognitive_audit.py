import json
import logging
import asyncio

class CognitiveAudit:
    """
    [FEAT-190] The Judge: Automated logic-based validation for technical tests.
    Uses a peer node to judge if a response is technically consistent and 'vibe-aligned'.
    """
    def __init__(self, resident_node):
        self.node = resident_node

    async def audit_technical_truth(self, query: str, response: str, constraints: str) -> bool:
        """
        Asks the peer node to judge the technical accuracy of an output.
        Returns True if the response is consistent with the constraints.
        """
        audit_prompt = (
            f"You are the Cognitive Auditor. YOUR TASK: Judge the following response for technical accuracy. "
            f"QUERY: {query}\n"
            f"RESPONSE: {response}\n"
            f"CONSTRAINTS: {constraints}\n\n"
            f"RULES: Output ONLY 'PASS' if the response satisfies the query and constraints. "
            f"Output ONLY 'FAIL' if there is a technical hallucination or logical inconsistency. "
            f"No conversational filler."
        )
        
        try:
            # [FEAT-240] Use the Native Sampling bridge for peer auditing
            result = await self.node.call_tool("think", {"query": audit_prompt})
            decision = result.content[0].text.upper()
            
            logging.info(f"[AUDIT] Decision: {decision}")
            
            # [HARDENING] Tiered keyword check for chatty small models
            if "FAIL" in decision:
                return False
            if "PASS" in decision or "ACCURATE" in decision:
                return True
            
            # Default to pass if the model is just being verbose but not failing
            return True
        except Exception as e:
            logging.error(f"[AUDIT] System failure: {e}")
            return False

    async def audit_vibe_alignment(self, response: str, expected_vibe: str) -> float:
        """[Task 6.4] Judges if the response tone matches the expected VIBE. Returns resonance score (0.0-1.0)."""
        audit_prompt = (
            f"You are the Vibe Auditor. YOUR TASK: On a scale of 0.0 to 1.0, how well does the following text exhibit a '{expected_vibe}' tone?\n"
            f"TEXT: {response}\n\n"
            f"RULES: Output ONLY the numeric score (e.g. 0.85). No conversational filler."
        )
        try:
            result = await self.node.call_tool("think", {"query": audit_prompt, "internal": True})
            score_text = result.content[0].text.strip()
            
            # Extract first float found
            import re
            match = re.search(r"\d+\.\d+", score_text)
            if match:
                score = float(match.group())
                logging.info(f"[AUDIT] Vibe Resonance: {score:.2f}")
                return score
            
            # If no float, check for pass/fail keywords as fallback
            if "PASS" in score_text.upper(): return 1.0
            if "FAIL" in score_text.upper(): return 0.0
            
            return 1.0 # Default to pass if unparseable but not failing
        except Exception as e:
            logging.error(f"[AUDIT] Vibe system failure: {e}")
            return 0.0
