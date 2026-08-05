# Lab Infrastructure: The Physical Floor
**Role: [LAB] - Silicon Laws & Environment Anchors**

> [!IMPORTANT]
> **PURPOSE:** This is the technical ledger for the physical environment.
> **[LAB]**: Hardware specs, mount points, absolute local paths, and environment-specific playbooks (e.g., Turing-specific breakthroughs).

## 📍 Physical Storage & Mounts
| Mount Point | Label | Capacity | Purpose |
| :--- | :--- | :--- | :--- |
| `/` | `rpool` | ~40GB | System OS, Configs, Logs. **High Pressure.** |
| `/home` | `rpool` | ~600GB | User data, Venvs. **High Pressure.** |
| `/speedy` | `speedy` | 150GB | **High-Speed Btrfs SSD.** Primary home for LLM weights. |
| `/mnt/2TB` | `2TB` | 2TB | Bulk storage (Ext4). |
| `/media/jallred/jellyfin` | `jellyfin` | 4TB | Media & Cold Archive (Ext4). |

## 🛠️ Tool Availability
*   **Migration**: `rsync`, `rclone` (configured for GDrive).
*   **Monitoring**: `nvidia-smi` (v550+), `df -h`, `lsblk`, `NVIDIA DCGM` (Continuous Telemetry).
*   **Automation**: `systemd` (`lab-attendant.service`).

## ⚙️ Hardware Characteristics
*   **Host**: `z87-Linux` (Native).
*   **GPU**: NVIDIA RTX 2080 Ti (11GB VRAM).
    *   **Architecture**: Turing (`sm_75`).
    *   **Constraint**: No native `bfloat16` support for fused kernels (use `float16` for Liger).
*   **Network**: Tailscale MagicDNS active.

## 📡 Transport Layer & Systemd Service Topology (V2)
| Unit / Protocol | Type | Scope | Port / Path | Purpose & Role |
| :--- | :--- | :--- | :--- | :--- |
| **`lab-attendant.service`** | Service | `system` | `:8000` / `:9999` | Acme Lab Attendant & Cognitive Hub Orchestrator (Foyer, ignition, VRAM manager). |
| **`chroma-server.service`** | Service | `user` | `:8001` | Persistent ChromaDB HTTP Vector Database (5 collections). |
| **`headroom-proxy.service`** | Service | `user` | `:8787` | Headroom Token Optimization Proxy for subagents. |
| **`opencode.socket`** | Socket | `user` | `0.0.0.0:4096` | Public Scale-to-Zero LAN Web UI Gateway (`http://192.168.1.238:4096/`). |
| **`opencode-proxy.service`** | Service | `user` | `:4096` ➔ `:4097` | Systemd Socket Proxy (`StopWhenUnneeded=true`, proxies 4096 to 4097). |
| **`opencode-core.service`** | Service | `user` | `127.0.0.1:4097` | Core OpenCode/Codex REST engine (`Headroom wrap codex serve`). |
| **`field-notes.service`** | Service | `system` | `:9001` | Python HTTP Server serving the Field Notes static dashboard. |
| **`acme-pager.service`** | Service | `system` | `:8501` | Neural Pager Streamlit activity log dashboard. |
| **`field-notes-nibbler.service`** | Service | `user` | Background | Continuous load-aware note scanner and indexer. |
| **`field-notes-nightly.timer`** | Timer | `user` | `02:00 AM` | Nightly 2:00 AM note synthesis & date aggregation sweep. |
| **vLLM Engine** | OpenAI API | `local` | `:8088` | Unified 3B Base Model inference (`llama-3.2-3b-instruct-awq`). |
| **Bicameral Hub** | WebSocket | `local` | `:8765` | Bicameral Dispatch & Node Coordination. |

## 🔗 Critical Symlinks
*   `~/Dev_Lab/models/hf_downloads` -> `/speedy/models` (In progress).

---

## 🚀 Infrastructure Playbooks

### LAB-001: Silicon Bringup (Hardware & Service Restoration)
**Objective**: Restore the Lab environment from a powered-off or crashed state.

1.  **Hardware/Driver Audit**:
    *   Execute `nvidia-smi`.
    *   **Success**: Driver version (e.g., 550+) and CUDA (e.g., 12.4+) reported.
    *   **Failure**: If "could not communicate with driver," perform kernel/driver maintenance and reboot.

2.  **The Invariant Sensory Core (EarNode)**:
    *   **Action**: Verify `EarNode` (NeMo) is responsive before starting cognitive engines.
    *   **Logic**: Sensing is the invariant constant of the Lab; reasoning is secondary.

