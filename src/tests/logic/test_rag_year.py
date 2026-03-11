import asyncio
import os, sys, json
sys.path.append(os.path.expanduser("~/Dev_Lab/HomeLabAI/src"))
from nodes.archive_node import get_context

async def run_test():
    res = await get_context("Validation events from 2019")
    print("RESULT:")
    try:
        data = json.loads(res)
        print("SOURCES:", data.get("sources"))
        print("TEXT PREVIEW:", data.get("text")[:200])
    except Exception as e:
        print("Raw output:", res)

asyncio.run(run_test())
