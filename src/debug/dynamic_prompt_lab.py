import requests
import json
import time
import os
import argparse
import sys

VLLM_URL = "http://localhost:8088/v1/chat/completions"
LAB_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_FILE = os.path.join(os.path.dirname(__file__), "active_prompt.json")

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return {
        "system": "You are a helpful assistant.",
        "user": "Hello!",
        "temperature": 0.2,
        "repetition_penalty": 1.2,
        "model": "unified-base"
    }

def run_test(config):
    payload = {
        "model": config.get("model", "unified-base"),
        "messages": [
            {"role": "system", "content": config["system"]},
            {"role": "user", "content": config["user"]}
        ],
        "temperature": config.get("temperature", 0.2),
        "repetition_penalty": config.get("repetition_penalty", 1.2),
        "max_tokens": 512,
        "stream": False
    }
    
    print(f"\n{'='*60}")
    print(f"🧪 DYNAMIC PROMPT TEST")
    print(f"{'='*60}")
    print(f"[SYSTEM]: {config['system'][:100]}...")
    print(f"[USER]:   {config['user']}")
    print(f"[PARAMS]: Temp={payload['temperature']}, Penalty={payload['repetition_penalty']}")
    
    try:
        start_t = time.time()
        response = requests.post(VLLM_URL, json=payload, timeout=120)
        duration = time.time() - start_t
        
        if response.status_code == 200:
            data = response.json()
            text = data['choices'][0]['message']['content'].strip()
            print(f"\n--- 🤖 RESPONSE ({duration:.2f}s) ---")
            print(text)
            print("-" * 30)
            
            # Sanity Audit
            if "!!!" in text:
                print("⚠️  CRITICAL: GIBBERISH DETECTED (Exclamation marks)")
            if len(text) > 400 and text.count(' ') < len(text) / 10:
                print("⚠️  CRITICAL: LOBOTOMY DETECTED (No whitespace/Raw tokens)")
                
            try:
                json_match = text[text.find('{'):text.rfind('}')+1]
                if json_match:
                    json.loads(json_match)
                    print("✅ VALID JSON DETECTED")
                else:
                    print("❌ NO JSON FOUND")
            except Exception as e:
                print(f"❌ INVALID JSON: {e}")
        else:
            print(f"❌ ERROR {response.status_code}: {response.text}")
            
    except Exception as e:
        print(f"❌ EXCEPTION: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--user", help="Override user query")
    parser.add_argument("--temp", type=float, help="Override temperature")
    parser.add_argument("--penalty", type=float, help="Override repetition penalty")
    args = parser.parse_args()

    config = load_config()
    
    if args.system: config["system"] = args.system
    if args.user: config["user"] = args.user
    if args.temp is not None: config["temperature"] = args.temp
    if args.penalty is not None: config["repetition_penalty"] = args.penalty
    
    run_test(config)
