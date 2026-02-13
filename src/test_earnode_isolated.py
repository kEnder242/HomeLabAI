import numpy as np
import sys
import os
import logging

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add src to path
sys.path.append(os.path.abspath("HomeLabAI/src"))
from equipment.ear_node import EarNode

def dummy_callback(text):
    print(f"Transcript: {text}")

def run_verification():
    print("🚀 Initializing EarNode...")
    try:
        ear = EarNode(callback=dummy_callback)
    except Exception as e:
        print(f"❌ Failed to initialize EarNode: {e}")
        import traceback
        traceback.print_exc()
        return

    print("🔊 Generating dummy audio signal (2 seconds of noise)...")
    # 16kHz, 2 seconds
    duration = 2
    sample_rate = 16000
    # Use random noise that is loud enough to pass SILENCE_THRESHOLD
    audio_data = np.random.randint(-5000, 5000, size=sample_rate * duration, dtype=np.int16)

    print("🧠 Running process_audio...")
    try:
        # Inspect the model sub-objects
        print(f"DEBUG: model.decoding.decoding.cuda_graphs = {getattr(ear.model.decoding.decoding, 'cuda_graphs', 'N/A')}")

        # Check the loopers
        if hasattr(ear.model.decoding.decoding, 'decoding_computer'):
            computer = ear.model.decoding.decoding.decoding_computer
            print(f"DEBUG: decoding_computer type: {type(computer).__name__}")
            if hasattr(computer, 'cuda_graphs'):
                print(f"DEBUG: computer.cuda_graphs = {computer.cuda_graphs}")

        result = ear.process_audio(audio_data)
        print(f"Result: {result}")
    except Exception as e:
        print(f"❌ process_audio failed: {e}")
        import traceback
        traceback.print_exc()

    print("🏁 Checking turn end...")
    # Force turn end by providing 0 timeout
    query = ear.check_turn_end(silence_timeout=-1)
    print(f"Final Query: {query}")

if __name__ == "__main__":
    run_verification()