3.  **Orchestrator Liveliness (`lab-attendant`)**:
    *   **Action**: `acme_attendant lab_heartbeat`
    *   **Verification**: Should return JSON with `[BOOT_HASH]`.
    *   **Autonomous Safety**: Employs the **Parallel Assassin [FEAT-119]** logic (`SIGKILL` + 2s kernel settle) to autonomously clear port 8765/8088 contention, eliminating manual `pkill` requirements.

4.  **Lab Server Ignition**:
    *   **Action**: `acme_attendant lab_start`
    *   **Logic**: Triggers the **Resident Handshake Gate [FEAT-165]**, blocking until all nodes are resident.
    *   **Verification**: `acme_attendant lab_status` (Watch for `[READY] Lab is Open`).

5.  **Uplink Verification**:
    *   `tail -f HomeLabAI/server.log` 
    *   Handshake via `intercom.py`.

### LAB-002: vLLM 0.16.0 Breakthrough Recipe (Turing/RTX 2080 Ti)
**Objective**: Maintain high-fidelity vLLM residency on 11GB Turing hardware without Ray/NCCL deadlocks.

#### 🍼 Baby Step 1: Residency & Inference Verified (Llama-1B)
*   **Goal**: Prove the stock v0.16.0 binary can pass the "333MiB Wall" and generate text.
*   **The Special Sauce**: `NCCL_SOCKET_IFNAME=lo` was the final missing piece, stabilizing the internal ZMQ handshakes.
*   **The Breakthrough Command**:
    ```bash
    NCCL_SOCKET_IFNAME=lo NCCL_P2P_DISABLE=1 VLLM_ATTENTION_BACKEND=XFORMERS \
    nohup ./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
        --model /speedy/models/Llama-3.2-1B-Instruct \
        --dtype float16 \
        --enforce-eager \
        --gpu-memory-utilization 0.5 \
        --max-model-len 4096 \
        --port 8088 > manual_vllm_step1.log 2>&1 &
    ```
*   **Result**: ✅ **SUCCESS**. VRAM reached 6.5GB. Coherent text ("*Pong*") verified via port 8088.

#### 🍼 Baby Step 2: Architecture Scar (Qwen-3B)
*   **Goal**: Upgrade to the "Unity" target (3B model).
*   **The Command**:
    ```bash
    NCCL_SOCKET_IFNAME=lo NCCL_P2P_DISABLE=1 VLLM_ATTENTION_BACKEND=XFORMERS \
    nohup ./.venv_vllm_016/bin/python3 -m vllm.entrypoints.openai.api_server \
        --model /speedy/models/Qwen2.5-3B-Instruct \
        --dtype float16 \
        --enforce-eager \
        --gpu-memory-utilization 0.5 \
        --max-model-len 4096 \
        --port 8088 > manual_vllm_step2.log 2>&1 &
    ```
*   **Result**: ❌ **FAILURE**. EngineCore failed with `KeyError: 'layers.0.mlp.gate_up_proj.weight'`.
*   **SCAR: Architecture Sensitivity**: vLLM 0.16.0's V1 engine is aggressive about weight-key naming. Qwen2.5 weights in `/speedy/models` lack the gate/up projection mapping expected by the v0.16.0 `Qwen2ForCausalLM` loader.

#### 🍼 Baby Step 4: SML Restoration & Phi-3.5-AWQ (The Fidelity Ladder)
*   **Goal**: Restore the "Small/Medium/Large" tiering using Turing-optimized models.
*   **Model Selection**: Standardized on **AWQ** for 3B+ models to ensure KV cache headroom.
*   **SNAG: Zombie VRAM Pressure**: Encountered a state where `nvidia-smi` reported 333MiB, but vLLM detected only 2.86GB free. This was caused by "Ghost" multiprocessing or ZMQ buffer residues from previous failed ignitions.
    *   **FIX**: A total **Silicon Purge** (`sudo fuser -kv /dev/nvidia0`) is mandatory if switching model architectures (e.g., Llama -> Phi).
*   **SNAG: FP16 Weight Pressure**: Verified that **Phi-3.5-mini (FP16)** is incompatible with 11GB vLLM v1. Its ~8GB weight footprint leaves < 1GB for KV cache after engine overhead.
    *   **FIX**: Pull and use **AWQ** versions for all models > 1B parameters.
*   **Result**: ✅ **SUCCESS**. Verified a three-tier Fidelity Ladder:
    *   **LARGE**: Llama-3.2-3B-AWQ (Verified ~6.5GB)
    *   **MEDIUM**: Phi-3.5-mini-AWQ (Verified ~5.5GB)
    *   **SMALL**: Llama-3.2-1B-FP16 (Verified ~4.5GB)

