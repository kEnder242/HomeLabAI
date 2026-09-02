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

            # 5. Verify accordion drawer starts closed
            drawer_content = page.locator("#blackboard-content")
            is_open_initial = await drawer_content.evaluate("el => el.classList.contains('open')")
            assert not is_open_initial, "Expected blackboard drawer to start closed"

            # 6. Click drawer toggle to open
            toggle_btn = page.locator(".drawer-toggle")
            await toggle_btn.click()
            is_open_after = await drawer_content.evaluate("el => el.classList.contains('open')")
            assert is_open_after, "Expected blackboard drawer to open after click"

            # 7. Verify blackboard entry contains distillation bullets and consensus
            entry_text = await page.locator(".blackboard-entry").inner_text()
            assert "Distillation Bullets:" in entry_text
            assert "1-Line Consensus:" in entry_text

            # 8. Click drawer toggle to close
            await toggle_btn.click()
            is_closed_again = await drawer_content.evaluate("el => !el.classList.contains('open')")
            assert is_closed_again, "Expected blackboard drawer to close after second click"

        finally:
            await context.close()
            await browser.close()
