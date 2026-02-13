import asyncio
import websockets
import json
import logging
import re
from typing import List

# Configuration
HOST = "z87-Linux.local"
PORT = 8765

logging.basicConfig(level=logging.INFO, format='%(asctime)s - TEST - %(message)s')

class TestResult:
    def __init__(self, passed: bool, feedback: str, score: float = 0.0):
        self.passed = passed
        self.feedback = feedback
        self.score = score

class Judge:
    def evaluate(self, prompt: str, response: str) -> TestResult:
        raise NotImplementedError

class RegexJudge(Judge):
    def __init__(self, pattern: str, should_match: bool = True):
        self.pattern = pattern
        self.should_match = should_match

    def evaluate(self, prompt: str, response: str) -> TestResult:
        match = re.search(self.pattern, response, re.IGNORECASE)
        passed = bool(match) == self.should_match
        feedback = f"Pattern '{self.pattern}' {'found' if match else 'not found'}."
        return TestResult(passed, feedback, 1.0 if passed else 0.0)

class InteractiveJudge(Judge):
    def evaluate(self, prompt: str, response: str) -> TestResult:
        print(f"\n--- INTERACTIVE JUDGE ---")
        print(f"Prompt:   {prompt}")
        print(f"Response: {response}")
        print(f"-------------------------")
        choice = input("Pass? (y/n/c for comment): ").strip().lower()
        if choice == 'y':
            return TestResult(True, "User approved", 1.0)
        elif choice == 'c':
            comment = input("Comment: ")
            return TestResult(True, f"User Comment: {comment}", 1.0)
        return TestResult(False, "User rejected", 0.0)

class TestCase:
    def __init__(self, name: str, prompt: str, judges: List[Judge]):
        self.name = name
        self.prompt = prompt
        self.judges = judges

async def run_test_suite(test_cases: List[TestCase]):
    uri = f"ws://{HOST}:{PORT}"
    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as websocket:
            for test in test_cases:
                logging.info(f"RUNNING: {test.name}")

                # 1. Inject Text
                await websocket.send(json.dumps({"debug_text": test.prompt}))

                # 2. Wait for Response (Brain/Pinky)
                # We need to wait a bit for silence timeout logic on server side if it's strictly time based
                # But since we set turn_pending=True, check_turn_end needs to fire.
                # Currently check_turn_end fires inside the audio loop.
                # Since we aren't sending audio, the loop might block on 'async for message'.
                # FIX: We send a small silence packet to tick the loop?
                # OR we just rely on the fact that we can send another message.

                # Wait for the response JSON
                try:
                    # Depending on server logic, it might take a moment (silence timeout is 1.2s)
                    # We might need to send "keepalives" or silence frames to drive the loop
                    # if the server loop is blocked on `websocket` iterator.

                    response_json = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    data = json.loads(response_json)
                    response_text = data.get("brain", "")

                    logging.info(f"GOT: {response_text[:100]}...")

                    # 3. Judge
                    all_passed = True
                    for judge in test.judges:
                        result = judge.evaluate(test.prompt, response_text)
                        if not result.passed:
                            all_passed = False
                            logging.error(f"FAIL: {result.feedback}")
                        else:
                            logging.info(f"PASS: {result.feedback}")

                except asyncio.TimeoutError:
                    logging.error(f"TIMEOUT: No response for {test.name}")

            # Graceful exit
            await websocket.close()

    except Exception as e:
        logging.error(f"Connection failed: {e}")

if __name__ == "__main__":
    # Define Suite
    suite = [
        TestCase(
            "Basic Greeting",
            "Hello Pinky, are you there?",
            [RegexJudge(r"(Narf|Poit|Zort|Egad)")]
        ),
        TestCase(
            "Complex Handoff",
            "Pinky, write a Python script to calculate Fibonacci sequence.",
            [RegexJudge(r"ASK_BRAIN", should_match=False), RegexJudge(r"Brain", should_match=True)]
            # Note: The server actually parses ASK_BRAIN internally and returns the Brain's response.
            # So the user sees the BRAIN's response, not the raw "ASK_BRAIN" string unless logic fails.
            # We expect the 'brain_source' to be 'The Brain'.
        )
    ]

    asyncio.run(run_test_suite(suite))
