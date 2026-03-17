import os
import sys

try:
    from unsloth import FastLanguageModel
    import torch
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import load_dataset
except ImportError:
    print("Unsloth not installed. Skipping actual import.")
    FastLanguageModel = None

def train_expert(dataset_path: str, output_dir: str, model_name: str = "unsloth/Llama-3.2-3B-Instruct"):
    """
    [FORGE-02] Trains a Rank 16 LoRA adapter using Unsloth for Turing SM 7.5.
    """
    print(f"Starting training on {dataset_path} -> {output_dir}")
    if FastLanguageModel is None:
        print("Mocking training completion since Unsloth is missing.")
        os.makedirs(output_dir, exist_ok=True)
        with open(os.path.join(output_dir, "adapter_config.json"), "w") as f:
            f.write('{"mock": true}')
        return

    max_seq_length = 2048 
    dtype = None 
    load_in_4bit = True 

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = model_name,
        max_seq_length = max_seq_length,
        dtype = dtype,
        load_in_4bit = load_in_4bit,
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
        # [FIX] Robust key detection to handle diverse datasets (Sentinel vs Voice vs History)
        available_keys = list(examples.keys())
        
        # Determine which fields to use
        instr_key = "instruction" if "instruction" in available_keys else ("prompt" if "prompt" in available_keys else None)
        out_key = "output" if "output" in available_keys else ("response" if "response" in available_keys else ("text" if "text" in available_keys else None))
        
        if not instr_key or not out_key:
            print(f"❌ DATASET SCHEMA ERROR: Found keys {available_keys}")
            raise KeyError("Missing required keys. Needs 'instruction' or 'prompt' and 'output' or 'response'.")

        instructions = examples[instr_key]
        outputs      = examples[out_key]
        texts = []
        for instruction, output in zip(instructions, outputs):
            text = f"User: {instruction}\n\nAssistant: {output}" + tokenizer.eos_token
            texts.append(text)
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
        args = TrainingArguments(
            per_device_train_batch_size = 2,
            gradient_accumulation_steps = 4,
            warmup_steps = 5,
            max_steps = 60,
            learning_rate = 2e-4,
            fp16 = not torch.cuda.is_bf16_supported(),
            bf16 = torch.cuda.is_bf16_supported(),
            logging_steps = 1,
            optim = "adamw_8bit",
            weight_decay = 0.01,
            lr_scheduler_type = "linear",
            seed = 3407,
            output_dir = "outputs",
        ),
    )

    trainer.train()
    
    model.save_pretrained(output_dir)
    print(f"Saved adapter to {output_dir}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python train_expert.py <dataset_jsonl> <output_lora_dir>")
        sys.exit(1)
    train_expert(sys.argv[1], sys.argv[2])
