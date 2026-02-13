import time
import os

LOG_FILE = "logs/pinky.log"

# ANSI Colors
RESET = "\033[0m"
CYAN = "\033[96m"   # User
PINK = "\033[95m"   # Pinky
GREEN = "\033[92m"  # Brain
GRAY = "\033[90m"   # System

def tail_f(filename):
    """Generator that yields new lines from a file like tail -f."""
    file = open(filename, 'r')
    # Go to the end of file
    file.seek(0, os.SEEK_END)

    while True:
        line = file.readline()
        if not line:
            time.sleep(0.1)
            continue
        yield line

def process_line(line):
    line = line.strip()
    if "[USER]" in line:
        content = line.split("[USER]", 1)[1]
        print(f"{CYAN}USER: {content.strip()}{RESET}")
    elif "[PINKY]" in line:
        content = line.split("[PINKY]", 1)[1]
        print(f"{PINK}PINKY: {content.strip()}{RESET}")
    elif "[BRAIN]" in line:
        content = line.split("[BRAIN]", 1)[1]
        print(f"{GREEN}BRAIN: {content.strip()}{RESET}")
    elif "🧠 Pinky requested THE BRAIN!" in line:
        print(f"{GRAY}--- Handing off to Brain ---{RESET}")
    # Optional: Filter out raw technical logs if desired
    # else:
    #     print(f"{GRAY}{line}{RESET}")

if __name__ == "__main__":
    if not os.path.exists(LOG_FILE):
        print(f"Waiting for {LOG_FILE} to be created...")
        while not os.path.exists(LOG_FILE):
            time.sleep(1)

    print(f"Watching {LOG_FILE} for conversation...")
    print("----------------------------------------")

    # Process existing lines first?
    # For now, let's just dump the whole file then tail
    with open(LOG_FILE, 'r') as f:
        for line in f:
            process_line(line)

    # Then tail
    for line in tail_f(LOG_FILE):
        process_line(line)
