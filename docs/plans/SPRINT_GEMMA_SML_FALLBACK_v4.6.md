# SPRINT [v4.6]: Gemma-Infused Resilience (SML Fallback)
**Status:** ACTIVE | **Focus:** VRAM-Efficient High-Fidelity Reasoning

## 🎯 Objective
Stabilize the "Both" (Voice + Logic) requirement on the 11GB Turing budget by replacing the heavy Llama-3B (LARGE) with a "Shrunk LARGE" (Gemma 2 2B AWQ) and implementing automated SML fallback triggers.

## 🏛️ The Fidelity Ladder (v4.6)
| Tier | Model | Format | VRAM (Est) | Utilization | Goal |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **LARGE** | **Gemma 2 2B-it** | AWQ | ~4.5GB | 0.4 | Strategic reasoning & complex coding. |
| **MEDIUM** | **Phi-3.5-mini** | AWQ | ~6.5GB | 0.4 | High-fidelity analytical/logic tasks. |
| **SMALL** | **Llama-3.2-1B** | FP16 | ~4.5GB | 0.3 | Fast routing & reflex responses. |

## 🛠️ Implementation Tasks
1.  **[MODEL] Weight Acquisition**: Download `bartowski/gemma-2-2b-it-AWQ` to `/speedy/models/`.
2.  **[CONFIG] Characterization**: Update `vram_characterization.json` with the new Gemma-centric LARGE tier.
3.  **[LOGIC] SML Fallback (FEAT-148)**:
    *   **Downshift Trigger**: If `mic_state == active` AND `vram_usage > 10.7GB` -> Force `SMALL` tier.
    *   **Upshift Trigger**: If `mic_state == inactive` for > 5m AND `query_complexity == HIGH` -> Restore `LARGE` (Gemma).
4.  **[TURING] Compatibility Check**: Verify Gemma 2 performance on Compute 7.5 (Float16 fallback).

## 🚀 Execution Strategy
1.  **Purge & Prime**: Standard silicon cleanup.
2.  **Residency Test**: Load EarNode FIRST, then Ignite Gemma 2 2B (Util 0.4).
3.  **Stress Test**: Perform simultaneous transcription and complex reasoning to monitor VRAM spikes.

## 🏺 Scars & Invariants
- **[SCAR-09] bfloat16 hardware**: Turing lacks native bf16. vLLM MUST cast Gemma 2 to float16/float32 automatically.
- **[UNITY] Single Foundation**: At any moment, only ONE Unity Base is active. SML swaps the base, Unity shares it.
