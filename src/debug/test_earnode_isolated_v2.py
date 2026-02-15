import numpy as np
import sys
import os
import logging
import torch

# Set up logging to stdout
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from equipment.ear_node import EarNode

def dummy_callback(text):
    print(f"Transcript: {text}")

def run_verification():
    print("🚀 Initializing EarNode...")
    try:
        # Override SILENCE_THRESHOLD for testing
        import equipment.ear_node
        equipment.ear_node.SILENCE_THRESHOLD = 1
        
        ear = EarNode(callback=dummy_callback)
    except Exception as e:
        print(f"❌ Failed to initialize EarNode: {e}")
        return

    print("🔊 Generating complex loud white noise (broadband)...")
    sample_rate = 16000
    duration = 5 # Longer duration
    # High amplitude noise
    audio_data = np.random.randint(-25000, 25000, size=sample_rate * duration, dtype=np.int16)

    print("🧠 Running process_audio...")
    audio_float = audio_data.astype(np.float32) / 32768.0
    
    with torch.no_grad():
        # Using the actual process_audio call to verify the full stack inside ear_node
        res = ear.process_audio(audio_data)
        print(f"DEBUG: process_audio result: {res}")
        
        # Also direct model check
        hypotheses = ear.model.transcribe(audio=[audio_float], verbose=True)
        print(f"DEBUG: Raw Hypotheses: {hypotheses}")

    if hypotheses and len(hypotheses) > 0 and hypotheses[0]:
        hyp = hypotheses[0]
        if isinstance(hyp, list): hyp = hyp[0]
        txt = getattr(hyp, 'text', str(hyp))
        print(f"SUCCESS: Transcribed text: '{txt}'")
        if txt.strip() != "" or len(hyp.y_sequence) > 0:
            print("✅ POSITIVE INDICATION: Model is parsing audio signal into tokens.")
        else:
            print("⚠️ Model produced empty text, but pipeline is live.")
    else:
        print("❌ Model returned NO hypotheses.")

if __name__ == "__main__":
    run_verification()
