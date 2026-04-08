import asyncio
import json
import sys
import subprocess

async def probe_node():
    # Start the node process
    cmd = [
        "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3", 
        "src/nodes/lab_node.py", 
        "--role", "LAB", 
        "--session", "MANUAL_PROBE"
    ]
    env = {"PYTHONPATH": "/home/jallred/Dev_Lab/HomeLabAI/src"}
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
        cwd="/home/jallred/Dev_Lab/HomeLabAI"
    )

    async def send(msg):
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        await proc.stdin.drain()

    # 1. Initialize
    await send({
        "jsonrpc": "2.0", "id": 0, "method": "initialize", 
        "params": {
            "protocolVersion": "2024-11-05", 
            "capabilities": {}, 
            "clientInfo": {"name": "prober", "version": "1.0.0"}
        }
    })
    
    # 2. Call Tool
    await send({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call", 
        "params": {
            "name": "think", 
            "arguments": {"query": "Respond with the word SUCCESS.", "internal": True}
        }
    })

    # Read output
    try:
        while True:
            line = await asyncio.wait_for(proc.stdout.readline(), timeout=30.0)
            if not line: break
            data = json.loads(line.decode())
            print(f"[RECV] {data}")
            if data.get("id") == 1:
                break
    except asyncio.TimeoutError:
        print("[TIMEOUT] Node did not respond.")
    
    proc.terminate()
    await proc.wait()

if __name__ == "__main__":
    asyncio.run(probe_node())
