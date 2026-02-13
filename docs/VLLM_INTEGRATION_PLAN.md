# vLLM Iterative Integration Plan: The Path to High-Throughput Reasoning

## Phase 1: Stability (The AWQ Foundation) [PRIORITY 1]
- **Goal:** Get vLLM running without OOM on the 11GB 2080 Ti alongside NeMo.
- **Strategy:** Use **Llama-3.1-8B-AWQ** with `--gpu-memory-utilization 0.5`.
- **Reasoning:** Hard-capping vLLM to ~5.5GB is the only way to ensure NeMo (3-4GB) and the system overhead don't collide.
- **Verification:** Integration test `test_vram_guard.py` must pass with `USE_BRAIN_VLLM=1`.

## Phase 2: Persona Persistence (The Sentinel Profile) [PRIORITY 2]
- **Goal:** Enable background interjections without starving the KV cache.
- **Strategy:** Implement a "Sentinel" startup profile with `--max-model-len 2048` and aggressive cache eviction.
- **Reasoning:** The Brain needs a permanent but small footprint to "listen." Large context is a luxury for active sessions, not background monitoring.
- **Verification:** Brain successfully interjects on "PCIe error" keywords while the Lab is IDLE.

## Phase 3: Performance (The Liger Optimization) [PRIORITY 3]
- **Goal:** Restore the 80% VRAM reduction efficiency.
- **Strategy:** Integrate `vllm_liger_server.py` logic into the Lab Attendant loader.
- **Reasoning:** Liger-Kernel's fused operations are the "theoretical peak" for our Turing hardware. This will eventually allow us to move from 8B to 14B+ models.
- **Verification:** Benchmarking tokens/sec and VRAM floor vs. baseline vLLM.

## Strategic Loading/Unloading
- **The "Transition Space" Pattern:** The Lab Attendant will implement a "Cooldown" period. When moving from a heavy Intercom session back to "Slow Burn," it will explicitly purge the vLLM KV cache or unload the engine to free VRAM for the `Nibbler`.
