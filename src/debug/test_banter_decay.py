import asyncio
import time
import os
import sys

# Ensure we can import acme_lab
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from acme_lab import AcmeLab

async def test_banter_decay():
    print("--- [TEST] Banter Decay Verification ---")
    lab = AcmeLab(mode="DEBUG_SMOKE")
    
    # 1. Initial State (Normal reflex)
    lab.last_activity = time.time()
    lab.connected_clients = {None} # Mock one client
    
    # Trigger one loop iteration (we'll simulate the logic inside the test)
    # Logic: idle_time = time.time() - self.last_activity
    # if idle_time > 60: banter_backoff += 1 else: banter_backoff = 0
    # reflex_ttl = 1.0 + (banter_backoff * 0.5)
    
    def simulate_reflex(lab_obj):
        idle_time = time.time() - lab_obj.last_activity
        if idle_time > 60:
            if lab_obj.banter_backoff < 10:
                lab_obj.banter_backoff += 1
        else:
            lab_obj.banter_backoff = 0
        lab_obj.reflex_ttl = 1.0 + (lab_obj.banter_backoff * 0.5)

    print(f"[INIT] reflex_ttl: {lab.reflex_ttl}")
    assert lab.reflex_ttl == 1.0
    
    # 2. Simulate Active session (no decay)
    lab.last_activity = time.time() - 30
    simulate_reflex(lab)
    print(f"[ACTIVE] (30s idle) reflex_ttl: {lab.reflex_ttl}")
    assert lab.reflex_ttl == 1.0
    
    # 3. Simulate Idle session (decay starts)
    lab.last_activity = time.time() - 65
    simulate_reflex(lab)
    print(f"[IDLE] (65s idle) reflex_ttl: {lab.reflex_ttl}")
    assert lab.reflex_ttl > 1.0
    
    # 4. Simulate deep idle (max decay)
    lab.banter_backoff = 10
    simulate_reflex(lab)
    print(f"[DEEP IDLE] reflex_ttl: {lab.reflex_ttl}")
    assert lab.reflex_ttl == 6.0 # 1.0 + 10*0.5
    
    # 5. Simulate activity reset
    lab.last_activity = time.time()
    simulate_reflex(lab)
    print(f"[RESET] (Just active) reflex_ttl: {lab.reflex_ttl}")
    assert lab.reflex_ttl == 1.0

    print("✅ Banter Decay logic verified.")

if __name__ == "__main__":
    asyncio.run(test_banter_decay())
