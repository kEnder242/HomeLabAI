# Copyright 2025-2026 Jason Allred (Pre-Employment Snapshot: 2026-11-22)
# SPDX-License-Identifier: Apache-2.0
from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("meta-llama/Llama-3-70b-chat-hf")
tokenizer.save_pretrained("/home/jallred/DeepAgent/tokenizers/llama3-70b-tokenizer")
