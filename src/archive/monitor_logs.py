import time
import os
import sys
import re

LOG_FILE = os.path.expanduser("~/VoiceGateway/logs/pinky.log")

def monitor():
    print(f"Watching {LOG_FILE} for activity... (Ctrl+C to stop)")
    try:
        # Open file, seek to end
        f = open(LOG_FILE, "r")
        f.seek(0, 2)
        
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.1)
                continue
            
            print(line.strip())
            
            # Exit conditions
            if "[PINKY]" in line or "[BRAIN]" in line:
                print("\n--> Turn Complete. Exiting monitor.")
                sys.exit(0)
            if "Handler exiting" in line:
                print("\n--> Client Disconnected. Exiting monitor.")
                sys.exit(0)
                
    except FileNotFoundError:
        print("Log file not found.")
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    monitor()

