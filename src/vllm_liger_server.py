import os
import logging

# Hard-set VLLM_USE_V1=0 to avoid experimental engine crashes
os.environ["VLLM_USE_V1"] = "0"

import uvloop
from liger_kernel.transformers import apply_liger_kernel_to_gemma2

from vllm.entrypoints.openai.api_server import (
    run_server, make_arg_parser, validate_parsed_serve_args
)
from vllm.utils.argparse_utils import FlexibleArgumentParser
from vllm.entrypoints.utils import cli_env_setup

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [vLLM-Liger] %(levelname)s - %(message)s')

def run():
    logging.info("Applying Liger-Kernel patches to Gemma 2 architecture...")
    try:
        apply_liger_kernel_to_gemma2()
        logging.info("✅ Liger-Kernel applied to Gemma 2 architecture.")
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

    logging.info(f"Starting vLLM server with Liger optimization. Model: {args.model}")
    uvloop.run(run_server(args))

if __name__ == "__main__":
    run()
