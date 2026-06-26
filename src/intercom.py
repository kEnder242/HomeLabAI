import asyncio
import websockets
import pyaudio
import sys
import os
import json
from enum import Enum, auto

# --- PLATFORM HANDLING ---
# msvcrt is Windows only. For Linux, we use select and termios/tty.
try:
    import msvcrt
    IS_WINDOWS = True
except ImportError:
    IS_WINDOWS = False
    try:
        import select
        import termios
        import tty
    except ImportError:
        pass

OLD_SETTINGS = None
if not IS_WINDOWS:
    try:
        OLD_SETTINGS = termios.tcgetattr(sys.stdin.fileno())
    except Exception:
        pass

def set_raw_mode(enable):
    if IS_WINDOWS or OLD_SETTINGS is None:
        return
    try:
        fd = sys.stdin.fileno()
        if enable:
            tty.setcbreak(fd)
        else:
            termios.tcsetattr(fd, termios.TCSADRAIN, OLD_SETTINGS)
    except Exception:
        pass

# --- COLOR HANDLING ---
try:
    import colorama
    colorama.init(autoreset=True)
except ImportError:
    pass # Fallback to raw ANSI if colorama is missing

# --- CONFIGURATION ---
VERSION = "3.4.0"
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
COLOR_BLUE = "\033[94m"

# State Machine
class ClientState(Enum):
    LOBBY = auto()
    LISTENING = auto()
    TYPING = auto()
    SHUTDOWN = auto()

# Global Context
STATE = ClientState.LOBBY
SHUTDOWN_EVENT = asyncio.Event()
IS_HEARING = False # Track if we are currently mid-transcription line

