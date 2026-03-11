
import os
import time
import torch
from moe_infinity import MoE

model_path = "models/hf_downloads/Mixtral-8x7B-Instruct-v0.1"
offload_dir = os.path.abspath("models/moe_offload")

if not os.path.exists(offload_dir):
    os.makedirs(offload_dir)

# Constructing the config dictionary based on ArcherConfig
config = {
    "offload_path": offload_dir,
    "device_memory_ratio": 0.7,  # Leave some headroom for EarNode/System
    "host_memory_ratio": 0.8,
    "prefetch": True
}

print(f"Initializing MoE-Infinity with {model_path}...")
start_time = time.time()

try:
    # MoE class takes (model_name_or_path, config)
    moe = MoE(model_path, config)
    print(f"Initialization complete in {time.time() - start_time:.2f}s")

    # The MoE class wraps a model. Based on entrypoints/big_modeling.py, 
    # it seems it might have a .model attribute or act as a wrapper.
    # Looking at the example in big_modeling.py: outputs = model.generate(input_ids)
    
    # We need a tokenizer. Let's use the one from the model path.
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_path)
    
    input_text = "Explain the concept of Mixture of Experts in one paragraph."
    print(f"\nPrompt: {input_text}")
    
    inputs = tokenizer(input_text, return_tensors="pt")
    input_ids = inputs.input_ids.to("cuda")

    start_gen = time.time()
    # Using the generate method shown in the Example docstring
    with torch.no_grad():
        output_ids = moe.generate(input_ids, max_new_tokens=50)
    gen_time = time.time() - start_gen

    response = tokenizer.decode(output_ids[0], skip_special_tokens=True)
    print(f"\nResponse: {response}")
    print(f"\nGeneration time: {gen_time:.2f}s")

except Exception as e:
    print(f"Error during MoE-Infinity execution: {e}")
    import traceback
    traceback.print_exc()
