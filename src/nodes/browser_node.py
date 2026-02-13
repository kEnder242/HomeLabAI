from mcp.server.fastmcp import FastMCP
import logging
import sys
import os
import asyncio
from playwright.async_api import async_playwright

# Logging setup
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("The Scout (Browser)")

@mcp.tool()
async def browse_url(url: str) -> str:
    """
    The Scout's Eyes: Navigate to a URL using a high-fidelity headless browser. 
    Essential for bypassing anti-bot measures on job boards and capturing 
    dynamic JavaScript content for analysis.
    """
    logging.info(f"[BROWSER] Navigating to {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Set a realistic user agent
            await page.set_extra_http_headers({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})
            
            await page.goto(url, wait_until="networkidle", timeout=30000)
            
            # Simple content extraction (Text only)
            content = await page.evaluate("() => document.body.innerText")
            await browser.close()
            
            # Clean up excessive whitespace
            clean_content = "\\n".join([line.strip() for line in content.split("\\n") if line.strip()])
            return clean_content[:10000] # Return first 10k chars
    except Exception as e:
        return f"Scout Error: Failed to navigate to {url}. Reason: {e}"

if __name__ == "__main__":
    mcp.run()
