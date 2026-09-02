"""
[FEAT-524] The Dead Air Delta Benchmark Harness
Evaluates actor-to-actor handovers across Cold Boot, Waking, and Operational Hot states.
"""
import asyncio
import json
import os
import time
import argparse
import urllib.request
from playwright.async_api import async_playwright

ATTENDANT_URL = "http://127.0.0.1:8765"
INTERCOM_URL = "http://localhost:9001/intercom.html"

def get_lab_status():
    """Query live attendant status."""
    try:
        req = urllib.request.Request(f"{ATTENDANT_URL}/status", headers={"User-Agent": "dead-air-delta-harness"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"    [!] Attendant status query error: {e}")
    return None

def trigger_sleep():
    """Put lab into hibernation for cold start test."""
    try:
        req = urllib.request.Request(f"{ATTENDANT_URL}/sleep", data=b'{"reason":"BENCHMARK_COLD"}', headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"    [!] Sleep trigger failed: {e}")
        return False

async def run_condition_benchmark(condition_name, p_instance, timeout_s=120):
    print(f"\n{'='*75}")
    print(f"[*] Starting Evaluation Condition: {condition_name}")
    print(f"{'='*75}")

    status = get_lab_status()
    pre_state = status.get("state", "UNKNOWN") if status else "UNKNOWN"
    pre_vram = status.get("vram_used", 0) if status else 0
    print(f"[*] Pre-Condition Silicon: State={pre_state}, VRAM={pre_vram}MB")

    browser = await p_instance.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    )
    context = await browser.new_context(storage_state=None)
    page = await context.new_page()

    handovers = {
        "condition": condition_name,
        "pre_state": pre_state,
        "pre_vram": pre_vram,
        "t0_dispatch": 0.0,
        "t1_triage": None,
        "t2_pinky_stance": None,
        "t3_brain_arch": None,
        "t4_deep_thought": None,
        "t5_pinky_judgment": None,
        "delta_t1": None,
        "delta_t2": None,
        "delta_t3": None,
        "delta_t4": None,
        "delta_t5": None,
        "total_round_trip": None,
        "events": []
    }

    try:
        await page.goto(INTERCOM_URL, wait_until="domcontentloaded")
        await page.evaluate("() => { try { sessionStorage.clear(); localStorage.clear(); } catch(e){} }")
        await page.wait_for_selector("#text-input", timeout=10000)

        # Wait for WebSocket ready
        try:
            await page.wait_for_function("() => (window.ws && window.ws.readyState === 1) || document.querySelector('#connection-dot.connected')", timeout=15000)
        except Exception:
            await asyncio.sleep(2.0)

        baseline_count = await page.evaluate("() => document.querySelectorAll('.message').length")

        query = "[STRATEGIC] Compare silicon memory limits of RTX 2080 Ti and M5 Air."
        await page.fill("#text-input", query)

        send_t = time.time()
        handovers["t0_dispatch"] = send_t
        await page.keyboard.press("Enter")
        print("[*] Query dispatched at t=0.00s. Tracking 5 discrete handover legs...")

        complete = False

        while time.time() - send_t < timeout_s:
            now = time.time()
            elapsed = now - send_t

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
                await asyncio.sleep(0.3)
                continue

            if len(new_elements) > len(handovers["events"]):
                added = new_elements[len(handovers["events"]):]
                for item in added:
                    src = item.get("src", "")
                    body = item.get("body", "")
                    src_l = src.lower()
                    body_l = body.lower()
                    is_xtalk = item.get("is_crosstalk", False) or "intuition" in body_l or "crosstalk" in src_l or "system" in src_l or "initiating" in body_l

                    evt = {
                        "elapsed_s": round(elapsed, 3),
                        "src": src,
                        "body_preview": body[:80],
                        "is_crosstalk": is_xtalk
                    }
                    handovers["events"].append(evt)
                    print(f"    [+{elapsed:.2f}s] [{src}]: {body[:60]}...")

                    # Ignore user message echoes
                    if "me" in src_l or "user" in src_l:
                        continue

                    # Delta 1: Triage resolution / warming pop / initial acknowledgment
                    if handovers["t1_triage"] is None:
                        if "triage" in src_l or "system" in src_l or "warming" in body_l or "waking" in body_l:
                            handovers["t1_triage"] = round(elapsed, 3)
                            handovers["delta_t1"] = round(elapsed, 3)
                            print(f"    --> Delta 1 (User -> Triage): {handovers['delta_t1']:.3f}s")

                    # Delta 2: Pinky initial stance
                    if handovers["t2_pinky_stance"] is None and handovers["t1_triage"] is not None:
                        if "pinky" in src_l and not ("summary" in src_l or "judgment" in src_l):
                            handovers["t2_pinky_stance"] = round(elapsed, 3)
                            handovers["delta_t2"] = round(elapsed - handovers["t1_triage"], 3)
                            print(f"    --> Delta 2 (Triage -> Pinky Stance): {handovers['delta_t2']:.3f}s")

                    # Delta 3: Brain architectural leg
                    if handovers["t3_brain_arch"] is None and (handovers["t2_pinky_stance"] is not None or handovers["t1_triage"] is not None):
                        if "brain" in src_l or "architect" in src_l:
                            ref_t = handovers["t2_pinky_stance"] or handovers["t1_triage"]
                            handovers["t3_brain_arch"] = round(elapsed, 3)
                            handovers["delta_t3"] = round(elapsed - ref_t, 3)
                            print(f"    --> Delta 3 (Pinky -> Brain Arch): {handovers['delta_t3']:.3f}s")

                    # Delta 4: Deep Thought oracle leg
                    if handovers["t4_deep_thought"] is None and (handovers["t3_brain_arch"] is not None or handovers["t2_pinky_stance"] is not None):
                        if "thought" in src_l or "oracle" in src_l:
                            ref_t = handovers["t3_brain_arch"] or handovers["t2_pinky_stance"] or handovers["t1_triage"]
                            handovers["t4_deep_thought"] = round(elapsed, 3)
                            handovers["delta_t4"] = round(elapsed - ref_t, 3)
                            print(f"    --> Delta 4 (Brain -> Deep Thought): {handovers['delta_t4']:.3f}s")

                    # Delta 5: Pinky summary & judgment (or final substantive assistant response)
                    is_assistant = ("pinky" in src_l or "brain" in src_l or "thought" in src_l or "assistant" in src_l)
                    if not is_xtalk and is_assistant and len(body) > 30 and ("warming" not in body_l):
                        ref_t = handovers["t4_deep_thought"] or handovers["t3_brain_arch"] or handovers["t2_pinky_stance"] or handovers["t1_triage"] or 0.0
                        handovers["t5_pinky_judgment"] = round(elapsed, 3)
                        handovers["delta_t5"] = round(elapsed - ref_t, 3)
                        handovers["total_round_trip"] = round(elapsed, 3)
                        print(f"    --> Delta 5 (Deep Thought -> Pinky Judgment): {handovers['delta_t5']:.3f}s")
                        print(f"    [+] Round Table Cycle Certified! Total: {handovers['total_round_trip']:.3f}s")
                        complete = True
                        break

            if complete:
                break
            await asyncio.sleep(0.4)

    finally:
        await context.close()
        await browser.close()

    return handovers

async def main():
    parser = argparse.ArgumentParser(description="[FEAT-524] Dead Air Delta Benchmark Harness")
    parser.add_argument("--condition", choices=["cold", "hot", "all"], default="hot", help="Execution condition")
    args = parser.parse_args()

    results = []
    async with async_playwright() as p:
        if args.condition in ("hot", "all"):
            res_hot = await run_condition_benchmark("OPERATIONAL_HOT", p, timeout_s=45)
            results.append(res_hot)

        if args.condition in ("cold", "all"):
            print("\n[*] Transitioning lab to HIBERNATING for cold boot test...")
            trigger_sleep()
            await asyncio.sleep(5)
            res_cold = await run_condition_benchmark("COLD_BOOT", p, timeout_s=120)
            results.append(res_cold)

    out_file = os.path.expanduser("~/Dev_Lab/Portfolio_Dev/field_notes/data/dead_air_deltas.json")
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[+] Benchmark complete. Saved {len(results)} condition run(s) to {out_file}")

if __name__ == "__main__":
    asyncio.run(main())
