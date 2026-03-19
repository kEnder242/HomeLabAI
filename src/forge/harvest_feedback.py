import json
import os

# [FEAT-232] Feedback Harvester
# Scrapes server.log for user feedback packets and formats them for curriculum induction.

FORGE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.dirname(FORGE_DIR)
LAB_DIR = os.path.dirname(SRC_DIR)
SERVER_LOG = os.path.join(LAB_DIR, "server.log")
OUTPUT_FILE = os.path.join(FORGE_DIR, "feedback_curriculum.jsonl")

def harvest():
    if not os.path.exists(SERVER_LOG):
        print(f"Log file {SERVER_LOG} not found.")
        return

    curriculum = []
    try:
        with open(SERVER_LOG, "r", encoding="utf-8") as f:
            for line in f:
                if "FEEDBACK: {" in line:
                    try:
                        # Extract JSON part
                        parts = line.split("FEEDBACK: ", 1)
                        if len(parts) < 2:
                            continue
                        json_str = parts[1].strip()
                        data = json.loads(json_str)
                        
                        # Filter for ⬆️ (UP) and ⬇️ (DOWN) votes
                        vote = data.get("vote", "")
                        if vote in ["⬆️", "⬇️", "UP", "DOWN"]:
                            curriculum.append(data)
                    except (json.JSONDecodeError, ValueError):
                        continue
    except Exception as e:
        print(f"Error reading log: {e}")
        return

    if curriculum:
        try:
            with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
                for item in curriculum:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            print(f"Successfully harvested {len(curriculum)} packets to {OUTPUT_FILE}")
        except Exception as e:
            print(f"Error writing curriculum: {e}")
    else:
        print("No eligible feedback packets found in log.")

if __name__ == "__main__":
    harvest()
