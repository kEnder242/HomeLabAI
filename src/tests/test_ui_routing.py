import asyncio
import time
import requests
from playwright.async_api import async_playwright

async def test_ui_routing():
    """[Task 17.4] Verify routing fidelity to #insight-console and #chat-console."""
    print("--- [Task 17.4] STARTING UI ROUTING VERIFICATION ---")
    
    # 0. Ensure Lab is Woken
    requests.post("http://localhost:8765/wake")
    
    # Wait until it is OPERATIONAL
    for _ in range(30):
        try:
            status = requests.get("http://localhost:8765/status", timeout=2).json()
            if status.get("state") in ["READY", "OPERATIONAL"]:
                print("Lab is OPERATIONAL")
                break
        except Exception:
            pass
        time.sleep(2)
        
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        url = "http://localhost:9001/intercom.html"
        print(f"[*] Connecting to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception as e:
            print(f"[-] UI Unreachable: {e}")
            await browser.close()
            return
        
        # 1. Send query
        query = "[ME] What are the core parameters of your architecture? Provide technical deep dive."
        print(f"[*] Sending query: {query}")
        await page.fill("#text-input", query)
        await page.press("#text-input", "Enter")
        
        # 2. Wait for responses
        print("[*] Waiting for Deep Thought priming and Pinky/Brain response...")
        insight_received = False
        chat_received = False
        
        for _ in range(30):
            insight_content = await page.inner_text("#insight-console")
            chat_content = await page.inner_text("#chat-console")
            
            # Check for priming / analytical quip in insight
            if "deep thought" in insight_content.lower() or "[thinking]" in insight_content.lower():
                insight_received = True
                
            # Check for Pinky response in chat
            if "Pinky" in chat_content or "Narf" in chat_content or "Poit" in chat_content or len(chat_content) > 500:
                chat_received = True
                
            if insight_received and chat_received:
                break
                
            await asyncio.sleep(2)
            
        print("\n--- ROUTING REPORT ---")
        print(f"Insight Channel Active (Deep Thought/Priming): {'✅ PASS' if insight_received else '❌ FAIL'}")
        print(f"Chat Channel Active (Pinky): {'✅ PASS' if chat_received else '❌ FAIL'}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ui_routing())
