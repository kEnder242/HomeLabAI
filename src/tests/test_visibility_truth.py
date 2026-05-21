import asyncio
import os
from playwright.async_api import async_playwright

async def test_ui_transparency():
    """
    [FEAT-364] UI Truth Verification: Physically verify that thoughts and system 
    milestones are visible in the Intercom DOM.
    """
    print("--- [FEAT-364] STARTING UI TRUTH VERIFICATION ---")
    
    async with async_playwright() as p:
        # Connect to existing lab instance if possible, or just observe the UI
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # 1. Navigate to Intercom
        # Using localhost since we are running on the Z87 host
        url = "http://localhost:9001/intercom.html"
        print(f"[*] Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=10000)
        except Exception as e:
            print(f"[-] Could not reach Intercom UI: {e}")
            await browser.close()
            return

        # 2. Trigger a Lab Start via the UI or REST (simulating user interaction)
        # For this test, we will just monitor the console for a few minutes
        # if the lab is already warming.
        
        print("[*] Monitoring Intercom consoles for 60s...")
        
        system_milestones_seen = []
        pinky_thoughts_seen = []
        
        for _ in range(30): # 60 seconds
            # Check Chat Console (Pinky)
            chat_content = await page.inner_text("#chat-console")
            if "Narf" in chat_content or "<thought>" in chat_content:
                if not pinky_thoughts_seen:
                    print("[+] PINKY VOICE DETECTED in Chat Console.")
                    pinky_thoughts_seen.append(True)
            
            # Check Insight Console (System/Shadow/Brain)
            insight_content = await page.inner_text("#insight-console")
            if "[SYSTEM]" in insight_content or "Step" in insight_content:
                if not system_milestones_seen:
                    print("[+] SYSTEM MILESTONES DETECTED in Insight Console.")
                    system_milestones_seen.append(True)
            
            if pinky_thoughts_seen and system_milestones_seen:
                break
                
            await asyncio.sleep(2)
        
        # 3. Final Verdict
        print("\n--- UI TRUTH REPORT ---")
        print(f"Pinky Visibility: {'✅ PASS' if pinky_thoughts_seen else '❌ FAIL'}")
        print(f"System Milestone Visibility: {'✅ PASS' if system_milestones_seen else '❌ FAIL'}")
        
        if not pinky_thoughts_seen or not system_milestones_seen:
            # Take a screenshot for forensic audit
            os.makedirs("HomeLabAI/logs/screenshots", exist_ok=True)
            path = "HomeLabAI/logs/screenshots/visibility_fail.png"
            await page.screenshot(path=path)
            print(f"[!] Forensic screenshot saved to {path}")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_ui_transparency())
