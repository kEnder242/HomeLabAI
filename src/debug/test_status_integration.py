import asyncio
import json
import os
from recruiter import run_recruiter_task

# Paths
WORKSPACE_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
DATA_DIR = os.path.join(WORKSPACE_DIR, "field_notes/data")
BRIEFS_DIR = os.path.join(DATA_DIR, "recruiter_briefs")
PAGER_FILE = os.path.join(DATA_DIR, "pager_activity.json")


async def test_status_integration():
    print("--- [TEST] Status & Pager Integration ---")

    # 1. Trigger Recruiter Task
    print("Step 1: Running Recruiter Task...")
    brief_path = await run_recruiter_task()
    print(f"Brief generated: {brief_path}")

    # 2. Verify Brief location on SSD
    if brief_path.startswith(BRIEFS_DIR):
        print("✅ SSD Path Verification PASSED.")
    else:
        print(f"❌ SSD Path Verification FAILED. Path: {brief_path}")

    # 3. Check Pager Activity
    print("Step 2: Checking Pager Activity...")
    with open(PAGER_FILE, "r") as f:
        pager = json.load(f)

    last_entry = pager[-1]
    if last_entry["source"] == "Recruiter" and "job_brief" in last_entry["message"]:
        print("✅ Pager Entry Verification PASSED.")
        print(f"Entry: {last_entry['message']}")
    else:
        print("❌ Pager Entry Verification FAILED.")

    print("\n--- [RESULT] Integration Test Complete ---")


if __name__ == "__main__":
    asyncio.run(test_status_integration())
