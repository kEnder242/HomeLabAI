
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
import time
import os
from liger_kernel.transformers import apply_liger_kernel_to_qwen2

def get_memory():
    return torch.cuda.memory_allocated() / 1024**2

model_path = "models/hf_downloads/Qwen2.5-3B-Instruct"

if not os.path.exists(model_path):
    print(f"Error: {model_path} not found.")
    exit(1)

print(f"Loading tokenizer from {model_path}...")
tokenizer = AutoTokenizer.from_pretrained(model_path)

print("--- Baseline (Without Liger) ---")
torch.cuda.empty_cache()
start_mem = get_memory()
model = AutoModelForCausalLM.from_pretrained(
    model_path, 
    dtype=torch.float16, 
    device_map="cuda"
)
end_mem = get_memory()
print(f"VRAM used by model: {end_mem - start_mem:.2f} MB")

input_text = "The quick brown fox jumps over the lazy dog."
inputs = tokenizer(input_text, return_tensors="pt").to("cuda")
with torch.no_grad():
    outputs = model(**inputs)
print(f"Forward pass successful. Current VRAM: {get_memory():.2f} MB")

del model
torch.cuda.empty_cache()
time.sleep(2)

print("\n--- With Liger Kernels ---")
apply_liger_kernel_to_qwen2()

start_mem = get_memory()
model_liger = AutoModelForCausalLM.from_pretrained(
    model_path, 
    dtype=torch.float16, 
    device_map="cuda"
)
end_mem = get_memory()
print(f"VRAM used by model (Liger): {end_mem - start_mem:.2f} MB")

with torch.no_grad():
    outputs = model_liger(**inputs)
print(f"Forward pass (Liger) successful. Current VRAM: {get_memory():.2f} MB")

print("\nExperiment complete.")
