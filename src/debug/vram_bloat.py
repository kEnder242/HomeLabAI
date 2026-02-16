import torch
import time
import sys

def allocate_vram(mib):
    print(f"Allocating {mib} MiB of VRAM...")
    # Each float32 is 4 bytes
    elements = (mib * 1024 * 1024) // 4
    try:
        tensor = torch.zeros(elements, device='cuda')
        print("Allocation successful.")
        return tensor
    except Exception as e:
        print(f"Allocation failed: {e}")
        return None

if __name__ == "__main__":
    target = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    t = allocate_vram(target)
    if t is not None:
        print("Holding allocation for 60 seconds...")
        time.sleep(60)
        print("Releasing memory.")
