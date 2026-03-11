import os
import sys
import tempfile

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from forge.archive_distillation import distill_markdown_to_dataset
from forge.train_expert import train_expert

def test_forge_fidelity():
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a mock expertise md
        input_dir = os.path.join(temp_dir, "expertise")
        os.makedirs(input_dir)
        md_file = os.path.join(input_dir, "test.md")
        with open(md_file, "w") as f:
            f.write("## RAPL Telemetry\nRAPL provides power constraints.")
            
        output_file = os.path.join(temp_dir, "dataset.jsonl")
        
        # Test Distillation
        dataset = distill_markdown_to_dataset(input_dir, output_file)
        assert len(dataset) == 1
        assert "RAPL Telemetry" in dataset[0]["instruction"]
        assert "RAPL provides power constraints." in dataset[0]["output"]
        
        # Test Train Expert (Mocked)
        output_lora_dir = os.path.join(temp_dir, "lora_output")
        train_expert(output_file, output_lora_dir)
        
        # Check if mocked save worked
        assert os.path.exists(os.path.join(output_lora_dir, "adapter_config.json"))
