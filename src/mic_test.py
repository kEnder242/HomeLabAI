import asyncio
import websockets
import pyaudio
import sys
import json

VERSION = "2026-01-08-v4"

# Configuration
HOST = "z87-Linux.local" 
PORT = 8765
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# State
LAB_READY = False

async def receive_messages(websocket):
    """Listens for text responses from the server."""
    global LAB_READY
    try:
        async for message in websocket:
            data = json.loads(message)
            
            # Status Event
            if data.get("type") == "status":
                if data.get("state") == "ready":
                    LAB_READY = True
                    print(f"\n✅ [ACME LAB]: {data.get('message', 'Ready')}")
                    print("🎤 Microphone is LIVE. Speak now... (Ctrl+C to stop)")

            # Final Transcript Event
            elif data.get("type") == "final":
                print(f"\n📨 [SENT]: \"{data['text']}\"")

            # Partial Transcript
            elif "text" in data:
                # Overwrite line for partials to keep it clean
                sys.stdout.write(f"\r👂 Hearing: {data['text']}   ")
                sys.stdout.flush()

            # Brain/Pinky Response
            elif "brain" in data:
                source = data.get("brain_source", "Unknown Brain")
                content = data['brain']
                print(f"\n\n🤖 [{source}]: {content}\n")
                
    except websockets.exceptions.ConnectionClosed:
        print("\n[DISCONNECTED] Server closed connection.")

async def send_audio(websocket):
    """Streams microphone audio to the server."""
    global LAB_READY
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)
    
    print("⏳ Connecting to Lab...")
    
    # Wait for Ready Signal (handled in receive loop) usually fast, 
    # but we don't want to stream silence before the server acknowledges.
    while not LAB_READY:
        await asyncio.sleep(0.1)

    try:
        while True:
            data = stream.read(CHUNK, exception_on_overflow=False)
            try:
                await websocket.send(data)
            except websockets.exceptions.ConnectionClosedOK:
                break 
            await asyncio.sleep(0.01)
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
    try:
        async with websockets.connect(uri) as websocket:
            # Run send and receive in parallel
            receiver = asyncio.create_task(receive_messages(websocket))
            sender = asyncio.create_task(send_audio(websocket))
            
            await asyncio.wait(
                [sender, receiver],
                return_when=asyncio.FIRST_COMPLETED
            )
            
            for task in [sender, receiver]:
                if not task.done(): task.cancel()
                
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
