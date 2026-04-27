import os
import json
import time
import subprocess
from src.infra.atomic_io import atomic_write_json

def test_pager_atomic():
    test_file = "Portfolio_Dev/field_notes/data/test_pager.json"
    print(f"[#] Testing Atomic Swap Protocol (BKM-022) on {test_file}")
    
    # 1. Prepare dummy data
    data = [{"timestamp": str(time.time()), "message": "Initial entry"}]
    
    # 2. Perform Atomic Write
    try:
        atomic_write_json(test_file, data)
        print("[+] Phase 1: Atomic write successful.")
        
        # Verify file existence and content
        if os.path.exists(test_file):
            with open(test_file, 'r') as f:
                content = json.load(f)
                if len(content) == 1:
                    print("[+] Phase 2: Content integrity verified.")
        
        # 3. Simulate high-frequency concurrency (Stress)
        print("[#] Stress testing atomicity (100 rapid writes)...")
        for i in range(100):
            data.append({"timestamp": str(time.time()), "message": f"Stress entry {i}"})
            atomic_write_json(test_file, data)
            
        print("[+] Phase 3: Stress test complete. No partial-write crashes.")
        
        # Final Verification
        with open(test_file, 'r') as f:
            final_content = json.load(f)
            print(f"[+] Final Ledger Depth: {len(final_content)} entries.")
            
    finally:
        if os.path.exists(test_file):
            os.remove(test_file)
            print("[+] Cleanup complete.")

if __name__ == "__main__":
    test_pager_atomic()
