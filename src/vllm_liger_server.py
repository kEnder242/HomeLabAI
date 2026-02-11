import os
import sys
import logging
from liger_kernel.transformers import apply_liger_kernel_to_mistral
from vllm.entrypoints.openai.api_server import main as vllm_main

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [vLLM-Liger] %(levelname)s - %(message)s')

def run():
    logging.info(f"Applying Liger-Kernel patches to Mistral architecture...")
    try:
        apply_liger_kernel_to_mistral()
        logging.info("✅ Liger-Kernel patches applied.")
    except Exception as e:
        logging.error(f"❌ Failed to apply Liger-Kernel: {e}")

    logging.info(f"Starting vLLM server (Legacy Stable Entrypoint)...")
    vllm_main()

if __name__ == "__main__":
    run()
