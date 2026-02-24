# 🧠 Sprint: Memory Optimization & MoE Paging
**Status:** Strategic Planning / Sandbox Definition
**Active Anchor:** Pinky (z87-Linux / 2080 Ti 11GB)

## 🎯 Objective
Implement a "Light Touch" experimental framework to enable high-capacity MoE inference (Mixtral-8x7B) and memory-efficient kernels (Liger) without destabilizing the core stability of the Lab.

---

## 🏗️ 1. The `EXPERIMENTAL_PAGING` Architecture
A non-persistent feature flag that enables a specialized inference path.

*   **Logic:** Sparsity-aware expert offloading. VRAM acts as an L1 Cache; System RAM as the backing store.
*   **Target:** Mixtral-8x7B (or DeepSeek-Coder-V2) for heavy-duty background tasks (Nightly Insights, Artifact Refinement).
*   **Isolation:** 
    *   **Venv:** Managed via `.venv_experimental` to prevent dependency drift in the Hub.
    *   **Resource Guard:** Automatic suspension of `EarNode` (NeMo) when active to reclaim ~1.8GB VRAM.
    *   **Lifecycle:** Orchestrated via `lab_attendant.py` with an "Auto-Kill" safety valve on OOM or thermal spikes (>85°C).

---

## ⚡ 2. The Kernel & Strategy Stack
*   **Liger Kernels:** Fused CUDA kernels to reduce VRAM footprint of RMSNorm, RoPE, and Attention layers.
*   **KV Cache Quantization:** Target FP8/INT8 to maximize context length within the 11GB budget.
*   **Weight-Only Quantization:** Standardize on 3.5 - 4.0 bpw (AWQ/EXL2) for the resident experts.

---

## 📅 3. Use-Case Mapping
| Priority | Task | Mode | Benefit |
| :--- | :--- | :--- | :--- |
| **High** | Nightly Insights | `PAGING_OFFLOAD` | Deep synthesis of the 18-year archive using 30B+ params. |
| **High** | Artifact Refinement | `PAGING_OFFLOAD` | High-fidelity ranking and summary generation for Diamond gems. |
| **Med** | Job Search Analysis | `PAGING_OFFLOAD` | Nuanced matching of CV to complex job descriptions. |
| **Low** | Live Intercom | `STABILITY_TIER` | Low-latency response via 3B Unified Base (Llama 3.2). |

---

## 🧪 4. Sandbox Deployment Plan
1.  **Stage 1: Environment Scaffolding**
    *   Create `.venv_experimental`.
    *   Install baseline MoE offloading dependencies (MoE-Infinity or Fiddler).
2.  **Stage 2: Feature Flag Injection**
    *   Update `lab_attendant.py` to recognize `--experimental-paging`.
    *   Implement "Downshift" logic for `EarNode` when flag is present.
3.  **Stage 3: Thermal & OOM Guard**
    *   Implement immediate SIGTERM on `nvidia-smi` thermal alarm or `torch.OutOfMemoryError`.

---

## 🏺 Engineering Constraints
*   **[SILICON-SCAR] Turing bf16:** RTX 2080 Ti (sm_75) does NOT support bfloat16 for fused Triton/Liger kernels. Use `float16` to prevent PTX codegen errors.
*   **[FEAT-075] Immutability:** No automated summarization of technical stories during refinement.
*   **[FEAT-031] Montana:** Isolate all experimental logs to `logs/experimental_paging.log`.
*   **[BKM-011] Scalpel:** All logic changes to `acme_lab.py` or `lab_attendant.py` MUST use the Atomic Patcher.
