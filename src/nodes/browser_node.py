import logging
import sys

from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP

# Logging setup
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)

mcp = FastMCP("The Scout (Browser)")


@mcp.tool()
async def browse_url(url: str) -> str:
    """
    The Scout's Eyes: Navigate to a URL using a headless browser.
    Essential for dynamic JavaScript content analysis.
    """
    logging.info(f"[BROWSER] Navigating to {url}...")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            # Set a realistic user agent
            ua = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36"
            )
            await page.set_extra_http_headers({"User-Agent": ua})

            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Simple content extraction (Text only)
            content = await page.evaluate("() => document.body.innerText")
            await browser.close()

            # Clean up excessive whitespace
            clean_content = "\n".join(
                [line.strip() for line in content.split("\n") if line.strip()]
            )
            return clean_content[:10000]  # Return first 10k chars
    except Exception as e:
        return f"Scout Error: Failed to navigate to {url}. Reason: {e}"


if __name__ == "__main__":
    mcp.run()
