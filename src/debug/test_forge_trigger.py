import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import os

async def run_test():
    # We want to talk to the ALREADY RUNNING archive node.
    # But MCP stdio_client usually spawns a new one.
    # The Hub is the one managing the nodes.
    
    # Simpler: Call the tool via the Hub's MCP interface if we can.
    # Or just run the training script directly to see if it kills vLLM.
    
    print("[*] Simulating ALARM Step 6: Forge Turn...")
    target = "lab_history"
    steps = 1
    
    # This is what Step 6 does:
    # await self.residents["archive"].call_tool("lab_train_adapter", {"adapter_name": target, "steps": steps})
    
    # We'll run the training script directly as the archive node would.
    train_script = os.path.expanduser("~/Dev_Lab/HomeLabAI/src/forge/train_adapter.py")
    
    print(f"[*] Executing: python3 {train_script} --adapter {target} --steps {steps}")
    
    proc = await asyncio.create_subprocess_exec(
        "/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python3", train_script, 
        "--adapter", target, "--steps", str(steps),
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    
    # While it's running, we check if vLLM dies.
    print("[*] Training started. Monitoring vLLM...")
    
    for i in range(10):
        await asyncio.sleep(2)
        # Check if vLLM process is still alive
        vllm_proc = None
        for p in os.popen("ps -ef | grep VLLM::EngineCore | grep -v grep").read().splitlines():
             vllm_proc = p
        
        if not vllm_proc:
            print("[!] vLLM crashed during training!")
            break
        else:
            print(f"[+] vLLM still alive (Attempt {i+1}/10)")

    stdout, stderr = await proc.communicate()
    print("[*] Training finished.")
    if stdout: print(f"STDOUT: {stdout.decode()[:100]}...")
    if stderr: print(f"STDERR: {stderr.decode()[:100]}...")

if __name__ == "__main__":
    asyncio.run(run_test())
