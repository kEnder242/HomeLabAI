# SPRINT [v4.7]: Micro-Resilience (Qwen-Ladder Hardening)
**Status:** ACTIVE | **Focus:** Ultra-Stable High-Throughput Reasoning

## 🎯 Objective
Pivot from heavy/unstable architectures to a **Micro-Resilience Ladder** (Qwen 1.5B/0.5B + Llama 1B). Achieve "Appliance-Grade" reliability on the 11GB Turing budget with ~50% VRAM headroom and automated SML fallback.

## 🏛️ The Micro-Ladder (v4.7.1)
| Tier | Model | Format | VRAM (Est) | Utilization | Goal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LARGE** | **Qwen 2.5 1.5B** | AWQ | ~5.5GB | 0.5 | Micro-Strategic reasoning (Unity Base). |
| **MEDIUM** | **Llama 3.2 1B** | FP16 | ~5.0GB | 0.5 | Analytical logic & tool triage. |
| **SMALL** | **Qwen 2.5 0.5B** | AWQ | ~3.8GB | 0.5 | Instant Reflex / Routing. |

## 🛠️ Hardening Tasks (Post-Mortem)
1.  **[ASSASSIN] Scorched Earth**: Update `cleanup_silicon` in the Lab Attendant to proactively check for and terminate `ollama` and `llama-box` binaries to prevent "Hidden VRAM" collisions.
2.  **[SML] Hysteresis Loop**: Implement automated downshift to `SMALL` when `mic_state == active`. Add a 5-minute cool-down timer before allowing an upshift to prevent "Model Flapping."
3.  **[BOOT] WARM_WAIT**: Hold the Hub in a `BOOT_WAIT` state (Port 8765) until the vLLM `/v1/models` endpoint returns a 200 (FlashInfer warmup completion).
4.  **[LORA] Persona Integrity**: Verify that the `lora_name` is correctly applied by vLLM to differentiate "Brain" from "Pinky" on the shared 1.5B Unity base.
5.  **[LOG] Global Montana Decorator**: Implement a base class decorator for all Nodes to automatically trigger `reclaim_logger()` after initialization, neutralizing NeMo/ChromaDB log hijacking globally.

## 🏺 Scars & Invariants
- **[SCAR-09] Gemma 2 Instability**: Tabled for Turing (Compute 7.5). Gemma 2's `float16` instability and `bfloat16` hardware requirement make it physically incompatible with our "High Fidelity" goal on this host.
- **[SCAR-10] vLLM V1 Handshaking**: Requires `NCCL_SOCKET_IFNAME=lo` to prevent internal timeouts on the physical Z87 NIC.
- **[UNITY] Single Foundation**: Unity (residency) and SML (tiering) are now distinct protocols. Unity shares the base; SML swaps it.

