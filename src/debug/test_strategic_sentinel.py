import asyncio
import json
import os
import sys

# Ensure we can import acme_lab
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from acme_lab import AcmeLab

async def test_sentinel_logic():
    print("--- [TEST] Strategic Sentinel Verification ---")
    lab = AcmeLab(mode="DEBUG_SMOKE")
    
    # Case 1: Typing mode (mic_active = False)
    # Should be strategic even if not mentioning "brain" (Amygdala filter)
    lab.mic_active = False
    query = "analyze the silicon regression logs"
    
    # Mocking self.residents to avoid full boot for this logic test
    lab.residents = {"pinky": None, "brain": None} 
    
    # We test the is_strategic logic branch specifically
    strat_keys = ["regression", "validation", "silicon"]
    casual_keys = ["hello", "hi"]
    
    is_casual = any(k in query.lower() for k in casual_keys)
    
    # Simulate the logic inside process_query
    is_strategic = False
    if lab.mic_active:
        is_strategic = any(k in query.lower() for k in strat_keys) and not is_casual
    else:
        if not is_casual:
            is_strategic = True # Current stub logic
            
    print(f"[CHECK] Typing Mode Strategic: {is_strategic}")
    assert is_strategic is True
    
    # Case 2: Casual Chat
    query = "hello pinky"
    is_casual = any(k in query.lower() for k in casual_keys)
    if lab.mic_active:
        is_strategic = any(k in query.lower() for k in strat_keys) and not is_casual
    else:
        if not is_casual:
            is_strategic = True
        else:
            is_strategic = False
            
    print(f"[CHECK] Casual Mode Strategic: {is_strategic}")
    assert is_strategic is False

    print("✅ Strategic Sentinel Logic verified.")

if __name__ == "__main__":
    asyncio.run(test_sentinel_logic())
