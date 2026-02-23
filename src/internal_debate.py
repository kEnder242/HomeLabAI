import asyncio
import logging
import datetime
import os
import json

class InternalDebate:
    def __init__(self, archive_node, pinky_node, brain_node):
        self.archive = archive_node
        self.pinky = pinky_node
        self.brain = brain_node
        self.history = []

    async def run_session(self, topic, turns=3):
        logging.info(f"[DEBATE] Starting debate on: {topic}")
        
        # 1. Archive Context Retrieval
        context = ""
        if self.archive:
            try:
                res = await self.archive.call_tool("peek_related_notes", arguments={"query": topic})
                context = res.content[0].text
            except Exception as e:
                logging.error(f"[DEBATE] Context retrieval failed: {e}")

        # 2. The Interaction Loop
        current_input = topic
        if context:
            current_input = f"Topic: {topic}\nHistorical Context: {context}"

        for i in range(turns):
            # Brain's Strategic Insight
            logging.info(f"[DEBATE] Turn {i+1}: Brain's turn.")
            brain_prompt = (
                f"Analyze this topic: {current_input}. "
                "Provide a strategic, validation-oriented perspective. "
                "Be concise and technical."
            )
            try:
                res = await self.brain.call_tool("deep_think", arguments={"task": brain_prompt, "context": "\n".join(self.history[-2:])})
                brain_out = res.content[0].text
                self.history.append(f"Brain: {brain_out}")
            except Exception as e:
                logging.error(f"[DEBATE] Brain failed: {e}")
                break

            # Pinky's Grounding/Banter
            logging.info(f"[DEBATE] Turn {i+1}: Pinky's turn.")
            pinky_prompt = (
                f"The Brain said: '{brain_out}'. "
                "Ground this in our practical lab environment. "
                "Add your characteristic enthusiasm and Narf-isms."
            )
            try:
                res = await self.pinky.call_tool("facilitate", arguments={"query": pinky_prompt, "context": brain_out})
                pinky_out = res.content[0].text
                self.history.append(f"Pinky: {pinky_out}")
                current_input = pinky_out
            except Exception as e:
                logging.error(f"[DEBATE] Pinky failed: {e}")
                break

        # 3. Final Synthesis
        summary = "\n---\n".join(self.history)
        return summary

    async def save_to_ledger(self, summary):
        """Saves the debate to the interaction logs for Morning Briefing."""
        log_dir = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data")
        log_path = os.path.join(log_dir, "nightly_dialogue.json")
        
        event = {
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "topic": "Internal Debate",
            "content": summary
        }
        
        try:
            with open(log_path, "w") as f:
                json.dump(event, f, indent=4)
            logging.info(f"[DEBATE] Dialogue saved to {log_path}")
        except Exception as e:
            logging.error(f"[DEBATE] Failed to save dialogue: {e}")

async def run_nightly_talk(archive, pinky, brain, topic="The future of laboratory automation"):
    debate = InternalDebate(archive, pinky, brain)
    summary = await debate.run_session(topic)
    await debate.save_to_ledger(summary)
    return summary
