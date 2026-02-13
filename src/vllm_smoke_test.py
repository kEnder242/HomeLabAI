import requests
import time

URL = "http://localhost:8088/v1/completions"

def smoke_test():
    print("--- vLLM + Liger Smoke Test ---")
    payload = {
        "model": "TheBloke/Mistral-7B-Instruct-v0.2-AWQ",
        "prompt": "Narf! What is the meaning of life?",
        "max_tokens": 50,
        "temperature": 0.1
    }

    start_time = time.time()
    try:
        print(f"Sending request to {URL}...")
        resp = requests.post(URL, json=payload, timeout=120)
        if resp.status_code == 200:
            data = resp.json()
            text = data['choices'][0]['text']
            latency = time.time() - start_time
            print(f"✅ SUCCESS ({latency:.2f}s)")
            print(f"Response: {text.strip()}")
        else:
            print(f"❌ FAILED ({resp.status_code}): {resp.text}")
    except Exception as e:
        print(f"❌ ERROR: {e}")

if __name__ == "__main__":
    smoke_test()
