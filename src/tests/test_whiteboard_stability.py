import pytest
import psutil
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_whiteboard_save_stability():
    """
    Simulates saving the whiteboard via Playwright and asserts:
    1. The server PID remains identical.
    2. The WebSocket connection remains open.
    """
    # 1. Locate the running Foyer server process PID by name
    initial_pid = None
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] == 'acme_foyer_v5':
            initial_pid = proc.info['pid']
            break
    if initial_pid is None:
        for proc in psutil.process_iter(['pid', 'cmdline']):
            cmdline = proc.info['cmdline']
            if cmdline and any('acme_lab.py' in part for part in cmdline):
                initial_pid = proc.info['pid']
                break
                
    assert initial_pid is not None, "Foyer server process not found."
    print(f"[Test] Found initial Foyer PID: {initial_pid}")
    
    # 2. Launch Playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Capture console messages
        page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
        
        # Go to the local intercom site
        await page.goto("http://localhost:9001/intercom.html")
        print(f"[Test] Loaded URL: {page.url}")
        
        # Wait 5 seconds for workspace WebSocket connection to be established
        await page.wait_for_timeout(5000)
        
        # Let's inspect window.ws
        ws_defined = await page.evaluate("() => typeof window.ws !== 'undefined'")
        print(f"[Test] window.ws defined: {ws_defined}")
        if ws_defined:
            ws_state = await page.evaluate("() => window.ws.readyState")
            print(f"[Test] window.ws readyState: {ws_state}")
        
        # 3. Simulate saving whiteboard.md
        print("[Test] Simulating whiteboard save event...")
        await page.evaluate("""() => {
            const socket = window.ws;
            if (socket && socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({
                    type: "workspace_save",
                    filename: "whiteboard.md",
                    content: "## Whiteboard Test\\nStabilization validated."
                }));
            } else {
                throw new Error("WebSocket not open in browser window.");
            }
        }""")
        
        # Wait 8 seconds to allow any potential file watch restart to trigger
        await page.wait_for_timeout(8000)
        
        # 4. Assertions
        current_pid = None
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'] == 'acme_foyer_v5':
                current_pid = proc.info['pid']
                break
        if current_pid is None:
            for proc in psutil.process_iter(['pid', 'cmdline']):
                cmdline = proc.info['cmdline']
                if cmdline and any('acme_lab.py' in part for part in cmdline):
                    current_pid = proc.info['pid']
                    break
                    
        assert current_pid == initial_pid, f"PID changed from {initial_pid} to {current_pid}!"
        
        socket_state = await page.evaluate("() => window.ws ? window.ws.readyState : -1")
        assert socket_state == 1, f"WebSocket closed! State: {socket_state}"
        
        print("✅ [PASS] Whiteboard save stability test passed successfully.")
        await browser.close()
