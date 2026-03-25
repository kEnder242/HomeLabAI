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
            decision = result.content[0].text.strip().upper()
            
            logging.info(f"[AUDIT] Decision: {decision}")
            return "PASS" in decision
        except Exception as e:
            logging.error(f"[AUDIT] System failure: {e}")
            return False

    async def audit_vibe_alignment(self, response: str, expected_vibe: str) -> bool:
        """Judges if the response tone matches the expected VIBE."""
        audit_prompt = (
            f"You are the Vibe Auditor. Does the following text exhibit a '{expected_vibe}' tone?\n"
            f"TEXT: {response}\n\n"
            f"Output ONLY 'PASS' or 'FAIL'."
        )
        try:
            result = await self.node.call_tool("think", {"query": audit_prompt})
            return "PASS" in result.content[0].text.strip().upper()
        except:
            return False
