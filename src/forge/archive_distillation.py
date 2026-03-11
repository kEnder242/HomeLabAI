import os
import json
import glob
import logging

logging.basicConfig(level=logging.INFO)

def distill_markdown_to_dataset(input_dir: str, output_file: str):
    """
    [FORGE-01] Distills raw markdown files into instruction-response pairs
    for LoRA Unsloth training.
    """
    dataset = []
    
    if not os.path.exists(input_dir):
        logging.warning(f"Input directory {input_dir} not found. Returning empty dataset.")
        return dataset

    md_files = glob.glob(os.path.join(input_dir, "**/*.md"), recursive=True)
    
    for file_path in md_files:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            # Simple heuristic: Split by h2 or h3 headers to form pairs
            sections = content.split("##")
            for section in sections:
                if not section.strip():
                    continue
                parts = section.split("\n", 1)
                if len(parts) == 2:
                    instruction = f"Explain {parts[0].strip()}"
                    response = parts[1].strip()
                    if response:
                        dataset.append({
                            "instruction": instruction,
                            "input": "",
                            "output": response
                        })
                        
    # Save as JSONL for Unsloth
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        for entry in dataset:
            f.write(json.dumps(entry) + "\n")
            
    logging.info(f"Distilled {len(dataset)} pairs from {len(md_files)} files into {output_file}")
    return dataset

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python archive_distillation.py <input_dir> <output_jsonl>")
        sys.exit(1)
    distill_markdown_to_dataset(sys.argv[1], sys.argv[2])
