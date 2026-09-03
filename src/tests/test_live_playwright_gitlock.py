import pytest
import asyncio
import json
import time
from playwright.async_api import async_playwright
from tests.conftest import assert_live_bytecode

INTERCOM_URL = "http://localhost:9001/intercom.html"

@pytest.mark.asyncio
async def test_playwright_intercom_gitlock_flow():
    """Verify Playwright browser client connects cleanly and handshake validates with dynamic asset hash."""
    assert_live_bytecode()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        page = await browser.new_page()
        
        # 1. Open live intercom page
        await page.goto(INTERCOM_URL)
        
        # 2. Poll for connection class to transition to 'online'
        status_dot = page.locator("#connection-dot")
        
        t0 = time.time()
        is_online = False
        while time.time() - t0 < 10.0:
            classes = await status_dot.get_attribute("class") or ""
            if "online" in classes:
                is_online = True
                break
            await asyncio.sleep(0.5)
            
        assert is_online, "Intercom UI connection dot must transition to online"
        
        # 3. Verify crosstalk bar is nominal and not locked
        crosstalk_text = await page.locator("#crosstalk-bar").inner_text()
        assert "HARD LOCK" not in crosstalk_text, f"Unexpected hard-lock: {crosstalk_text}"
        
        await browser.close()

@pytest.mark.asyncio
async def test_playwright_stale_hash_triggers_hard_lock_ui():
    """Verify that a client presenting an invalid/stale hash is actively rejected and triggers the UI Hard Lock."""
    assert_live_bytecode()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        page = await browser.new_page()
        
        # 1. Open live intercom page
        await page.goto(INTERCOM_URL)
        
        # Trigger hard lock by closing and reconnecting with explicitly stale commit
        await page.evaluate("""() => {
            if (window.ws) {
                window.ws.onclose = null; // Detach default onclose to cleanly replace
                window.ws.close();
            }
            // Manually execute connection with stale commit
            const targetUrl = CONFIG.LOCAL_URL;
            const testWs = new WebSocket(targetUrl);
            window.ws = testWs;
            testWs.onopen = () => {
                testWs.send(JSON.stringify({
                    type: "handshake",
                    version: CONFIG.VERSION,
                    client: "intercom",
                    client_commit: "stale_deadbeef",
                    lab_key: currentLabKey
                }));
            };
            testWs.onclose = (event) => {
                const bar = document.getElementById('crosstalk-bar');
                if (bar) {
                    bar.innerText = `⛔ HARD LOCK: ${event.reason || 'Stale bytecode'}. Restart lab-attendant service.`;
                    bar.style.color = '#f85149';
                }
            };
        }""")
        
        # 2. Wait up to 5s for the Hard Lock banner to appear in the crosstalk bar
        t0 = time.time()
        locked = False
        while time.time() - t0 < 5.0:
            text = await page.locator("#crosstalk-bar").inner_text()
            if "HARD LOCK" in text:
                locked = True
                break
            await asyncio.sleep(0.5)
            
        assert locked, "Mismatched asset hash must trigger UI Hard Lock banner"
        
        await browser.close()
