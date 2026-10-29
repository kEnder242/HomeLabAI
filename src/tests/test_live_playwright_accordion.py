import asyncio
import json
import pytest
from playwright.async_api import async_playwright

INTERCOM_URL = "http://localhost:9001/intercom.html"


@pytest.mark.asyncio
async def test_live_playwright_rag_accordion():
    """Verify that rag_eval packets render as interactive <details class="rag-eval-card"> HTML elements

    and clicking <summary> expands the archive excerpt cleanly.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = await browser.new_page()
        await page.goto(INTERCOM_URL)

        # Wait for page scripts to load and websocket to mount
        await page.wait_for_function("() => window.ws !== undefined")

        # Inject simulated rag_eval packet
        payload = {
            "type": "rag_eval",
            "doc_id": "DOC-RAPL-2020",
            "n_results": 3,
            "tier": "1",
            "full_context": "Historical RAPL engagement recorded on May 11, 2020 for PECI framework.",
            "query": "When did I start working on RAPL?",
            "channel": "chat",
        }

        await page.evaluate(
            """(data) => {
            window.ws.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
        }""",
            payload,
        )

        # 1. Assert the accordion element exists as a real DOM node
        card = page.locator(".rag-eval-card")
        await card.wait_for(state="attached", timeout=5000)

        tag_name = await card.evaluate("el => el.tagName.toLowerCase()")
        assert tag_name == "details", f"Expected <details> element, but got <{tag_name}>"

        # Verify not escaped inside <pre><code>
        escaped_pre = page.locator("pre:has-text('&lt;details')")
        assert await escaped_pre.count() == 0, "RAG eval card was mistakenly HTML-escaped inside <pre>!"

        # 2. Check initial collapsed state
        is_open_initial = await card.evaluate("el => el.hasAttribute('open')")
        assert not is_open_initial, "RAG eval accordion should initially be collapsed"

        # 3. Verify summary content
        summary = card.locator("summary")
        summary_text = await summary.text_content()
        assert "Ref: DOC-RAPL-2020" in summary_text
        assert "[Tier: 1]" in summary_text

        # 4. Click summary to expand
        await summary.click()

        # 5. Verify expanded state and archive text visibility
        is_open_after = await card.evaluate("el => el.hasAttribute('open')")
        assert is_open_after, "RAG eval accordion should be open after clicking summary"

        body_pre = card.locator(".rag-eval-body pre")
        body_text = await body_pre.text_content()
        assert "Historical RAPL engagement recorded on May 11, 2020" in body_text

        await browser.close()


@pytest.mark.asyncio
async def test_live_playwright_brain_chunks_accordion():
    """[Story 108.26 / FEAT-671] Verify Brain's chunk evaluation renders as a collapsible accordion on Right Console."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        page = await browser.new_page()
        await page.goto(INTERCOM_URL)

        # Wait for page scripts to load and websocket to mount
        await page.wait_for_function("() => window.ws !== undefined")

        # Inject simulated Brain thought_stream final packet with CHUNK evaluation
        brain_analysis = (
            "[ANALYSIS]\n"
            "- CHUNK-1: Verified historical RAPL initiation on May 11, 2020 for PECI framework => KEEP\n"
            "- CHUNK-2: Tangential thermal daemon documentation => DROP\n"
            "[BEDROCK SELECTION]\n"
            "- CHUNK-1: KEEP"
        )
        payload = {
            "type": "thought_stream",
            "token": brain_analysis,
            "brain": brain_analysis,
            "source": "Brain (Archive)",
            "brain_source": "Brain (Archive)",
            "channel": "insight",
            "console": "Right",
            "final": True,
        }

        await page.evaluate(
            """(data) => {
            window.ws.onmessage(new MessageEvent('message', { data: JSON.stringify(data) }));
        }""",
            payload,
        )

        # 1. Assert Brain chunk card exists inside insight console (Right Console)
        insight_console = page.locator("#insight-console")
        card = insight_console.locator(".brain-chunk-card")
        await card.wait_for(state="attached", timeout=5000)

        tag_name = await card.evaluate("el => el.tagName.toLowerCase()")
        assert tag_name == "details", f"Expected <details> element, but got <{tag_name}>"

        # 2. Check summary text mentions evaluated chunks count
        summary = card.locator("summary")
        summary_text = await summary.text_content()
        assert "Evidence Chunks" in summary_text
        assert "2 evaluated" in summary_text

        # 3. Check initial collapsed state
        is_open_initial = await card.evaluate("el => el.hasAttribute('open')")
        assert not is_open_initial, "Brain chunks accordion should initially be collapsed"

        # 4. Click to expand
        await summary.click()
        is_open_after = await card.evaluate("el => el.hasAttribute('open')")
        assert is_open_after, "Brain chunks accordion should be open after clicking summary"

        # 5. Check chunk text visibility
        pre = card.locator(".rag-eval-body pre")
        pre_text = await pre.text_content()
        assert "CHUNK-1: Verified historical RAPL initiation" in pre_text

        await browser.close()
