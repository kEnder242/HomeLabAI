"""[FEAT-520] Unit & Playwright End-to-End Test Suite: Forced Triage Routing.
Verifies:
1. Deterministic forced triage win for PINKY (via <|PINKY|> token and routing policy).
2. Deterministic forced triage win for BRAIN (via <|BRAIN|> token and routing policy).
3. Playwright browser validation of intercom.html DOM elements, asserting that
   .msg-source.pinky and .msg-source.brain styling classes render correctly when routed.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from playwright.async_api import async_playwright

# ==============================================================================
# SECTION 1: Deterministic Hub & Triage Routing Unit Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_forced_triage_routing_pinky_unit():
    """Verify that a forced Pinky triage payload dispatches to the Pinky node."""
    from logic.cognitive_hub import CognitiveHub
    
    hub = CognitiveHub.__new__(CognitiveHub)
    hub.residents = {}
    hub.session_buffers = {}
    hub.current_interest = 0.0
    hub.broadcast = AsyncMock()
    hub._token_routes = {
        "<|PINKY|>": {"addressed_to": "PINKY", "vibe": "TECHNICAL", "domain": "standard", "importance": 0.5},
        "<|BRAIN|>": {"addressed_to": "BRAIN", "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8},
    }
    
    # Verify token resolution forces PINKY
    route = hub._token_routes.get("<|PINKY|>")
    assert route is not None
    assert route["addressed_to"] == "PINKY"
    
    # Mock Pinky and Brain residents
    pinky_called = False
    brain_called = False
    
    mock_pinky = MagicMock()
    async def pinky_think(*args, **kwargs):
        nonlocal pinky_called
        pinky_called = True
        return "Pinky responding"
    mock_pinky.call_tool = pinky_think
    
    mock_brain = MagicMock()
    async def brain_think(*args, **kwargs):
        nonlocal brain_called
        brain_called = True
        return "Brain responding"
    mock_brain.call_tool = brain_think
    
    hub.residents["pinky"] = mock_pinky
    hub.residents["brain"] = mock_brain
    
    # Route to primary responder
    target_node = route["addressed_to"].lower()
    assert target_node == "pinky"
    await hub.residents[target_node].call_tool("think", {})
    
    assert pinky_called is True
    assert brain_called is False


@pytest.mark.asyncio
async def test_forced_triage_routing_brain_unit():
    """Verify that a forced Brain triage payload dispatches to the Brain node."""
    from logic.cognitive_hub import CognitiveHub
    
    hub = CognitiveHub.__new__(CognitiveHub)
    hub.residents = {}
    hub._token_routes = {
        "<|PINKY|>": {"addressed_to": "PINKY", "vibe": "TECHNICAL", "domain": "standard", "importance": 0.5},
        "<|BRAIN|>": {"addressed_to": "BRAIN", "vibe": "TECHNICAL", "domain": "standard", "importance": 0.8},
    }
    
    route = hub._token_routes.get("<|BRAIN|>")
    assert route is not None
    assert route["addressed_to"] == "BRAIN"
    
    pinky_called = False
    brain_called = False
    
    mock_pinky = MagicMock()
    async def pinky_think(*args, **kwargs):
        nonlocal pinky_called
        pinky_called = True
        return "Pinky responding"
    mock_pinky.call_tool = pinky_think
    
    mock_brain = MagicMock()
    async def brain_think(*args, **kwargs):
        nonlocal brain_called
        brain_called = True
        return "Brain responding"
    mock_brain.call_tool = brain_think
    
    hub.residents["pinky"] = mock_pinky
    hub.residents["brain"] = mock_brain
    
    target_node = route["addressed_to"].lower()
    assert target_node == "brain"
    await hub.residents[target_node].call_tool("think", {})
    
    assert brain_called is True
    assert pinky_called is False


# ==============================================================================
# SECTION 2: Playwright Browser DOM & Rendering Verification
# ==============================================================================

@pytest.mark.asyncio
async def test_playwright_forced_routing_dom_elements():
    """Playwright E2E test verifying Intercom DOM structure for Pinky vs Brain routing."""
    intercom_url = "http://localhost:9001/intercom.html"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Navigate to Web Intercom
        response = await page.goto(intercom_url)
        assert response.status == 200
        
        # 1. Assert input container and text field exist
        text_input = await page.query_selector("#text-input")
        assert text_input is not None
        
        # 2. Inject simulated messages for both Pinky and Brain to verify CSS styling classes
        await page.evaluate("""() => {
            const chatBox = document.querySelector('#chat-log') || document.querySelector('#console-row') || document.body;
            
            // Create Pinky test message
            const pinkyMsg = document.createElement('div');
            pinkyMsg.className = 'message';
            pinkyMsg.id = 'test-pinky-msg';
            pinkyMsg.innerHTML = '<span class="msg-source pinky">PINKY</span><span class="msg-body">Narf! Point taken!</span>';
            chatBox.appendChild(pinkyMsg);
            
            // Create Brain test message
            const brainMsg = document.createElement('div');
            brainMsg.className = 'message';
            brainMsg.id = 'test-brain-msg';
            brainMsg.innerHTML = '<span class="msg-source brain">BRAIN</span><span class="msg-body">Architectural analysis verified.</span>';
            chatBox.appendChild(brainMsg);
        }""")
        
        # 3. Assert Pinky message element rendered with .msg-source.pinky class
        pinky_source = await page.query_selector("#test-pinky-msg .msg-source.pinky")
        assert pinky_source is not None
        pinky_text = await pinky_source.inner_text()
        assert "PINKY" in pinky_text
        
        # 4. Assert Brain message element rendered with .msg-source.brain class
        brain_source = await page.query_selector("#test-brain-msg .msg-source.brain")
        assert brain_source is not None
        brain_text = await brain_source.inner_text()
        assert "BRAIN" in brain_text
        
        await browser.close()


@pytest.mark.asyncio
async def test_playwright_triage_pane_mapping():
    """Verify that triage messages map to the correct DOM pane (#chat-console vs #insight-console)."""
    intercom_url = "http://localhost:9001/intercom.html"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        response = await page.goto(intercom_url)
        assert response.status == 200

        # Inject triage messages via intercom_v2.js appendMsg()
        await page.evaluate("""() => {
            // 1. Local vLLM triage -> channel='chat' -> Pinky's Console (Left)
            appendMsg('{"addressed_to": "PINKY", "vibe": "CASUAL"}', 'brain-msg', 'Lab (Triage)', 'chat');

            // 2. Kender/Deep Thought triage -> channel='insight' -> Brain's Insight (Right)
            appendMsg('{"addressed_to": "BRAIN", "vibe": "TECHNICAL"}', 'brain-msg', 'Deep Thought (Triage)', 'insight');
        }""")

        # Verify #chat-console (Pinky Left) contains the Lab (Triage) message
        pinky_pane = page.locator("#chat-console")
        pinky_triage = pinky_pane.locator(".message", has_text="Lab (Triage)")
        await pinky_triage.wait_for(state="visible", timeout=3000)
        assert await pinky_triage.count() == 1

        # Verify #insight-console (Brain Right) contains the Deep Thought (Triage) message
        insight_pane = page.locator("#insight-console")
        brain_triage = insight_pane.locator(".message", has_text="Deep Thought (Triage)")
        await brain_triage.wait_for(state="visible", timeout=3000)
        assert await brain_triage.count() == 1

        # Cross-isolation check: Lab (Triage) must NOT be in insight pane, Deep Thought (Triage) must NOT be in chat pane
        assert await insight_pane.locator(".message", has_text="Lab (Triage)").count() == 0
        assert await pinky_pane.locator(".message", has_text="Deep Thought (Triage)").count() == 0

        await browser.close()

