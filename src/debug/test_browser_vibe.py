import asyncio
from playwright.async_api import async_playwright
import subprocess
import time
import os

# --- Paths ---
INTERCOM_URL = "http://localhost:9001/intercom.html" # Assuming field-notes is running on 9001
STYLE_CSS = "/home/jallred/Dev_Lab/Portfolio_Dev/field_notes/style.css"

def get_key():
    import hashlib
    try:
        with open(STYLE_CSS, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except:
        return "none"

async def run_browser_simulation():
    print("[*] Starting Playwright Browser Simulation...")
    key = get_key()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # 1. Start Lab (Cold Start)
        print("[*] Triggering Lab Ignition (VLLM)...")
        subprocess.run(["curl", "-X", "POST", f"http://localhost:9999/start?key={key}", "-H", "Content-Type: application/json", "-d", '{"engine": "OLLAMA", "model": "MEDIUM", "reason": "BROWSER_SIM"}'])
        
        # 2. Navigate to Intercom immediately
        print(f"[*] Navigating to {INTERCOM_URL}")
        await page.goto(INTERCOM_URL)
        
        # Monitor console for "trash" errors
        logs = []
        page.on("console", lambda msg: logs.append(f"[JS] {msg.text}"))
        
        # 3. Simulate "Impatient" User
        print("[*] Waiting for connection dot...")
        await page.wait_for_selector("#connection-dot.online", timeout=20000)
        
        print("[*] Typing 'hi' while in INIT state...")
        await page.fill("#text-input", "hi")
        await page.keyboard.press("Enter")
        
        # 4. Monitor for the "Thinking Stall"
        print("[*] Monitoring for responses (60s window)...")
        found_thinking = False
        found_operational = False
        found_response = False
        
        for _ in range(60):
            content = await page.content()
            status_text = await page.inner_text("#crosstalk-bar")
            
            if "THINKING" in status_text:
                if not found_thinking:
                    print("[+] UI detected 🧠 THINKING status.")
                    found_thinking = True
            
            if "OPERATIONAL" in status_text:
                if not found_operational:
                    print("[+] UI detected ⚡ Mind is OPERATIONAL.")
                    found_operational = True

            # Look for Pinky's response in the console
            if "Pinky" in content or "Brain" in content:
                if "hi" not in content: # Avoid seeing our own query
                     print("[+] SUCCESS: Received cognitive response in browser!")
                     found_response = True
                     break
            
            await asyncio.sleep(1)
            
        if not found_response:
            print("[-] FAILURE: No cognitive response received. Stall detected.")
            # Print last 5 JS logs for debugging
            for log in logs[-5:]:
                print(log)
        
        await browser.close()
        return found_response

if __name__ == "__main__":
    asyncio.run(run_browser_simulation())
