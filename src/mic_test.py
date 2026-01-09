import asyncio
import websockets
import pyaudio
import sys
import json

VERSION = "1.0.2"

# Configuration
HOST = "z87-Linux.local" 
PORT = 8765
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# Global State
LAB_READY = False
SHUTDOWN_EVENT = asyncio.Event()

async def receive_messages(websocket):
    """Listens for text responses from the server."""
    global LAB_READY
    try:
        async for message in websocket:
            data = json.loads(message)
            
            # Status Event
            if data.get("type") == "status":
                state = data.get("state")
                server_ver = data.get("version", "Unknown")
                
                # Version Check
                if server_ver != VERSION:
                    print(f"\n⚠️ [VERSION MISMATCH]: Client {VERSION} vs Server {server_ver}")
                    print("⚠️ Please run sync_to_windows.sh to update.")

                if state == "ready":
                    LAB_READY = True
                    print(f"\n✅ [ACME LAB v{server_ver}]: {data.get('message', 'Ready')}")
                    print("🎤 Microphone is LIVE. Speak now... (Ctrl+C to stop)")
                elif state == "waiting":
                    print(f"\n⏳ [LOBBY v{server_ver}]: {data.get('message', 'Please wait...')}")
                elif state == "shutdown":
                    print("\n🛑 [ACME LAB]: Lab is closing. Goodbye!")
                    SHUTDOWN_EVENT.set()
                    return

            # Final Transcript Event
            elif data.get("type") == "final":
                print(f"\n📨 [SENT]: \"{data['text']}\"" )

            # Partial Transcript
            elif "text" in data:
                sys.stdout.write(f"\r👂 Hearing: {data['text']}   ")
                sys.stdout.flush()

            # Brain/Pinky Response
            elif "brain" in data:
                source = data.get("brain_source", "Unknown Brain")
                content = data['brain']
                print(f"\n\n🤖 [{source}]: {content}\n")
                
    except websockets.exceptions.ConnectionClosed:
        print("\n[DISCONNECTED] Server closed connection.")
        SHUTDOWN_EVENT.set()

async def send_audio(websocket):
    """Streams microphone audio to the server."""
    global LAB_READY
    p = pyaudio.PyAudio()
    stream = None
    
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
        
        print("⏳ Connecting to Lab...")
        
        while not LAB_READY and not SHUTDOWN_EVENT.is_set():
            await asyncio.sleep(0.1)

        while not SHUTDOWN_EVENT.is_set():
            data = stream.read(CHUNK, exception_on_overflow=False)
            try:
                await websocket.send(data)
            except websockets.exceptions.ConnectionClosedOK:
                break 
            await asyncio.sleep(0.01)
            
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[MIC ERROR]: {e}")
    finally:
        print("[MIC CLOSED]")
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()

async def connect_with_retry(uri, max_retries=10, delay=1.0):
    for i in range(max_retries):
        try:
            ws = await websockets.connect(uri)
            return ws
        except (ConnectionRefusedError, OSError):
            print(f"⏳ Waiting for Lab... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError("Could not connect to Acme Lab.")

async def main():
    uri = f"ws://{HOST}:{PORT}"
    try:
        ws = await connect_with_retry(uri)
        async with ws as websocket:
            # Run tasks
            receiver = asyncio.create_task(receive_messages(websocket))
            sender = asyncio.create_task(send_audio(websocket))
            
            # Wait for either natural end or shutdown signal
            await SHUTDOWN_EVENT.wait()
            
            # Cleanup
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
