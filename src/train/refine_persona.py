"""
[FEAT-160] The Pedigree Burn: LoRA Fine-Tuning Pipeline
This script orchestrates the Unsloth fine-tuning process to encode the distilled 
18-year engineering pedigree into physical LoRA adapters for the 2080 Ti.
"""

import os
import json
import logging
import argparse

# The Unsloth framework is expected for 2080 Ti efficiency (Turing architecture)
try:
    from unsloth import FastLanguageModel
    from datasets import load_dataset
    from trl import SFTTrainer
    from transformers import TrainingArguments
except ImportError:
    logging.warning("[BURN] Unsloth or dependencies not found. This is a scaffold script.")

PORTFOLIO_DIR = os.path.expanduser("~/Dev_Lab/Portfolio_Dev")
LAB_DIR = os.path.expanduser("~/Dev_Lab/HomeLabAI")
ADAPTER_DIR = "/speedy/models/adapters"

# --- Training Configuration ---
max_seq_length = 2048 
dtype = None # Auto detection for float16 (Turing)
load_in_4bit = True # VRAM efficiency

def get_trainer(model, tokenizer, dataset, output_dir):
    return SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text",
        max_seq_length = max_seq_length,
        dataset_num_proc = 2,
        packing = False,
        args = TrainingArguments(
            per_device_train_batch_size = 2,
            gradient_accumulation_steps = 4,
            warmup_steps = 5,
            max_steps = 60, # Short burn for fast character adoption
            learning_rate = 2e-4,
            fp16 = True, # Force FP16 for Turing
            bf16 = False, # Disable BF16
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = output_dir,
        ),
    )

def format_dataset(dataset_file, persona):
    """Formats the JSON pairs into the Unsloth/Llama-3 prompt structure."""
    if not os.path.exists(dataset_file):
        logging.error(f"[BURN] Dataset {dataset_file} not found.")
        return None

    with open(dataset_file, "r") as f:
        data = json.load(f)

    formatted_data = []
    for pair in data:
        # Construct the Llama-3 instruction format
        text = f"<|begin_of_text|><|start_header_id|>system<|end_header_id|>\n\nYou are {persona}.<|eot_id|><|start_header_id|>user<|end_header_id|>\n\n{pair['instruction']}<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n{pair['response']}<|eot_id|>"
        formatted_data.append({"text": text})

    # Save temporary JSONL for datasets library
    tmp_path = dataset_file.replace(".json", ".jsonl")
    with open(tmp_path, "w") as f:
        for entry in formatted_data:
            f.write(json.dumps(entry) + "\n")
    
    return tmp_path

def execute_burn(target_persona, base_model, dataset_path):
    print(f"\n--- 🚀 IGNITING PEDIGREE BURN: {target_persona} ---")
    print(f"Base Model: {base_model}")
    print(f"Dataset: {dataset_path}")
    
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name = base_model,
            max_seq_length = max_seq_length,
            dtype = dtype,
            load_in_4bit = load_in_4bit,
        )

        model = FastLanguageModel.get_peft_model(
            model,
            r = 16, # Choose any number > 0 ! Suggested 8, 16, 32, 64, 128
            target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",],
            lora_alpha = 16,
            lora_dropout = 0, # Supports any, but = 0 is optimized
            bias = "none",    # Supports any, but = "none" is optimized
            use_gradient_checkpointing = "unsloth", # True or "unsloth" for very long context
            random_state = 3407,
            use_rslora = False,
            loftq_config = None,
        )

        formatted_path = format_dataset(dataset_path, target_persona)
        if not formatted_path: return

        from datasets import load_dataset
        dataset = load_dataset("json", data_files=formatted_path, split="train")

        output_dir = os.path.join(ADAPTER_DIR, f"{target_persona.lower().replace(' ', '_')}_v2")
        trainer = get_trainer(model, tokenizer, dataset, output_dir)
        
        print("[BURN] Training started...")
        trainer.train()
        
        print(f"[BURN] Saving LoRA to {output_dir}")
        model.save_pretrained(output_dir)
        tokenizer.save_pretrained(output_dir)
        
        print(f"--- ✅ BURN COMPLETE: {target_persona} ---")

    except Exception as e:
        print(f"[ERROR] Burn failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pedigree Burn Orchestrator")
    parser.add_argument("--base-model", default="unsloth/Llama-3.2-3B-Instruct", help="HuggingFace model ID or local path")
    args = parser.parse_args()

    # Create adapter dir if missing
    os.makedirs(ADAPTER_DIR, exist_ok=True)

    # 1. Burn Pinky
    pinky_data = os.path.join(os.path.dirname(__file__), "pinky_distilled.json")
    if os.path.exists(pinky_data):
        execute_burn("Pinky", args.base_model, pinky_data)

    # 2. Burn Shadow
    shadow_data = os.path.join(os.path.dirname(__file__), "shadow_distilled.json")
    if os.path.exists(shadow_data):
        execute_burn("Shadow_Brain", args.base_model, shadow_data)
