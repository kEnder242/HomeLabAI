import os
import asyncio
import json
import logging
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

try:
    from nodes.loader import BicameralNode
except ImportError:
    from loader import BicameralNode

BROWSER_SYSTEM_PROMPT = (
    "You are the Browser Node, 'The Scout'. IDENTITY: Web Acquisition Operative. "
    "ROLE: High-fidelity web scraper and content extractor. "
    "CONTEXT: You specialize in bypassing anti-bot measures (within ethical bounds) "
    "to extract clean Job Descriptions (JDs) for the Recruiter node. "
    "CORE DIRECTIVE: Provide clean, unformatted text or markdown of the target content."
)

node = BicameralNode("Browser", BROWSER_SYSTEM_PROMPT)
mcp = node.mcp

@mcp.tool()
async def browse_url(url: str) -> str:
    """Extracts clean text/markdown from a job board page or any URL."""
    logging.info(f"[BROWSER] Navigating to: {url}")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True)
            # Use a real-looking UA to avoid simple bot detection
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Set a reasonable timeout
            await page.goto(url, wait_until="networkidle", timeout=45000)
            
            # Wait a bit for any dynamic content
            await asyncio.sleep(2)
            
            content = await page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove scripts, styles, and other noise
            for s in soup(['script', 'style', 'nav', 'footer', 'header', 'iframe', 'noscript']):
                s.decompose()
            
            # Get text and clean it
            text = soup.get_text(separator='\n')
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = '\n'.join(lines)
            
            await browser.close()
            
            # Return a reasonable chunk
            return clean_text[:10000] # Cap at 10k chars for sanity
            
        except Exception as e:
            logging.error(f"[BROWSER] Error browsing {url}: {e}")
            return f"Error: Failed to fetch {url}. Exception: {str(e)}"

@mcp.tool()
async def ping_engine(force: bool = False) -> str:
    """[FEAT-192] Verify and force engine readiness."""
    success, msg = await node.ping_engine(force=force)
    return json.dumps({"success": success, "message": msg})

if __name__ == "__main__":
    node.run()
