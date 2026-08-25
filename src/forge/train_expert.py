import os
import sys
import ctypes
import time

os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

# Preload CUDA 13 runtime libraries from pip virtualenv
_cu13_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".venv/lib/python3.12/site-packages/nvidia/cu13/lib")
if os.path.exists(_cu13_dir):
    _nvjit = os.path.join(_cu13_dir, "libnvJitLink.so.13")
    if os.path.exists(_nvjit):
        try:
            ctypes.CDLL(_nvjit, mode=ctypes.RTLD_GLOBAL)
        except Exception:
            pass

try:
    from unsloth import FastLanguageModel
    import torch
    from trl import SFTTrainer
    from transformers import TrainingArguments, TrainerCallback
    from datasets import load_dataset
except ImportError:
    print("Unsloth not installed. Skipping actual import.")
    FastLanguageModel = None

class HardwarePacingCallback(TrainerCallback):
    """[FEAT-452] Pauses 5.0s between optimization steps to let host VRMs, PSU capacitors, and GPU silicon settle to baseline."""

    def __init__(self, delay_sec: float = 5.0):
        self.delay_sec = delay_sec

    def on_step_end(self, args, state, control, **kwargs):
        print(f"\n⏱️ [HARDWARE PACING] Step {state.global_step}/{state.max_steps} complete. Settling hardware for {self.delay_sec}s...", flush=True)
        time.sleep(self.delay_sec)
        print("⚡ [HARDWARE PACING] Hardware settled to baseline. Initiating next optimization pulse.\n", flush=True)


def train_expert(dataset_path: str, output_dir: str, steps: int = 60, model_name: str = "unsloth/Llama-3.2-3B-Instruct-bnb-4bit", pacing_delay: float = 5.0):
    """
    [FEAT-160] Pedigree Refinement Pipeline & [FORGE-02]
    Trains a Rank 16 LoRA adapter using Unsloth for Turing SM 7.5.
    Standardized on Llama-3.2-3B-Instruct for superior performance.
    """
    print(f"Starting training on {dataset_path} -> {output_dir} ({steps} steps, pacing_delay={pacing_delay}s)", flush=True)
    if FastLanguageModel is None:
        print("Mocking training completion since Unsloth is missing.", flush=True)
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "adapter_config.json"), "w") as f:
            f.write('{"mock": true}')
        return

    max_seq_length = min(2048, 1536)  # [FEAT-452] Clamp to 1536 for VRM/thermal headroom
    dtype = None 
    load_in_4bit = True 

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = model_name,
        max_seq_length = max_seq_length,
        dtype = dtype,
        load_in_4bit = load_in_4bit,
        low_cpu_mem_usage = True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r = 16,
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_alpha = 16,
        lora_dropout = 0,
        bias = "none",
        use_gradient_checkpointing = "unsloth",
        random_state = 3407,
        use_rslora = False,
        loftq_config = None,
    )

    dataset = load_dataset("json", data_files=dataset_path, split="train")

    def formatting_prompts_func(examples):
        # [FIX] Robust key detection to handle diverse datasets (Sentinel vs Voice vs History vs Journal Ledger)
        available_keys = list(examples.keys())
        
        # Determine which fields to use
        instr_key = "instruction" if "instruction" in available_keys else ("prompt" if "prompt" in available_keys else None)
        out_key = "output" if "output" in available_keys else ("response" if "response" in available_keys else ("text" if "text" in available_keys else None))
        
        texts = []
        if "dialogue" in available_keys:
            dialogues = examples["dialogue"]
            for d in dialogues:
                texts.append(str(d) + tokenizer.eos_token)
        elif instr_key and out_key:
            instructions = examples[instr_key]
            outputs      = examples[out_key]
            for instruction, output in zip(instructions, outputs):
                text = f"User: {instruction}\n\nAssistant: {output}" + tokenizer.eos_token
                texts.append(text)
        else:
            print(f"❌ DATASET SCHEMA ERROR: Found keys {available_keys}")
            raise KeyError("Missing required keys. Needs 'instruction'/'prompt'/'output' or 'dialogue'.")
        return { "text" : texts, }

    dataset = dataset.map(formatting_prompts_func, batched = True,)

    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text",
        max_seq_length = max_seq_length,
        dataset_num_proc = 2,
        packing = False,
        callbacks = [HardwarePacingCallback(delay_sec=pacing_delay)],
        args = TrainingArguments(
            per_device_train_batch_size = 1,
            gradient_accumulation_steps = 4,
            warmup_steps = 10,
            max_steps = steps,
            learning_rate = 2e-4,
            fp16 = not torch.cuda.is_bf16_supported(),
            bf16 = torch.cuda.is_bf16_supported(),
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = "outputs",
            report_to = "none",
        ),
    )

    trainer.train()
    
    model.save_pretrained(output_dir)
    print(f"✅ [FORGE COMPLETE] Adapter successfully trained and saved to {output_dir}", flush=True)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Unsloth LoRA Expert Fine-Tuning")
    parser.add_argument("pos_dataset", nargs="?", default=None, help="Dataset JSONL path (positional)")
    parser.add_argument("pos_output", nargs="?", default=None, help="Output LoRA dir (positional)")
    parser.add_argument("pos_steps", nargs="?", type=int, default=None, help="Training steps (positional)")
    parser.add_argument("pos_model", nargs="?", default=None, help="Base model (positional)")
    parser.add_argument("--dataset", default=None, help="Dataset JSONL path")
    parser.add_argument("--output", default=None, help="Output LoRA dir")
    parser.add_argument("--steps", type=int, default=60, help="Training steps")
    parser.add_argument("--model", default=None, help="Base model")
    parser.add_argument("--pacing-delay", type=float, default=5.0, help="Hardware settling delay in seconds between steps (default: 5.0s)")
    args = parser.parse_args()

    dataset_in = args.dataset or args.pos_dataset
    output_out = args.output or args.pos_output
    steps_in = args.steps or (args.pos_steps if args.pos_steps is not None else 60)
    model_in = args.model or args.pos_model
    pacing_delay_in = args.pacing_delay

    if not dataset_in or not output_out:
        print("Usage: python train_expert.py --dataset <dataset_jsonl> --output <output_lora_dir> [--steps N] [--model M] [--pacing-delay S]")
        sys.exit(1)

    if not model_in:
        try:
            import json
            config_path = os.path.expanduser("~/Dev_Lab/HomeLabAI/config/infrastructure.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    base = cfg.get("model_manifest", {}).get("unified-base", "")
                    if "qwen2.5-3b" in base.lower():
                        model_in = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"
                    elif "llama-3.2-3b" in base.lower():
                        model_in = "unsloth/Llama-3.2-3B-Instruct-bnb-4bit"
        except Exception:
            pass

    if not model_in:
        model_in = "unsloth/Qwen2.5-3B-Instruct-bnb-4bit"

    train_expert(
        dataset_path=dataset_in,
        output_dir=output_out,
        steps=steps_in,
        model_name=model_in,
        pacing_delay=pacing_delay_in,
    )
