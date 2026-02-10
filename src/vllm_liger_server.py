import os
import sys
import logging
import uvloop
from liger_kernel.transformers import apply_liger_kernel_to_mistral
from vllm.entrypoints.openai.api_server import (
    run_server, make_arg_parser, validate_parsed_serve_args
)
from vllm.utils.argparse_utils import FlexibleArgumentParser
from vllm.entrypoints.utils import cli_env_setup

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [vLLM-Liger] %(levelname)s - %(message)s')

def run():
    logging.info(f"Applying Liger-Kernel patches to Mistral architecture...")
    try:
        apply_liger_kernel_to_mistral()
        logging.info("✅ Liger-Kernel patches applied.")
    except Exception as e:
        logging.error(f"❌ Failed to apply Liger-Kernel: {e}")

    # Standard vLLM setup
    cli_env_setup()
    parser = FlexibleArgumentParser(
        description="vLLM OpenAI-Compatible RESTful API server with Liger-Kernel."
    )
    parser = make_arg_parser(parser)
    args = parser.parse_args()
    validate_parsed_serve_args(args)

    logging.info(f"Starting vLLM server with Liger optimization...")
    uvloop.run(run_server(args))

if __name__ == "__main__":
    run()