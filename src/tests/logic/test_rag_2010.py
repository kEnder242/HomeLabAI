import asyncio
import os, sys, json
sys.path.append(os.path.expanduser("~/Dev_Lab/HomeLabAI/src"))
from nodes.archive_node import get_context

async def run_test():
    res = await get_context("Validation events from 2010")
    print("RAW RES:", repr(res))
    try:
        data = json.loads(res)
        print("SOURCES:", data.get("sources"))
        print("TEXT:", data.get("text"))
    except Exception as e:
        print("JSON Error:", e)

asyncio.run(run_test())