async def get_user_input():
    """Blocking input wrapped in a thread."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, sys.stdin.readline)

async def check_keyboard_trigger():
    """Polls for SPACE key to toggle modes (Cross-Platform)."""
    if IS_WINDOWS:
        if msvcrt.kbhit():
            char = msvcrt.getch()
            # Trigger text mode only on SPACE (32)
            if char == b' ':
                return True
    else:
        if OLD_SETTINGS is not None:
            try:
                r, _, _ = select.select([sys.stdin], [], [], 0)
                if r:
                    char = sys.stdin.read(1)
                    if char == ' ':
                        return True
            except Exception:
                pass
    return False

async def receive_messages(websocket):
    """Listens for server responses and updates the UI."""
    global STATE, IS_HEARING
    try:
        async for message in websocket:
            data = json.loads(message)

            # 1. Status Events
            if data.get("type") == "status":
                s = data.get("state")
                v = data.get("version", "unknown")
                is_vocal = data.get("vocal", False) or data.get("engine_vocal", False)
                if s == "OPERATIONAL" or is_vocal or s == "ready" or s == "connected":
                    if STATE == ClientState.LOBBY:
                        print(f"{COLOR_GREEN}[ACME LAB]: Connected to v{v}. Ready. {COLOR_RESET}")
                        print(f"{COLOR_BLUE}[INFO] Press SPACE to Type, Ctrl+C to Quit.{COLOR_RESET}")
                    STATE = ClientState.LISTENING
                elif s == "shutdown" or s == "HIBERNATING" or s == "offline":
                    if IS_HEARING:
                        print("")
                        IS_HEARING = False
                    print(f"{COLOR_RED}[ACME LAB]: Closing / Hibernating.{COLOR_RESET}")
                    STATE = ClientState.LOBBY

            # 2. Transcription & Responses
            elif "text" in data and STATE == ClientState.LISTENING:
                IS_HEARING = True
                sys.stdout.write(f"\rHearing: {data['text']}   ")
                sys.stdout.flush()

            elif data.get("type") == "final":
                 if IS_HEARING:
                     print("")
                     IS_HEARING = False
                 print(f"{COLOR_YELLOW}[YOU]: {data['text']}{COLOR_RESET}")

            elif "brain" in data:
                if IS_HEARING:
                    print("")
                    IS_HEARING = False
                source = data.get("brain_source", "Unknown")
                content = data['brain']
                c = COLOR_PINK if "Pinky" in source else COLOR_CYAN
                print(f"{c}[{source}]: {content}{COLOR_RESET}")

            # 3. Debug Events (Brain Activity)
            elif data.get("type") == "debug":
                event = data.get("event")
                if event == "BRAIN_OUTPUT":
                    if IS_HEARING:
                        print("")
                        IS_HEARING = False
                    print(f"{COLOR_CYAN}[THE BRAIN]: {data.get('data')}{COLOR_RESET}")
                elif event == "PINKY_DECISION":
                    decision = data.get("data", {})
                    tool = decision.get("tool")
                    if tool and tool != "facilitate" and tool != "None":
                        if IS_HEARING:
                            print("")
                            IS_HEARING = False
                        print(f"{COLOR_PINK}[PINKY THOUGHT]: Decided to use '{tool}'{COLOR_RESET}")

    except websockets.exceptions.ConnectionClosed:
        SHUTDOWN_EVENT.set()

async def audio_and_input_loop(websocket):
    """
    The Core Loop. 
    Manages Audio Streaming AND Keyboard Polling.
    """
    global STATE
    p = pyaudio.PyAudio()
    stream = None

    current_raw = False
    try:
        # Setup Audio
        stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        print(f"{COLOR_BLUE}[CLIENT] Connecting to Intercom...{COLOR_RESET}")

        while not SHUTDOWN_EVENT.is_set():

            # --- STATE: LISTENING (Mic On) ---
            if STATE == ClientState.LISTENING:
                if not current_raw:
                    set_raw_mode(True)
                    current_raw = True

                if stream.is_stopped():
                    stream.start_stream()

                # 1. Read Mic
                try:
                    data = stream.read(CHUNK, exception_on_overflow=False)
                    await websocket.send(data)
                except Exception:
                    # Ignore stream errors during switch
                    pass

                # 2. Poll Keyboard (Trigger)
                if await check_keyboard_trigger():
                    if current_raw:
                        set_raw_mode(False)
                        current_raw = False
                    STATE = ClientState.TYPING
                    stream.stop_stream() # Mute Mic
                    print(f"{COLOR_BLUE}[TEXT MODE] Type your message (ENTER to send, empty to cancel):{COLOR_RESET}")
                    sys.stdout.write(">> ")
                    sys.stdout.flush()

                await asyncio.sleep(0.01) # Yield to event loop

            # --- STATE: TYPING (Mic Off) ---
            elif STATE == ClientState.TYPING:
                if current_raw:
                    set_raw_mode(False)
                    current_raw = False

                # 1. Get Input (Blocking, off-thread)
                user_text = (await get_user_input()).strip()

                # 2. Process
                if user_text:
                    # Check for local commands
                    if user_text.lower() == "/quit":
                        STATE = ClientState.SHUTDOWN
                        SHUTDOWN_EVENT.set()
                        break

                    # Send as JSON Event
                    payload = {
                        "type": "text_input",
                        "content": user_text,
                        "timestamp": 0 # TODO: Add real time
                    }
                    await websocket.send(json.dumps(payload))

                # 3. Return to Listening
                print(f"{COLOR_GREEN}[CLIENT] Mic Resumed.{COLOR_RESET}")
                STATE = ClientState.LISTENING

            # --- STATE: LOBBY/WAITING ---
            else:
                if current_raw:
                    set_raw_mode(False)
                    current_raw = False
                await asyncio.sleep(0.1)

    except Exception as e:
        print(f"{COLOR_RED}[ERROR]: {e}{COLOR_RESET}")
    finally:
        set_raw_mode(False)
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()

async def connect_with_retry(uri):
    """Connection logic with retry."""
    for i in range(5):
        try:
            return await websockets.connect(uri)
        except Exception:
            print(f"Waiting for server... ({i+1}/5)")
            await asyncio.sleep(1)
    raise ConnectionRefusedError("Server Unreachable")

async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Acme Intercom Client")
    parser.add_argument("--host", default="127.0.0.1", help="Foyer WebSocket host")
    parser.add_argument("--port", type=int, default=8765, help="Foyer WebSocket port")
    args = parser.parse_args()

    uri = f"ws://{args.host}:{args.port}"
    print(f"{COLOR_BLUE}[CLIENT] Connecting to {uri}...{COLOR_RESET}")
    try:
        ws = await connect_with_retry(uri)
        async with ws as websocket:
            # Handshake
            await websocket.send(json.dumps({"type": "handshake", "version": VERSION, "client": "intercom"}))

            # Tasks
            io_task = asyncio.create_task(audio_and_input_loop(websocket))
            rx_task = asyncio.create_task(receive_messages(websocket))

            await SHUTDOWN_EVENT.wait()
            io_task.cancel()
            rx_task.cancel()

    except Exception as e:
        print(f"\n{COLOR_RED}Fatal: {e}{COLOR_RESET}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{COLOR_RED}Goodbye!{COLOR_RESET}")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
