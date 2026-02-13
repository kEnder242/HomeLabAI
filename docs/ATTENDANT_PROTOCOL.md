# 🛡️ Attendant Protocol: Silicon Lifecycle v3.6

**Goal:** Centralized, aggressive process management to prevent VRAM fragmentation and orphaned logic.

### **1. The "Lead Engineer" Lifecycle**
Manual `pkill` is now **deprecated**. All silicon-level cleanup is handled by the Lab Attendant.

*   **POST `/start`**: Automatically performs a "Silicon Sweep" of all related processes (`vllm`, `ollama`, `acme_lab`, `archive_node`) before launching. 
*   **POST `/hard_reset`**: Total scorched-earth reset. Clears all residents, inference engines, and the `round_table.lock`. 
*   **GET `/status`**: Now reports `last_error` by parsing `server.log` for `[FATAL]` signals or process exit codes.

### **2. VRAM Guard: Headroom Logic**
The Attendant enforces strict headroom to prevent the "EarNode OOM" seen in Phase 3.5.

| Engine | Headroom Required | Target Utilization |
| :--- | :--- | :--- |
| **vLLM** | 7000 MiB | 0.4 |
| **Ollama** | 3000 MiB | Dynamic |

### **3. Failure Recovery**
If the Lab Hub crashes (e.g., `AttributeError: 'NoneType' object has no attribute 'choices'`), the Attendant will detect the process exit and update `/status` immediately. 

**Recommendation:** Always check `/status` before assuming the mind is online.
