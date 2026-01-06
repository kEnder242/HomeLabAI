import asyncio
import websockets
import pyaudio
import sys
import json

# Configuration
HOST = "z87-Linux.local" 
# HOST = "192.168.1.XX" # Fallback
PORT = 8765
CHUNK = 2048 # Larger chunk for network efficiency
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

async def receive_messages(websocket):
    """Listens for text responses from the server."""
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                text = data.get("text", "")
                print(f"\n[SERVER]: {text}")
            except json.JSONDecodeError:
                print(f"\n[RAW]: {message}")
    except websockets.exceptions.ConnectionClosed:
        print("\n[DISCONNECTED] Server closed connection.")

async def send_audio(websocket):
    """Streams microphone audio to the server."""
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    print("\n[MIC ACTIVE] Speak now... (Ctrl+C to stop)")
    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            try:
                await websocket.send(data)
            except websockets.exceptions.ConnectionClosedOK:
                break # Exit loop cleanly if connection closes
            await asyncio.sleep(0.01) # Yield to let receive_messages run
    except KeyboardInterrupt:
        pass
    except websockets.exceptions.ConnectionClosedError:
        print("[DISCONNECTED] Connection lost unexpectedly.")
    finally:
        print("[MIC CLOSED]")
        stream.stop_stream()
        stream.close()
        p.terminate()

async def main():
    uri = f"ws://{HOST}:{PORT}"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("[CONNECTED] Link established.")
            
            # Run send and receive in parallel
            sender = asyncio.create_task(send_audio(websocket))
            receiver = asyncio.create_task(receive_messages(websocket))
            
            # Wait until one terminates (usually sender via Ctrl+C)
            done, pending = await asyncio.wait(
                [sender, receiver],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in pending:
                task.cancel()
                
    except Exception as e:
        print(f"[ERROR] Connection failed: {e}")

if __name__ == "__main__":
    try:
        import pyaudio
        import websockets
    except ImportError:
        print("Missing dependencies. Run: pip install pyaudio websockets")
        sys.exit(1)
        
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye.")