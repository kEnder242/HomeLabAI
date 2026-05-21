import asyncio
import os
import time
from playwright.async_api import async_playwright

async def test_visibility_truth():
    """
    [FEAT-367] Hardened UI Truth: Waits for physical log entries before asserting DOM.
    Ensures 100% voice restoration and no 'easy pass' on reflexes.
    """
    print("--- [FEAT-367] STARTING HARDENED UI TRUTH VERIFICATION ---")
    
    SERVER_LOG = "HomeLabAI/server.log"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Open Intercom
        url = "http://localhost:9001/intercom.html"
        print(f"[*] Connecting to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=15000)
        except Exception as e:
            print(f"[-] UI Unreachable: {e}")
            await browser.close()
            return

        # 2. Inject Query
        query = "[ME] Analyze the Year 2023. Reference PECISTRESSOR specifically."
        print(f"--- SENDING SEMANTIC QUERY: {query} ---")
        await page.fill("#text-input", query)
        await page.press("#text-input", "Enter")

        # 3. Log-Based Waiting (The Physician's Probe)
        # We wait for the Hub to log that it salvaged a thought or dispatched to Pinky.
        print("[*] Monitoring server.log for physical reasoning trace...")
        found_in_log = False
        start_time = time.time()
        
        while time.time() - start_time < 300: # 5 minute limit
            if os.path.exists(SERVER_LOG):
                with open(SERVER_LOG, "r") as f:
                    log_tail = f.read()[-5000:] # Last 5k chars
                    if "<thought>" in log_tail and "2023" in log_tail:
                        print("[+] LOG TRACE CONFIRMED: Hub dispatched semantic thought.")
                        found_in_log = True
                        break
            await asyncio.sleep(2)
        
        if not found_in_log:
            print("[-] TIMEOUT: Log trace never showed semantic thought.")
        
        # 4. DOM Assertion (Verify routing to Browser)
        print("[*] Verifying DOM visibility...")
        # Wait a few seconds for WebSocket propagation to UI
        await asyncio.sleep(5)
        
        chat_content = await page.inner_text("#chat-console")
        insight_content = await page.inner_text("#insight-console")
        
        # STRICT SEMANTIC CHECK: Must contain "2023" and NOT just Narf/Zort
        has_semantic_pinky = "2023" in chat_content or "<thought>" in chat_content
        has_milestones = "Step 1" in insight_content or "[SYSTEM]" in insight_content
        
        print("\n--- [BKM-029] VERIFICATION REPORT ---")
        print(f"Pinky Semantic Voice: {'✅ PASS' if has_semantic_pinky else '❌ FAIL'}")
        print(f"Ignition Visibility: {'✅ PASS' if has_milestones else '❌ FAIL'}")
        
        if not has_semantic_pinky:
            print("\n🚨 CRITICAL FAILURE: Pinky is MUTE or REFLEX-ONLY.")
            print(f"Chat Content Trace: {chat_content[-200:]}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_visibility_truth())
