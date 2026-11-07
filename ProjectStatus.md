# Home Lab AI: Project Status (Sep 25, 2026)

## Current Core Architecture: v6.5 "Decoupled Accountability & Unified Forge"
*   **Orchestration**: Managed via **`lab-attendant-v3.py` (systemd)** & **`accountability-watchdog.timer` (06:00 daily)**.
    *   **Autonomous Forge [FEAT-213]**: Silicon Valet logic for nightly multi-adapter LoRA induction (4 adapters).
    *   **Bilingual Attendant (V3) [FEAT-156]**: Dual REST/MCP support with SSE hot-linking and Foyer `:8765` state machine.
    *   **VRAM Guard & Quiesce [FEAT-213]**: Hardware-enforced VRAM eviction (<250MB) and 165W GPU power clamp before nightly training.
    *   **Decoupled Accountability Sentry [FEAT-619 / BKM-066]**: Out-of-band 06:00 AM independent grading watchdog with stale lock, dead PID scythe, and live endpoint verification.
    *   **Telemetry Breadcrumb Indexer [FEAT-607 / BKM-067]**: Stage-to-trace mapping in `foyer_stage_ledger.jsonl` and high-speed `read_roundtable_turn.py` CLI extractor.
*   **The Communication Hub (Bicameral Resonance & Multi-Node Round Table)**:
    *   **Unified Base Model [FEAT-030 / FEAT-687 / FEAT-689]**: Upgraded to **Qwen3.6-35B-A3B** sparse MoE via hybrid **`moe-cuda-rpc`** (NVIDIA RTX 2080 Ti 10GB CUDA0 + Intel Arc B580 12GB Vulkan0 RPC :50052, 0 MB DDR3 footprint, 35.87 tok/s generation decode, FlashAttention-2 prefill at 62.43 tok/s).
    *   **Induction Step 6 [FEAT-160]**: Nightly multi-adapter LoRA burn (`cli_voice_v1`, `lab_history_v1`, `triage_v1`, `reviewer_v1`).
    *   **5-Stage Round Table Deliberation**: Triage $\to$ Pinky HyDE $\to$ Brain Archive $\to$ Deep Thought Strategic Synthesis $\to$ Pinky Coherence Review.
*   **Synthesis Pipeline**:
    *   **Dream Synthesis [FEAT-214]**: Multi-mode persona distillation & gem refinement.
    *   **Safe-Scalpel [FEAT-198]**: Atomic, lint-gated code patching via MCP.

## Key Components & Status
| Component | Status | Notes |
| :--- | :--- | :--- |
| **NVIDIA Driver** | ✅ ONLINE | CUDA 12.4 / 13.0, 165W GPU power clamp enforced, headless display |
| **Intel Arc B580** | ✅ ONLINE | Primary HDMI display (`card0`), 16GB ReBAR active, ggml-rpc-server on :50052 |
| **Unified LLM Engine** | ✅ OPERATIONAL | Port :8088 (`moe-cuda-rpc`), zero DDR3 spilling, reasoning suppression active |
| **Lab Attendant & Foyer** | ✅ OPERATIONAL | Port :8765 operational; scale-to-zero quiescence active |
| **ChromaDB DNA Daemon** | ✅ ONLINE | Port :8001 serving feature_dna, behavioral_dna, vibe_dna, diagnostic_dna |
| **Decoupled Watchdog** | ✅ ACTIVE | `accountability-watchdog.timer` scheduled daily at 06:00 AM |
| **OpenCode Core** | ✅ ONLINE | REST port 4097 gated with 2.5G/3.0G systemd cgroup limits |

## Recent Completed Sprints
*   **SPR-110.0 "Heterogeneous MoE Dual-GPU Engine & Pure VRAM Architecture"** (`FEAT-687`, `FEAT-688`, `FEAT-689`, `FEAT-680`, `FEAT-685`, `FEAT-686`, `BKM-079`, `BKM-081`, `BKM-088`): Sliced Qwen3.6-35B-A3B MoE model across 23GB dedicated VRAM pool (zero DDR3 spilling) using native CUDA FlashAttention-2 + Vulkan RPC hybrid backend. Delivered 62.43 tok/s prompt prefill and 35.87 tok/s decode (+25.8% to +49.4% over pure Vulkan). Verified physical HDMI topology with 16GB ReBAR on Arc B580 and headless RTX 2080 Ti. Ingested 105 SCRIPT DNA items into ChromaDB with universal bucketed ripgrep. Integrated Nibbler pipeline and certified 5-stage cognitive Waterfall flow end-to-end on physical silicon.
*   **SPR-105.0 "Pure Waterfall Restoration & Decoupled Tri-Anchor Alignment"** (`FEAT-658`, `FEAT-451`, `FEAT-330`, `FEAT-619`, `FEAT-523`, `BKM-082`, `BKM-086`): Restored pure decoupled waterfall cognitive flow, excised artificial min token floor to enforce concise ceiling headroom, excised 7-week watchdog green lie with 30h mtime sentinel, unblocked Nibbler intake pipeline with Foyer session auth, and certified end-to-end on live silicon.
*   **SPR-91.0 "Decoupled Accountability Watchdog & Dead PID Sentry"** (`FEAT-619`, `BKM-066`): Decoupled morning accountability grading from batch execution into an independent out-of-band systemd timer.
*   **SPR-90.0 "Applied Writer Studio & AST Backflow"** (`FEAT-614`–`FEAT-618`, `BKM-064`, `BKM-065`, `INS-036`): Unified projection toolbar, review panel dialogue, and polymorphic `PHL` $\to$ `INS` mutations.
*   **SPR-88.0 "Nightly Accountability Digest & Dashboard Integration"** (`FEAT-607`, `FEAT-608`): Multi-stage health evaluation matrix, expandable digest cards in `status.html`, and synthetic morning round table probes.

*Refer to `Portfolio_Dev/FeatureTracker.md` and `HomeLabAI/docs/Protocols.md` for permanent technical DNA.*
