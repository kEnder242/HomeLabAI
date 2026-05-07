import requests
import json
import time
import argparse
import sys

VLLM_URL = "http://localhost:8088/v1/chat/completions"

def test_prompt(system_prompt, user_query, temperature=0.2, repetition_penalty=1.2, model="unified-base"):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_query}
        ],
        "temperature": temperature,
        "repetition_penalty": repetition_penalty,
        "max_tokens": 512,
        "stream": False
    }
    
    print(f"\n--- 🧪 Prompt Iteration Test ---")
    print(f"[CONFIG]: Temp={temperature}, Penalty={repetition_penalty}")
    print(f"[QUERY]: {user_query}")
    
    try:
        start_t = time.time()
        response = requests.post(VLLM_URL, json=payload, timeout=120)
        duration = time.time() - start_t
        
        if response.status_code == 200:
            data = response.json()
            text = data['choices'][0]['message']['content'].strip()
            print(f"[RESULT ({duration:.2f}s)]: {text}")
            
            # JSON check
            try:
                # Basic cleanup in case of preamble
                json_match = text[text.find('{'):text.rfind('}')+1]
                json.loads(json_match)
                print("[STATUS]: ✅ VALID JSON")
            except Exception as e:
                print(f"[STATUS]: ❌ INVALID JSON ({e})")
                if "!!!" in text or len(text) > 300:
                    print("[ALERT]: ☢️ GIBBERISH/LOBOTOMY DETECTED")
        else:
            print(f"[ERROR]: vLLM returned {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"[EXCEPTION]: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt-type", choices=["high-fidelity", "stabilized", "custom"], default="stabilized")
    parser.add_argument("--query", default="[ME] What was April 2017 like?")
    parser.add_argument("--temp", type=float, default=0.2)
    parser.add_argument("--penalty", type=float, default=1.2)
    args = parser.parse_args()

    PROMPTS = {
        "high-fidelity": (
            "You are The Lab Node, the Sentient Sentinel of Acme Lab.\n"
            "CORE ROLE: You overhear all interactions and provide high-fidelity situational triage.\n"
            "TASK: Return ONLY a raw JSON block.\n"
            "SCHEMA:\n"
            "{\n"
            "  \"intent\": \"STRATEGIC | RECALL | CASUAL | OPERATIONAL\",\n"
            "  \"addressed_to\": \"PINKY | BRAIN | MICE\",\n"
            "  \"vibe\": \"ARCHIVE_HISTORY | PINKY_INTERFACE | BRAIN_STRATEGY | SILICON_TELEMETRY\",\n"
            "  \"domain\": \"exp_tlm | exp_bkm | exp_for | standard\",\n"
            "  \"casual\": 0.0-1.0, \"intrigue\": 0.0-1.0, \"importance\": 0.0-1.0,\n"
            "  \"situation\": \"text\", \"hints\": \"Technical guidance\"\n"
            "}\n"
            "EXAMPLE:\n"
            "{\"intent\": \"STRATEGIC\", \"addressed_to\": \"BRAIN\", \"vibe\": \"SILICON_TELEMETRY\", \"domain\": \"exp_tlm\", \"importance\": 0.9, \"casual\": 0.0, \"intrigue\": 0.8, \"situation\": \"Telemetry query\", \"hints\": \"Check RAPL/MSR anchors\"}\n"
            "STEERAGE RULES:\n"
            "1. HIGH IMPORTANCE (1.0): Any technical query (RAPL, MSR, BKM, Silicon, NVIDIA).\n"
            "2. BRAIN ADDRESS: Complex synthesis, historical deep dives, or technical BKMs.\n"
            "3. PINKY ADDRESS: Greetings, simple facts, or casual talk.\n"
            "4. No preamble. No markdown. Output ONLY the raw JSON."
        ),
        "stabilized": (
            "You are The Lab Node sentinel. Respond ONLY with a raw JSON block.\n"
            "SCHEMA: {\"intent\": \"STRATEGIC\", \"addressed_to\": \"BRAIN\", \"vibe\": \"ARCHIVE\", \"domain\": \"standard\", \"casual\": 0.0, \"intrigue\": 1.0, \"importance\": 1.0, \"situation\": \"text\", \"hints\": \"text\"}\n"
            "RULES: 1. No preamble. 2. No markdown. 3. High importance for technical queries."
        )
    }
    
    system_prompt = PROMPTS[args.prompt_type]
    test_prompt(system_prompt, args.query, temperature=args.temp, repetition_penalty=args.penalty)