*   **SCAR: The WebSocket Hang (Mar 3, 2026)**: Attempting to `await ws.recv()` inside a synchronous shell command without a global timeout blocks the Agent turn. If the model chooses a tool instead of a direct response, the script hangs forever, triggering the CLI watchdog.
*   **STRATEGY: The Loopback Moat (127.0.0.1 vs 0.0.0.0)**:
    *   **Dev/Transitory**: Bind to `127.0.0.1` to ensure internal stability and zero external exposure during refactors. This aligns with the `lo` breakthrough (LAB-002) by preventing physical IP handshake traps.
    *   **Production**: Bind to `0.0.0.0` for appliance-grade reachability across the Bicameral network (Linux <-> Windows), secured via Cloudflare/Zero-Trust.
*   **Mandate**: Use "Trigger-Poll-Observe" pattern via Attendant registers and Trace Delta Capture.
*   **SCAR: The Physical IP Trap**: Without `NCCL_SOCKET_IFNAME=lo`, vLLM attempts handshakes on the physical NIC (192.168.x.x). On the Z87 board, this overhead causes a race condition that results in the process silently exiting during the ZMQ/NCCL initialization phase.
*   **SCAR: The HF Shadow-Lookup**: All local model paths **must be absolute** (starting with `/`). If a relative path is used, vLLM 0.16.0 defaults to a HuggingFace repository lookup and triggers an `OSError` crash.
*   **SCAR: The Watchdog Reaper**: The vLLM v1 core requires a ~45s warmup. If the parent CLI tool terminates before this completes, the background engine is often reaped unless decoupled via `nohup` or `systemd`.

### LAB-005: Modular Hub Architecture (v4.8 Refactor)
**Objective**: Decouple the monolithic `acme_lab.py` into specialized managers to improve maintainability and residency efficiency.

1.  **Sensory Layer (`SensoryManager`)**:
    *   **Role**: Handles binary audio buffers, VAD (Voice Activity Detection), and EarNode (NeMo) residency.
    *   **Invariant**: EarNode must be loaded **before** any cognitive nodes to claim contiguous VRAM.
2.  **Cognitive Layer (`CognitiveHub`)**:
    *   **Role**: Encapsulates reasoning logic, tool extraction, and node dispatching.
    *   **Feature**: Employs robust regex-based JSON extraction to handle banter-wrapped tool calls.
3.  **Observability Layer (Montana Protocol)**:
    *   **Role**: Centralized in `src/infra/montana.py`.
    *   **Function**: Reclaims log visibility from third-party libraries and injects the 4-part fingerprint `[BOOT_HASH : COMMIT : ROLE : PID]` into all streams.

4.  **Validation Checkpoints**:
    *   **The Settle Window**: 15s mandatory silicon settle during Ignition and Shutdown.
    *   **The Wall**: Pass 333MiB VRAM usage within 20s.
    *   **Residency**: Pass 6000MiB+ VRAM allocation.
    *   **Warmup**: FlashInfer attention warmup must complete (approx 45s).
    *   **Inference**: Verify with "Narf! Ping" completion.

5.  **Reaping Protocol**:
    *   **Logic**: [FEAT-316.1] SIGTERM -> 2s Settle -> SIGKILL.
    *   **Goal**: Ensure clean handle release by the NVIDIA kernel driver.

### LAB-003: The Unity Pattern (Multi-LoRA Residency)
**Objective**: Optimize multi-agent residency on the 11GB Turing budget.

> [!IMPORTANT]
> **Unity vs. SML**: The Unity Pattern (Single Active Foundation) should NOT be conflated with the **SML (Small/Medium/Large) Fallback** logic. 
> 1. **Unity** ensures that at any given moment, all active nodes share the *current* resident foundation to save VRAM. 
> 2. **SML** provides the resilience ladder to *switch* the entire foundation (the Unity base) to a different tier (e.g., 3B to 1B) during mode transitions (e.g., Text-Only to Voice Gateway).

1.  **Architecture**: The full Bicameral Mind (Pinky, Brain, Architect, Archive) should target a shared VRAM footprint using a **Unified Base Model** (e.g., Llama-3.2-3B) via vLLM 0.16.0.
2.  **Fast-Switching**: Leverage `--enable-lora` to swap node personas (Brain_v1, Pinky_v1) without reloading base weights.
3.  **SCAR: Windows Model Isolation**: Windows (Node 'Brain') does NOT need to sync with Linux models. Attempting to force identical weight sets across the bridge is a performance trap. Windows should leverage the RTX 4090's capacity for Mixtral/Llama-70B independently of the Linux resident tiering.

