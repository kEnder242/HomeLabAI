import asyncio
import json
import websockets
import time

# Configuration
HUB_URL = "ws://localhost:8765"

async def run_gui_flow_tests():
    """Comprehensive suite for verified GUI flows."""
    print("\n--- 🏁 STARTING GUI FLOW VERIFICATION ---")
    
    async with websockets.connect(HUB_URL) as ws:
        # 1. Handshake & Cabinet Sync
        print("[TEST] Handshake...")
        await ws.send(json.dumps({"type": "handshake", "version": "3.6.4"}))
        
        # Recv Status
        welcome = await asyncio.wait_for(ws.recv(), timeout=5)
        assert json.loads(welcome)['type'] == 'status'
        
        # Recv Cabinet
        cabinet = await asyncio.wait_for(ws.recv(), timeout=10)
        files = json.loads(cabinet).get('files', [])
        print(f"[PASS] Cabinet Synced: {len(files)} items.")
        assert len(files) > 0
        assert any(".json" in f for f in files)
        
        # 2. File Reading (Verification of Slug Mapping)
        target_file = "2024.json"
        print(f"[TEST] Reading {target_file}...")
        await ws.send(json.dumps({"type": "read_file", "filename": target_file}))
        
        content_msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(content_msg)
        assert data['type'] == 'file_content'
        assert len(data['content']) > 1000 # Verify substantial content
        print(f"[PASS] {target_file} content retrieved.")

        # 3. Text Interaction & No-JSON Leak Check
        print("[TEST] Text Input (Pi) & Leak Check...")
        await ws.send(json.dumps({"type": "text_input", "content": "What is pi to 5 decimals? Just the number."}))
        
        # We expect a response that is NOT raw JSON
        start_t = time.time()
        while time.time() - start_t < 30:
            msg = await asyncio.wait_for(ws.recv(), timeout=15)
            resp = json.loads(msg)
            if resp.get('brain'):
                txt = resp['brain']
                print(f"[RECV] {resp['brain_source']}: {txt[:50]}...")
                # Verify no raw JSON blocks in the output
                assert "{" not in txt or "}" not in txt
                print("[PASS] Natural language response verified (No JSON leak).")
                break

        # 4. Graceful Shutdown Tool Call
        print("[TEST] Lifecycle: close_lab...")
        await ws.send(json.dumps({"type": "text_input", "content": "Please close the lab."}))
        
        # Expect shutdown sequence
        final_msg = await asyncio.wait_for(ws.recv(), timeout=10)
        data = json.loads(final_msg)
        print(f"[RECV] {data.get('brain_source')}: {data.get('brain')}")
        assert "Closing" in data.get('brain', '')
        print("[PASS] Shutdown signal intercepted successfully.")

if __name__ == "__main__":
    try:
        asyncio.run(run_gui_flow_tests())
        print("\n--- ✅ ALL GUI FLOWS VERIFIED ---")
    except Exception as e:
        print(f"\n--- ❌ FLOW VERIFICATION FAILED: {e} ---")
        exit(1)
