import os
import logging
import uvloop
import liger_kernel.transformers as lt
from vllm.entrypoints.openai.api_server import (
    run_server, make_arg_parser, validate_parsed_serve_args
)
from vllm.utils.argparse_utils import FlexibleArgumentParser
from vllm.entrypoints.utils import cli_env_setup

# Hard-set VLLM_USE_V1=0 to avoid experimental engine crashes
os.environ["VLLM_USE_V1"] = "0"

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [vLLM-Liger] %(levelname)s - %(message)s'
)

def apply_dynamic_liger(model_name: str):
    """Model-aware Liger kernel application."""
    model_lower = model_name.lower()
    logging.info(f"Applying Liger logic for model: {model_name}")
    
    if "gemma2" in model_lower or "gemma-2" in model_lower:
        logging.info("Applying Liger-Kernel to Gemma 2 architecture...")
        lt.apply_liger_kernel_to_gemma2()
    elif "mistral" in model_lower:
        logging.info("Applying Liger-Kernel to Mistral architecture...")
        lt.apply_liger_kernel_to_mistral()
    elif "llama" in model_lower:
        # Llama 2, 3, 3.1, and 3.2 share the same base architecture in Liger
        logging.info("Applying Liger-Kernel to Llama architecture...")
        lt.apply_liger_kernel_to_llama()
    else:
        logging.warning(f"No specific Liger patch for {model_name}. Defaulting to Llama-native kernel.")
        # Default to Llama-native as it's our Unity standard
        lt.apply_liger_kernel_to_llama()

def run():
    # Standard vLLM setup
    cli_env_setup()
    parser = FlexibleArgumentParser(
        description="vLLM OpenAI-Compatible RESTful API server with Liger-Kernel."
    )
    parser = make_arg_parser(parser)
    args = parser.parse_args()
    validate_parsed_serve_args(args)

    apply_dynamic_liger(args.model)

    logging.info(f"Starting vLLM server with Liger. Model: {args.model}")
    uvloop.run(run_server(args))

if __name__ == "__main__":
    run()