### LAB-004: vLLM Multi-LoRA Manifest
**Objective**: Hardcode model and adapter paths for consistent Turing residency.

1.  **Verified Foundation Paths**:
    *   **LARGE/MEDIUM**: `/speedy/models/llama-3.2-3b-instruct-awq`
    *   **SMALL**: `/speedy/models/Llama-3.2-1B-Instruct`
2.  **Adapter Path**: `/speedy/models/adapters/`.
    *   `brain_v1`: Strategic strategic adapter.
    *   `pinky_v1`: Intuitive gateway adapter.
3.  **Registration**: All models must be registered in `infrastructure.json` with absolute paths to prevent "Weight Volatility."

### LAB-006: ICM Hybrid Memory Pipeline (Daemon Embedding & Async Extraction)
**Objective**: Optimize persistent memory ingestion during high-density OpenAgent developer subagent runs.

1.  **Architecture**: Decouple synchronous tool calls from ONNX model cold-starts. Vector embeddings are generated via the resident ChromaDB daemon (`http://localhost:8001`), avoiding 2GB process spikes.
2.  **Deferred Queueing**: Tool outputs are logged to `pending_queue.jsonl` instantly and vectorized asynchronously via `icm extract-pending` during session pauses or idle windows.
3.  **Efficiency**: Eliminates 100%+ CPU spikes and 1.8GB-2.0GB RAM allocations per subagent turn while retaining 100% cross-session memory integrity.


### LAB-007: ChromaDB HTTP Vector Daemon (Port 8001)
**Objective**: Maintain a persistent background ChromaDB vector service for sub-second embedding retrieval and git pre-commit hook synchronization.

1.  **Architecture**: Managed via systemd user service `chroma-server.service` (`ExecStart=chroma run --path ~/AcmeLab/chroma_db --port 8001`).
2.  **Resource Limits**: Configured with `MemoryHigh=1G` and `MemoryMax=1.5G` to guarantee non-disruptive memory residency on host `z87-Linux`.
3.  **Circuit Breaker Integration**: Configured with `StartLimitIntervalSec=60s` and `StartLimitBurst=3` (BKM-038). All client scripts (`sync_chroma_dna.py`, `archive_node.py`, `refine_gem.py`) implement a graceful `try HttpClient(port=8001) except Exception: PersistentClient(...)` failover.

### LAB-008: Headroom Token Optimization Proxy (Port 8787)
**Objective**: Intercept subagent LLM tool outputs to compress context by 60–90% before dispatching queries to model providers.

1.  **Architecture**: Managed via systemd user service `headroom-proxy.service` (`ExecStart=python -m headroom.cli proxy --port 8787`).
2.  **Resource Limits**: Configured with `MemoryHigh=500M` and `MemoryMax=1000M` to maintain lightweight memory residency.
3.  **Circuit Breaker Integration**: Configured with `StartLimitIntervalSec=60s` and `StartLimitBurst=3` (BKM-038).

### LAB-009: Field Notes Dual-Pipeline Synthesis Daemons (Nibbler & Nightly Timer)
**Objective**: Delineate continuous load-aware background note processing from scheduled off-peak 2:00 AM maintenance sweeps.

1.  **Continuous Slow-Burn Nibbler (`field-notes-nibbler.service`)**:
    *   **Architecture**: Managed via systemd user service running `field_notes/mass_scan.py` under the virtual environment (`/home/jallred/Dev_Lab/HomeLabAI/.venv/bin/python`).
    *   **Behavior**: Executes a continuous load-aware loop ("every once in a while") that checks CPU load and VRAM utilization before invoking chunk processors (`nibble_v2.py`, `scan_queue.py`).
2.  **Nightly Maintenance Sweep (`field-notes-nightly.timer`)**:
    *   **Architecture**: Managed via systemd user timer `field-notes-nightly.timer` (`OnCalendar=*-*-* 02:00:00`) triggering oneshot service `field-notes-nightly.service`.
    *   **Behavior**: Executes `field_notes/aggregate_years.py` at 2:00 AM daily to synthesize date groupings and clean historical records.

### LAB-010: Apple M5 Inference Node Integration & Async Judge Protocol
**Objective**: Integrate Node 3 (Apple M5 MacBook Air 10-Core CPU, 32GB Unified Memory) into the Round Table topology as an ultra-fast Metal-accelerated OpenAI-compliant REST provider and asynchronous 256K sanity judge.

