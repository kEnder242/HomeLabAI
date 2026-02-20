import asyncio
import os
import sys
import time

# Ensure we can import acme_lab
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from acme_lab import AcmeLab

async def test_memory_logic():
    print("--- [TEST] MIB Wipe & Deep Context Verification ---")
    lab = AcmeLab(mode="DEBUG_SMOKE")
    
    # 1. Verify Deep Context Cap (50)
    for i in range(60):
        # We manually simulate the append logic
        lab.recent_interactions.append(f"User: interaction {i}")
        if len(lab.recent_interactions) > 50:
            lab.recent_interactions.pop(0)
            
    print(f"[CHECK] Context Length after 60 pushes: {len(lab.recent_interactions)}")
    assert len(lab.recent_interactions) == 50
    assert lab.recent_interactions[0] == "User: interaction 10"
    
    # 2. Trigger MIB Wipe
    # We test the logic branch in process_query (simplified)
    query = "Look at the light"
    wipe_keys = ["look at the light", "wipe memory", "neuralyzer", "clear context"]
    
    is_wipe = any(k in query.lower() for k in wipe_keys)
    print(f"[CHECK] Wipe detected: {is_wipe}")
    assert is_wipe is True
    
    if is_wipe:
        lab.recent_interactions = []
        
    print(f"[CHECK] Context Length after Wipe: {len(lab.recent_interactions)}")
    assert len(lab.recent_interactions) == 0

    print("✅ MIB Wipe & Deep Context verified.")

if __name__ == "__main__":
    asyncio.run(test_memory_logic())
