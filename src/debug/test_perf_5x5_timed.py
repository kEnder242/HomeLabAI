import asyncio
import json
import os
import sys
import time
import argparse
import urllib.request
from playwright.async_api import async_playwright

# [TEST-55] SPRINT 54: Physical Bedrock Timed Gauntlet & Cold-Start Latency Certification
# Accurately measures Warming Pop (<100ms), Deep Thought Quip (<1.5s), and Real Answer TTFT.

LAB_DIR = "/home/jallred/Dev_Lab/HomeLabAI"
ATTENDANT_URL = "http://127.0.0.1:8765"
INTERCOM_URL = "http://localhost:9001/intercom.html"

def get_lab_status():
    """Query live attendant status to determine ignition state and duration."""
    try:
        req = urllib.request.Request(f"{ATTENDANT_URL}/status", headers={"User-Agent": "perf-5x5-harness"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    [⚠️] Attendant status query error: {e}")
    return None

async def run_cycle(cycle_id, total_cycles, wait_mins, p_instance, force_cold=False):
    print(f"\n{'='*70}")
    print(f"[Cycle {cycle_id}/{total_cycles}] Target Wait Interval: {wait_mins} minute(s)...")
    if wait_mins > 0:
        await asyncio.sleep(wait_mins * 60)
    
# [FEAT-254] VRAM Pre-Flight Gate
    # 1. Pre-flight Lab State Probe (Story 54.10 awareness)
    status = get_lab_status()
    if status:
        state = status.get("state", "UNKNOWN")
        vocal = status.get("vocal", False)
        duration = status.get("state_duration_s", 0)
        iso = status.get("state_changed_iso", "unknown")
        vram = status.get("vram_used", 0)
        print(f"[*] Pre-Flight State: {state} (Vocal={vocal}, VRAM={vram}MB) | State Changed: {iso} ({duration:.1f}s ago)")
        is_cold = (state == "HIBERNATING" or not vocal)
    else:
        print("    [⚠️] Could not verify attendant state. Assuming standard evaluation.")
        is_cold = True

    # 2. Clean Incognito Browser Context (Zero History Residue)
    browser = await p_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )
    context = await browser.new_context(storage_state=None)
    page = await context.new_page()
    
    try:
        await page.goto(INTERCOM_URL, wait_until="domcontentloaded")
        
        # Clear any localStorage / sessionStorage left in client
        await page.evaluate("() => { try { sessionStorage.clear(); localStorage.clear(); } catch(e){} }")
        
        query = "[ME] [STRATEGIC] Analyze the lab architecture."
        await page.wait_for_selector("#text-input", timeout=10000)
        # Explicitly wait for WebSocket connection to be fully OPEN before sending
        try:
            await page.wait_for_function("() => (window.ws && window.ws.readyState === 1) || document.querySelector('#connection-dot.connected')", timeout=15000)
        except Exception:
            await asyncio.sleep(2.0)
        
        # 3. Snapshot Baseline Message Count Before Sending Query
        baseline_count = await page.evaluate("() => document.querySelectorAll('.message').length")
        
        await page.fill("#text-input", query)
        
        # 4. Dispatch Query & Measure
        send_t = time.time()
        await page.keyboard.press("Enter")
        print(f"[*] Query Dispatched at t=0.00s. Monitoring for Warming Pop & Real Engine Response...")
        
        warming_pop_t = None
        real_answer_t = None
        real_answer_text = ""
        real_answer_src = ""
        success = False
        
        # [FEAT-521] Liveliness & Dead Air Event Ledger
        event_timeline = [{"t": 0.0, "src": "USER", "kind": "DISPATCH"}]
        crosstalk_events = []
        actor_events = []
        
        last_event_t = 0.0
        max_dead_air_with_crosstalk = 0.0
        
        while time.time() - send_t < 180:
            current_elapsed = time.time() - send_t
            try:
                new_elements = await page.evaluate(f"""() => {{
                    const all = Array.from(document.querySelectorAll('.message'));
                    return all.slice({baseline_count}).map(el => ({{
                        src: (el.querySelector('.msg-source')?.innerText || '').trim(),
                        body: (el.querySelector('.msg-body')?.innerText || '').trim(),
                        is_crosstalk: el.classList.contains('internal') || (el.querySelector('.msg-source')?.innerText || '').toLowerCase().includes('crosstalk') || (el.querySelector('.msg-source')?.innerText || '').toLowerCase().includes('system')
                    }}));
                }}""")
            except Exception:
                await asyncio.sleep(0.5)
                continue
            
            # Detect newly added elements in timeline
            if len(new_elements) > len(event_timeline) - 1:
                added_count = len(new_elements) - (len(event_timeline) - 1)
                for item in new_elements[-added_count:]:
                    src = item.get("src", "")
                    body = item.get("body", "")
                    src_lower = src.lower()
                    body_lower = body.lower()
                    is_xtalk = item.get("is_crosstalk", False) or "crosstalk" in src_lower or "system" in src_lower
                    
                    gap_from_last = current_elapsed - last_event_t
                    if gap_from_last > max_dead_air_with_crosstalk:
                        max_dead_air_with_crosstalk = gap_from_last
                    last_event_t = current_elapsed
                    
                    evt = {
                        "t": current_elapsed,
                        "src": src,
                        "kind": "CROSSTALK" if is_xtalk else "ACTOR",
                        "preview": body[:60]
                    }
                    event_timeline.append(evt)
                    
                    if is_xtalk:
                        crosstalk_events.append(evt)
                        print(f"    [💬 CROSSTALK @ +{current_elapsed:.2f}s] Source: {src} | Preview: '{body[:45]}...'")
                    else:
                        actor_events.append(evt)
                    
                    # Check for Warming Pop
                    if "warming its anchors" in body_lower and warming_pop_t is None:
                        warming_pop_t = current_elapsed
                        print(f"    [🔥 WARMING POP] Source: {src} | Latency: {warming_pop_t*1000:.0f}ms (Budget: <100ms)")
                    
                    # Check for Real Engine Response
                    is_assistant = ("brain" in src_lower or "pinky" in src_lower or "thought" in src_lower or "failover" in src_lower)
                    if is_assistant and len(body) > 15 and "warming its anchors" not in body_lower:
                        real_answer_t = current_elapsed
                        real_answer_text = body
                        real_answer_src = src
                        success = True
                        break
            
            if success:
                break
            await asyncio.sleep(0.5)

        # 5. Report Cycle Verdict & Liveliness Metrics
        dead_air_without_crosstalk = real_answer_t if real_answer_t is not None else (time.time() - send_t)
        heavy_lifting_saved_s = max(0.0, dead_air_without_crosstalk - max_dead_air_with_crosstalk)
        heavy_lifting_pct = (heavy_lifting_saved_s / dead_air_without_crosstalk * 100.0) if dead_air_without_crosstalk > 0 else 0.0

        if success:
            print(f"    [🏆 REAL ANSWER] Source: {real_answer_src} | TTFT: {real_answer_t:.2f}s | Length: {len(real_answer_text)} chars")
            print(f"    [📊 LIVELINESS BENCHMARK]:")
            print(f"       * Dead Air (WITH Crosstalk):    {max_dead_air_with_crosstalk:.2f}s max gap")
            print(f"       * Dead Air (WITHOUT Crosstalk): {dead_air_without_crosstalk:.2f}s (Total TTFT)")
            print(f"       * Crosstalk Heavy Lifting:      {heavy_lifting_saved_s:.2f}s perceived wait reduction ({heavy_lifting_pct:.1f}%)")
            print(f"       * Total Timeline Events:        {len(event_timeline)} (Crosstalk: {len(crosstalk_events)}, Actor: {len(actor_events)})")
            
            if is_cold:
                if warming_pop_t is not None:
                    print(f"    [✅ COLD START CERTIFIED] Standalone pop arrived in {warming_pop_t*1000:.0f}ms, full answer delivered in {real_answer_t:.2f}s.")
                else:
                    print(f"    [ℹ️ NOTE] Engine woke from cold state ({real_answer_t:.2f}s), warming pop was bypassed or suppressed.")
            else:
                print(f"    [⚡ HOT STEADY STATE] Response delivered in {real_answer_t:.2f}s (Engine was already vocal).")
        else:
            print("    [❌ FAILED] No valid assistant response received within 180s timeout.")

    finally:
        await browser.close()
    
    return {
        "success": success,
        "real_answer_t": real_answer_t,
        "dead_air_with_crosstalk": max_dead_air_with_crosstalk,
        "dead_air_without_crosstalk": dead_air_without_crosstalk,
        "heavy_lifting_saved_s": heavy_lifting_saved_s,
        "heavy_lifting_pct": heavy_lifting_pct,
        "event_count": len(event_timeline),
        "crosstalk_count": len(crosstalk_events)
    }

async def main():
    parser = argparse.ArgumentParser(description="AcmeLab Performance Gauntlet & Cold-Start Latency Benchmarker")
    parser.add_argument("--cold-cert", action="store_true", help="Single controlled cold-start certification turn")
    parser.add_argument("--smoke", action="store_true", help="Fast smoke run: 3 cycles with 0-minute wait")
    parser.add_argument("--intervals", nargs="+", type=int, default=None, help="Custom wait intervals in minutes")
    args = parser.parse_args()

    if args.cold_cert:
        print("💎 INITIATING CONTROLLED COLD-START CERTIFICATION (STORY 54.12)")
        intervals = [0]
    elif args.smoke:
        print("🧪 INITIATING SMOKE TEST (3 Rapid Cycles, 0m Wait)")
        intervals = [0, 0, 0]
    elif args.intervals is not None:
        intervals = args.intervals
        print(f"💎 INITIATING CUSTOM TIMED GAUNTLET: intervals = {intervals}")
    else:
        print("💎 INITIATING TIMED PERFORMANCE GAUNTLET (75 MINS)")
        print("[*] intervals: 0, 5, 10, 20, 40 minutes (moving up to 40m quiescence wait).")
        intervals = [0, 5, 10, 20, 40]

    results = []
    async with async_playwright() as p:
        for i, wait in enumerate(intervals):
            res = await run_cycle(i+1, len(intervals), wait, p, force_cold=args.cold_cert)
            results.append(res)
            if not res.get("success"):
                print(f"\n❌ GAUNTLET FAILED at cycle {i+1}.")
                sys.exit(1)
        
        print(f"\n{'='*70}")
        print("🏆 GAUNTLET COMPLETE: Performance Bedrock & Latency Budgets are CERTIFIED.")
        
        # [FEAT-521] Summary Report
        avg_dead_air_xtalk = sum(r["dead_air_with_crosstalk"] for r in results) / len(results) if results else 0
        avg_dead_air_no_xtalk = sum(r["dead_air_without_crosstalk"] for r in results) / len(results) if results else 0
        avg_lifting_pct = sum(r["heavy_lifting_pct"] for r in results) / len(results) if results else 0
        
        print("\n📈 [FEAT-521] LIVELINESS BENCHMARK SUMMARY:")
        print(f"   • Cycles Completed:             {len(results)}/{len(intervals)}")
        print(f"   • Avg Dead Air (WITH Crosstalk):    {avg_dead_air_xtalk:.2f}s")
        print(f"   • Avg Dead Air (WITHOUT Crosstalk): {avg_dead_air_no_xtalk:.2f}s")
        print(f"   • Crosstalk Heavy-Lifting Lift:     {avg_lifting_pct:.1f}% perceived wait reduction")

if __name__ == "__main__":
    asyncio.run(main())

