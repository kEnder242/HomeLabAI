import asyncio
import websockets
import pyaudio
import sys
import json

VERSION = "1.0.4"

# Configuration
HOST = "z87-Linux.local" 
PORT = 8765
CHUNK = 2048
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_PINK = "\033[95m"
COLOR_CYAN = "\033[96m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"

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
                
                if state == "ready":
                    LAB_READY = True
                    print(f"\n{COLOR_GREEN}[ACME LAB v{server_ver}]: {data.get('message', 'Ready')}{COLOR_RESET}")
                    print("Microphone is LIVE. Speak now... (Ctrl+C to stop)")
                elif state == "waiting":
                    print(f"\n{COLOR_YELLOW}[LOBBY v{server_ver}]: {data.get('message', 'Please wait...')}{COLOR_RESET}")
                elif state == "shutdown":
                    print(f"\n{COLOR_RED}[ACME LAB]: Lab is closing. Goodbye!{COLOR_RESET}")
                    SHUTDOWN_EVENT.set()
                    return

            # Final Transcript Event
            elif data.get("type") == "final":
                print(f"\n{COLOR_YELLOW}[USER]: \"{data['text']}\"{COLOR_RESET}" )

            # Partial Transcript
            elif "text" in data:
                sys.stdout.write(f"\rHearing: {data['text']}   ")
                sys.stdout.flush()

            # Brain/Pinky Response
            elif "brain" in data:
                source = data.get("brain_source", "Unknown Brain")
                content = data['brain']
                color = COLOR_PINK if "Pinky" in source else COLOR_CYAN
                print(f"\n\n{color}[{source}]: {content}{COLOR_RESET}\n")

            # Debug Events (Brain Activity)
            elif data.get("type") == "debug":
                event = data.get("event")
                if event == "BRAIN_OUTPUT":
                    print(f"\n{COLOR_CYAN}🧠 [THE BRAIN]: {data.get('data')}{COLOR_RESET}")
                elif event == "PINKY_DECISION":
                    decision = data.get("data", {})
                    tool = decision.get("tool")
                    print(f"\n{COLOR_PINK}🐹 [PINKY THOUGHT]: Decided to use '{tool}'{COLOR_RESET}")
                
    except websockets.exceptions.ConnectionClosed:
        print(f"\n{COLOR_RED}[DISCONNECTED] Server closed connection.{COLOR_RESET}")
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
        
        print("Connecting to Lab...")
        
        while not LAB_READY and not SHUTDOWN_EVENT.is_set():
            await asyncio.sleep(0.1)

        while not SHUTDOWN_EVENT.is_set():
            try:
                data = stream.read(CHUNK, exception_on_overflow=False)
                await websocket.send(data)
                await asyncio.sleep(0.01)
            except (websockets.exceptions.ConnectionClosedOK, asyncio.CancelledError):
                break 
            
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        print(f"\n{COLOR_RED}[STOP] User requested shutdown...{COLOR_RESET}")
        try:
            await websocket.send(json.dumps({"debug_text": "SHUTDOWN_PROTOCOL_OVERRIDE"}))
        except: pass
    except Exception as e:
        print(f"{COLOR_RED}[MIC ERROR]: {e}{COLOR_RESET}")
    finally:
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
            print(f"Waiting for Lab... ({i+1}/{max_retries})")
            await asyncio.sleep(delay)
    raise ConnectionRefusedError("Could not connect to Acme Lab.")

async def main():
    uri = f"ws://{HOST}:{PORT}"
    try:
        ws = await connect_with_retry(uri)
        async with ws as websocket:
            await websocket.send(json.dumps({"type": "handshake", "version": VERSION}))
            
            receiver = asyncio.create_task(receive_messages(websocket))
            sender = asyncio.create_task(send_audio(websocket))
            
            await SHUTDOWN_EVENT.wait()
            
            for task in [sender, receiver]:
                if not task.done(): task.cancel() 
                
    except Exception as e:
        print(f"{COLOR_RED}[ERROR] Connection failed: {e}{COLOR_RESET}")

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