1.  **Node Hardware & Network Identity**:
    *   **Host**: Apple M5 MacBook Air (10-Core CPU, 32 GB Unified Memory).
    *   **Primary IP**: `192.168.1.46` (Wired Ethernet `en5` over Orbi Netgear RBR760 router).
    *   **Remote Admin SSH**: `ssh jasons-air@192.168.1.46`.
2.  **Active Software Stack & Ports**:
    *   **MLX OpenAI REST API Server**: `http://192.168.1.46:8000/v1` (`mlx_lm.server`).
    *   **Active Model**: `mlx-community/Qwen2.5-Coder-14B-Instruct-4bit`.
    *   **Open-WebUI Dashboard**: `http://192.168.1.46:3000` (Port 3000 visual management UI).
3.  **Paths & Environment Relaunch Recipes**:
    *   **MLX Venv**: `/Users/jallred/.venv-mlx/bin/mlx_lm.server --model mlx-community/Qwen2.5-Coder-14B-Instruct-4bit --host 0.0.0.0 --port 8000`
    *   **Open-WebUI Venv**: `OPENAI_API_BASE_URL="http://127.0.0.1:8000/v1" WEBUI_AUTH=False ~/.venv-webui/bin/open-webui serve --port 3000 --host 0.0.0.0`
    *   **Model Storage**: `~/.cache/huggingface/hub/`
4.  **Async 256K Evaluation & Two-Lane Feedback Loop**:
    *   Driven by `src/nodes/mlx_judge_node.py`. Evaluates full 256K turn traces asynchronously without delaying initial response streaming.
    *   **Factual/Archive Feedback**: Corrections route to ChromaDB (`:8001`) and `refine_gem.py`.
    *   **Style/Persona Feedback**: Retorts route to offline LoRA dataset (`cli_voice_v1`).
### LAB-011: OpenAgent Swarm Service Topology (Ports 4096/4097 & Scale-to-Zero)
**Objective**: Maintain high-fidelity local OpenAgent swarm delegation with Scale-to-Zero idle proxying and zero orphan port collisions.

1.  **Architecture**:
    *   **Core Engine (`opencode-core.service`)**: Managed as a systemd user service executing `/usr/local/bin/headroom wrap codex -- serve --port 4097 --hostname 127.0.0.1 --mdns false`.
    *   **Public Gateway (`opencode.socket` + `opencode-proxy.service`)**: Listens on `0.0.0.0:4096` (`TriggerLimitIntervalSec=0`) and proxies incoming LAN traffic on `http://192.168.1.238:4096/` to `127.0.0.1:4097`.
2.  **Scale-to-Zero Behavior**: `opencode-proxy.service` uses `StopWhenUnneeded=true` and `--exit-idle-time=5m` to gracefully release socket proxies when idle.
3.  **Strict Lifecycle Mandate**: All service lifecycles MUST be managed strictly via systemd (`systemctl --user start|stop|restart opencode-core.service`). Manual execution of `codex serve` or background CLI daemons (`&`, `nohup`) outside of systemd is strictly prohibited to prevent orphan process collisions on port 4097.

### LAB-012: Dual-Channel Agent Context Architecture (ICM Hook + CLaRa DNA MCP)
**Objective**: Guarantee that all builder agents (AGY, OpenAgent) automagically receive grounded FEAT specs, BKM protocols, and infrastructure playbooks in their prompt context before every turn — while maintaining on-demand tool access for deep exact-ID lookups.

1.  **Automagic Context Injection Channel (ICM Hook)**:
    *   **Engine**: ICM (`/home/jallred/.local/bin/icm`) configured via `~/.config/icm/config.toml` (`provider = "chroma"`, `chroma_url = "http://localhost:8001"`).
    *   **Hook**: Registered under `BeforeAgent` in `~/.gemini/antigravity-cli/settings.json` (`icm hook prompt`).
    *   **Behavior**: Executes semantic vector similarity searches against ChromaDB `:8001` on every prompt, automagically prepending top matching context to the prompt before turn generation.
2.  **On-Demand Tool Bridge Channel (CLaRa DNA MCP Server)**:
    *   **Engine**: `clara-dna` FastMCP server (`AcmeLab/src/clara_dna_mcp_server.py`) using `chromadb.HttpClient` on port `8001`. Zero VRAM, zero GPU, <1MB RAM.
    *   **Registration**: Registered in `~/.gemini/config/mcp_config.json` (AGY) and `HomeLabAI/.opencode.json` (OpenAgent).
    *   **Tools**: Exposes `query_dna()`, `get_protocol()`, and `list_collections()`.







