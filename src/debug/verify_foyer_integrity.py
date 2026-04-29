import socket
import sys
import time

def check_port(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return True
    except (ConnectionRefusedError, socket.timeout, OSError):
        return False

if __name__ == "__main__":
    host = "localhost"
    port = 8765
    print(f"--- Probing Lab Foyer (Port {port}) ---")
    
    is_up = check_port(host, port)
    if is_up:
        print(f"SUCCESS: Port {port} is OPEN.")
        sys.exit(0)
    else:
        print(f"FAILURE: Port {port} is CLOSED.")
        sys.exit(1)
