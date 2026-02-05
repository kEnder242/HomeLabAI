import torch
import time
import os
import sys

def mps_test(duration=30):
    if not torch.cuda.is_available():
        print("❌ CUDA not available.")
        return

    device = torch.device("cuda")
    print(f"🚀 Starting MPS test on {torch.cuda.get_device_name(0)}")
    print(f"📁 Pipe Directory: {os.environ.get('CUDA_MPS_PIPE_DIRECTORY', 'NOT SET')}")
    
    # Large matrices to saturate Turing cores
    size = 4096
    a = torch.randn(size, size, device=device)
    b = torch.randn(size, size, device=device)
    
    start_time = time.time()
    count = 0
    while time.time() - start_time < duration:
        c = torch.matmul(a, b)
        torch.cuda.synchronize() # Force wait for GPU
        count += 1
        if count % 100 == 0:
            print(f"Iter {count}...")
            
    print(f"✅ Finished {count} iterations in {duration}s.")

if __name__ == "__main__":
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    mps_test(duration)
