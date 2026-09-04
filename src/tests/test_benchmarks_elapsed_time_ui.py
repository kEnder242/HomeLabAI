"""
[FEAT-525] Verification: Live Round Table Elapsed Time & Blackboard Drawer UI
Playwright DOM test verifying canvas chart and accordion drawer interaction.
"""
import pytest
from playwright.async_api import async_playwright

BENCHMARKS_URL = "http://localhost:9001/benchmarks.html"

@pytest.mark.asyncio
async def test_elapsed_time_tab_and_drawer():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(BENCHMARKS_URL, wait_until="domcontentloaded")

            # 1. Verify 1st tab button exists with LIVE ROUND TABLE ELAPSED TIME
            elapsed_tab_btn = page.locator("button.tab-btn:has-text('LIVE ROUND TABLE ELAPSED TIME')")
            await elapsed_tab_btn.wait_for(state="visible", timeout=5000)

            # 2. Verify tab-delta-t starts active (default tab)
            delta_pane = page.locator("#tab-delta-t")
            has_hidden = await delta_pane.evaluate("el => el.classList.contains('hidden')")
            assert not has_hidden, "Expected tab-delta-t to be visible as default active tab"

            # 3. Verify canvas exists and is rendered
            canvas = page.locator("#delta-t-chart")
            await canvas.wait_for(state="visible", timeout=5000)
            c_width = await canvas.evaluate("el => el.width")
            assert c_width >= 900, f"Expected canvas width >= 900, got {c_width}"

            # 4. Verify blackboard ledger container contains expandable turn details
            ledger_container = page.locator("#blackboard-ledger-container")
            await ledger_container.wait_for(state="visible", timeout=5000)
            
            # Wait for details elements to be rendered by JS
            await page.wait_for_selector("#blackboard-ledger-container details.feature-details", timeout=5000)
            turn_details = page.locator("#blackboard-ledger-container details.feature-details")
            count = await turn_details.count()
            assert count >= 1, f"Expected at least 1 turn in ledger, got {count}"

            # 5. Verify first turn summary format (TURN 1 • TOPIC • [SCOPE])
            first_summary = await turn_details.first.locator("summary").inner_text()
            assert "TURN" in first_summary
            assert "CONTEXT_SCOPE_LONG" in first_summary

            # 6. Verify expanded contents (Distillation Bullets & Live Elapsed Checkpoints)
            details_content = turn_details.first.locator(".details-content")
            content_text = await details_content.inner_text()
            assert "DISTILLATION BULLETS" in content_text.upper()
            assert "1-LINE CONSENSUS" in content_text.upper()
            assert "LIVE ELAPSED CHECKPOINTS" in content_text.upper()

        finally:
            await context.close()
            await browser.close()
