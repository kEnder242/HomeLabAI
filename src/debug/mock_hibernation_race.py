import asyncio
import os
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Ensure we can import from src
sys.path.append(os.path.abspath("HomeLabAI/src"))

from acme_lab import AcmeLab

async def test_hibernation_race():
    print("--- 🧪 MOCK: Hibernation Race Condition Test ---")
    
    # [FIX] Patch os.open to bypass singleton lock
    with patch('os.open', return_value=999):
        with patch('os.fdopen'):
            # 1. Setup Lab
            lab = AcmeLab()
            lab.status = "HIBERNATING"
            lab.engine_ready.clear()
            lab._residents_booted = False
            
            # 2. Mock Attendant and boot_residents
            # We want to simulate boot_residents taking time
            original_boot = lab.boot_residents
            boot_count = 0
            
            async def mocked_boot(stack):
                nonlocal boot_count
                boot_count += 1
                print(f"[MOCK] boot_residents called (Count: {boot_count})")
                await asyncio.sleep(2) # Simulate work
                lab._residents_booted = True
                lab.engine_ready.set()
                lab.status = "OPERATIONAL"

            lab.boot_residents = mocked_boot
            
            # Mock network calls in process_query
            lab.broadcast = AsyncMock()
            lab.spark_restoration = AsyncMock()
            lab.cognitive = MagicMock()
            lab.cognitive.process_query = AsyncMock(return_value="OK")
            
            # Patch aiohttp session for the wait_ready call
            class MockResponse:
                def __init__(self, status):
                    self.status = status
                async def __aenter__(self): return self
                async def __aexit__(self, *args): pass
                async def json(self): return {"status": "success"}

            class MockSession:
                def __init__(self):
                    self.get = MagicMock(side_effect=self._get)
                def _get(self, *args, **kwargs):
                    # Return an awaitable that returns the context manager
                    fut = asyncio.Future()
                    fut.set_result(MockResponse(200))
                    return fut
                async def __aenter__(self): return self
                async def __aexit__(self, *args): pass
            mock_session = MockSession()

            with patch('aiohttp.ClientSession', return_value=mock_session):

                with patch('socket.socket'): # Mock port check
                    # 3. Simulate multiple concurrent queries
                    print("[SIM] Sending 3 concurrent queries during hibernation...")
                    tasks = [
                        asyncio.create_task(lab.process_query("[ME] Query 1")),
                        asyncio.create_task(lab.process_query("[ME] Query 2")),
                        asyncio.create_task(lab.process_query("[ME] Query 3"))
                    ]
                    
                    await asyncio.gather(*tasks)
            
            print(f"--- 🏁 Result: boot_residents called {boot_count} times ---")
            if boot_count > 1:
                print("[FAIL] Race condition detected: Multiple boots spawned!")
            else:
                print("[PASS] Only one boot cycle occurred.")

if __name__ == "__main__":
    asyncio.run(test_hibernation_race())
