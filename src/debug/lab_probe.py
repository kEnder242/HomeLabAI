import requests
import time
import json

URL = "http://localhost:9999"

def check_lab():
    print("--- 🔬 Python Lab Probe ---")
    try:
        # 1. Start
        payload = {"engine": "vLLM", "mode": "SERVICE_UNATTENDED", "disable_ear": True}
        print(f"[SEND] /start with {payload}")
        r = requests.post(f"{URL}/start", json=payload, timeout=5)
        print(f"[RECV] {r.status_code}: {r.text}")

        # 2. Wait
        print("[WAIT] Waiting for readiness...")
        for i in range(15):
            r = requests.get(f"{URL}/heartbeat", timeout=5)
            data = r.json()
            ready = data.get("full_lab_ready")
            vllm = data.get("vllm_running")
            print(f"   [{i}] Ready: {ready} | vLLM: {vllm}")
            if ready:
                print("✅ Lab is READY.")
                return True
            time.sleep(5)
        
        print("❌ Lab timed out.")
        return False
    except Exception as e:
        print(f"❌ Probe Failed: {e}")
        return False

if __name__ == "__main__":
    check_lab()
