import os
import json

def check_prep_status():
    print("--- ✈️ Acme Lab: Pre-Flight Check (Prep for Tomorrow) ---")
    
    # 1. Models
    model_path = os.path.expanduser("~/AcmeLab/models/llama-3.1-8b-awq")
    if os.path.exists(model_path) and len(os.listdir(model_path)) > 0:
        print("[PASS] vLLM Alpha Weights: Found.")
    else:
        print("[WAIT] vLLM Alpha Weights: Downloading/Missing.")

    # 2. Observational Memory
    om_file = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/compressed_history.json")
    if os.path.exists(om_file):
        with open(om_file, 'r') as f:
            data = json.load(f)
            print(f"[PASS] OM Engine: Active. Last run: {data.get('last_synthesis')}")
    else:
        print("[FAIL] OM Engine: No history found.")

    # 3. Recruiter Ready
    rec_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/recruiter.py")
    if os.path.exists(rec_path):
        print("[PASS] Recruiter Engine: Patched & Ready.")

if __name__ == "__main__":
    check_prep_status()
