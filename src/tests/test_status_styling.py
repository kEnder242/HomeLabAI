import pytest
from playwright.async_api import async_playwright

@pytest.mark.asyncio
async def test_status_log_styles():
    """
    Launches status.html in Playwright and asserts:
    1. .system-inline element color resolves to dark grey (#555 or rgb(85, 85, 85))
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Go to status.html
        await page.goto("http://localhost:9001/status.html")
        print(f"[Test] Loaded status page: {page.url}")
        
        # Inject a dummy system log message to test the color computed style
        color = await page.evaluate("""() => {
            const el = document.createElement('div');
            el.className = 'msg-body system-inline';
            el.innerText = 'Test system log';
            document.body.appendChild(el);
            const style = window.getComputedStyle(el);
            const c = style.color;
            document.body.removeChild(el);
            return c;
        }""")
        
        print(f"[Test] Computed system-inline color: {color}")
        # color should be rgb(85, 85, 85) which is #555
        assert color in ["rgb(85, 85, 85)", "#555", "#555555"], f"Incorrect color style: {color}"
        
        print("✅ [PASS] CSS system-inline color formatting is correct.")
        await browser.close()
