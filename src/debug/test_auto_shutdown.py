import asyncio
import websockets
import sys
import time

async def test():
    uri = "ws://localhost:8765"
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Connected! Waiting 5 seconds...")
        await asyncio.sleep(5)
        print("Disconnecting...")
    
    print("Disconnected. Waiting for auto-shutdown (5s delay + margin)...")
    await asyncio.sleep(10)
    print("Done.")

if __name__ == "__main__":
    asyncio.run(test())
