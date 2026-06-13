import asyncio
from playwright.async_api import async_playwright
import json

async def run_repro():
    print("[*] Starting Remote NetworkError Reproduction...")
    
    async with async_playwright() as p:
        # Launch browser
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # We will use a data URL to simulate a page on notes.jason-lab.dev trying to fetch pager.jason-lab.dev
        # This will simulate the cross-origin fetch
        
        html_content = """
        <html>
        <body>
            <h1>Reproduction</h1>
            <script>
                async function testFetch() {
                    console.log("[JS] Attempting fetch to https://pager.jason-lab.dev/health");
                    try {
                        const response = await fetch('https://pager.jason-lab.dev/health', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({})
                        });
                        console.log("[JS] Fetch Success: " + response.status);
                    } catch (e) {
                        console.error("[JS] Fetch Error: " + e.name + " - " + e.message);
                    }
                }
                testFetch();
            </script>
        </body>
        </html>
        """
        
        page.on("console", lambda msg: print(f"  {msg.text}"))
        
        print("[*] Navigating to simulation page...")
        # To simulate cross-origin, we can just use a local file or data URL
        # Browsers treat data URLs as unique origins, which triggers CORS
        await page.set_content(html_content)
        
        # Wait for the console error
        print("[*] Waiting for result...")
        await asyncio.sleep(5)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_repro())
