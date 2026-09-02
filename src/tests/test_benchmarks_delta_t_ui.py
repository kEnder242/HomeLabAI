"""
[FEAT-525] Verification: Round Table Delta-T Telemetry & Blackboard Drawer UI
Playwright DOM test verifying canvas chart and accordion drawer interaction.
"""
import pytest
from playwright.async_api import async_playwright

BENCHMARKS_URL = "http://localhost:9001/benchmarks.html"

@pytest.mark.asyncio
async def test_delta_t_telemetry_tab_and_drawer():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
        )
        context = await browser.new_context()
        page = await context.new_page()

        try:
            await page.goto(BENCHMARKS_URL, wait_until="domcontentloaded")

            # 1. Verify 4th tab button exists
            delta_tab_btn = page.locator("button.tab-btn:has-text('ROUND TABLE DELTA-T')")
            await delta_tab_btn.wait_for(state="visible", timeout=5000)

            # 2. Verify tab-delta-t starts hidden
            delta_pane = page.locator("#tab-delta-t")
            has_hidden = await delta_pane.evaluate("el => el.classList.contains('hidden')")
            assert has_hidden, "Expected tab-delta-t to be hidden on initial load"

            # 3. Click the tab button
            await delta_tab_btn.click()
            is_visible = await delta_pane.evaluate("el => !el.classList.contains('hidden')")
            assert is_visible, "Expected tab-delta-t to be visible after clicking tab button"

            # 4. Verify canvas exists and is rendered
            canvas = page.locator("#delta-t-chart")
            await canvas.wait_for(state="visible", timeout=5000)
            c_width = await canvas.evaluate("el => el.width")
            assert c_width >= 900, f"Expected canvas width >= 900, got {c_width}"

            # 5. Verify blackboard ledger container contains expandable turn details
            ledger_container = page.locator("#blackboard-ledger-container")
            await ledger_container.wait_for(state="visible", timeout=5000)
            
            # Wait for details elements to be rendered by JS
            await page.wait_for_selector("#blackboard-ledger-container details.feature-details", timeout=5000)
            turn_details = page.locator("#blackboard-ledger-container details.feature-details")
            count = await turn_details.count()
            assert count >= 3, f"Expected at least 3 historical turns in ledger, got {count}"

            # 6. Verify first turn summary format (TURN 1 • TOPIC • [SCOPE])
            first_summary = await turn_details.first.locator("summary").inner_text()
            assert "TURN 1" in first_summary
            assert "SILICON_MEMORY_LIMITS" in first_summary
            assert "CONTEXT_SCOPE_LONG" in first_summary

            # 7. Verify expanded contents (Distillation Bullets & 1-Line Consensus)
            details_content = turn_details.first.locator(".details-content")
            content_text = await details_content.inner_text()
            assert "DISTILLATION BULLETS" in content_text.upper()
            assert "1-LINE CONSENSUS" in content_text.upper()
            assert "HANDOVER TELEMETRY" in content_text.upper()

        finally:
            await context.close()
            await browser.close()
