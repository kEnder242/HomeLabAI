# Home Lab AI Project Overview

## Goals

- Build a **hybrid local LLM setup** using:
  - **Linux server** for hosting models, inference services, embeddings, Docker workloads, and GPU acceleration.
  - **Windows desktop** for heavy-duty local LLM workloads (via Ollama/GPU), microphone input, and fast local desktop clients.
- Get **DeepAgent** (open-source agent framework) running locally, with local models and/or remote Ollama backends.
- Host supporting services:
  - Embeddings (MiniLM or better)
  - Wisper - See https://github.com/SYSTRAN/faster-whisper and https://github.com/speaches-ai/speaches 
  - RAG tools like **OpenNotebook** (NotebookLM-style)
- Eventually explore efficient model deployments using emerging techniques (sparse inference, quantization alternatives, etc.).


## Current Environment

### Windows Machine (Heavy Lifting)
- **OS:** Windows 11
- **GPU:** NVIDIA (CUDA-capable)
- **LLM Runtime:** Ollama installed and working
- **Models Installed in Ollama:** Multiple (e.g., Llama 3 variants)
- **Role:** Primary inference host for large LLMs

### Linux Machine (Host/Coordinator)
- **OS:** Ubuntu
- **Role:**
  - Runs DeepAgent orchestrator
  - Hosts Docker embedding service
  - Acts as the “brain” for agent routing
- **AI Tools Installed:**
  - Docker + GPU drivers
  - Container hosting `all-MiniLM-L6-v2` embedding model
  - Verified endpoint: `http://localhost:5005/v1/`

### Docker Embedding Model
- **Container Model:** `sentence-transformers/all-MiniLM-L6-v2`
- **Expose Port:** 5005
- **Available via:** `GET /v1/models`
- **Unclear Functions:** Embedding generation endpoints returned blank; may require:
  - Correct OpenAI-compatible embedding routes
  - Reviewing server implementation
  - Switching to a confirmed embedding server (e.g., Text-Embeddings-Inference or HuggingFace TEI)

---

## Networking Layout
- **Linux Host (DeepAgent)** → Calls → **Windows Ollama (LLMs)**
- **Linux Host** → Calls → **Docker Embedding Service**
- **Agents** can run on either machine, but control flow originates on Linux.

---

## Capabilities Verified Working
- Docker container launches successfully
- Ollama models load and respond on Windows
- CUDA and drivers are functioning on both systems
- DeepAgent runs and can call local/remote models (except embeddings not verified)
- Network communication between Linux ↔ Windows confirmed

---

## Outstanding Questions / Items to Validate
- Is the `all-MiniLM-L6-v2` Docker runtime embedding endpoint implemented or incomplete?
- Does DeepAgent accept arbitrary embedding URLs, or only specific API formats?
- Should the embedding service be replaced with HF’s Text Embedding Inference (TEI)?
- Do you want to unify everything behind a single config or keep modular services?

---

## Future Plans
### 1. Migrate to Sparse Inference (PyTorch 2.5+)
- Incorporate models that support structured sparsity
- Evaluate which LLMs already ship with sparse-friendly weight formats
- Potentially deploy via:
  - vLLM (when sparse support matures)
  - PyTorch ExecuTorch or TensorRT-LLM sparse modes

### 2. Improve Multi-Agent Setup
- Configure DeepAgent for:
  - Document ingestion
  - Embedding search
  - Multi-step reasoning pipelines
- Possibly move to “thinking models” like Kimi K2 when available

---

## Working Summary
You have a fully functioning hybrid home-lab with:

- **Windows GPU box** running ollama for large LLM inference.
- **Linux host** coordinating agents and providing embeddings via Docker.
- **DeepAgent** partially configured and ready for full hybrid operation.
- **GPU drivers across both systems verified.**
- **Embeddings container installed**, though its capabilities need re-verification.
- **Everything network-reachable and modular** so agents can call across machines.

This structure supports:
- Running reasoning/planning centrally (Linux)
- Offloading heavy LLM compute (Windows)
- Offloading embeddings (Docker service)
- Adding future models or pipelines as needed

# Index of URLs considered

### Models & Frameworks
- MiniLM: https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2  
- Kimi-K2-Thinking (MLX): https://huggingface.co/mlx-community/Kimi-K2-Thinking  
- DeepAgent - https://github.com/RUC-NLPIR/DeepAgent 

### Whisper / Speech-to-Text
- faster-whisper: https://github.com/SYSTRAN/faster-whisper  
- faster-whisper (AIXerum fork): https://github.com/AIXerum/faster-whisper  
- whisper.cpp: https://github.com/ggerganov/whisper.cpp  

### Research / Technology
- Sparse inference:  
https://pytorch.org/blog/beyond-quantization-bringing-sparse-inference-to-pytorch/  

### OpenNotebook  
- Website: https://www.open-notebook.ai/  
- GitHub: https://github.com/lfnovo/open-notebook  
- Article: https://www.zdnet.com/article/i-found-an-open-source-notebooklm-alternative-that's-powerful-private-and-free/  

### Documentation Mentioned
- Google Nested Learning:  
https://research.google/blog/introducing-nested-learning-a-new-ml-paradigm-for-continual-learning/

---

## DeepAgent Configuration and Bug Fixes

This section documents the local modifications made to the DeepAgent project files to enable its operation in a hybrid environment and to address several runtime issues.

### Modified Files:

*   **`deepagent_run_deep_agent_modified.py`**: This file contains the modified version of `src/run_deep_agent.py`. Key changes include:
    *   **Tokenizer Chat Template Handling:** Added logic to gracefully handle tokenizers without a predefined `chat_template`, improving compatibility with Ollama-served models.
    *   **Model Short Name Initialization:** Ensured that the `model_short_name` variable is always assigned, preventing `UnboundLocalError` when using custom model names.
    *   **Data List Initialization:** Initialized the `data_list` variable to prevent `UnboundLocalError` during data loading.
    *   **API Bank Data Loading:** Corrected the conditional logic for loading `api_bank` data to ensure proper assignment of `data_list`.
    *   **Concurrency Limit:** Reduced the default `--concurrent_limit` from 32 to 4 to prevent overwhelming the Ollama server during concurrent requests.
    
*   **`deepagent_my_config_modified.yaml`**: This file contains the configured `config/my_config.yaml`. It includes settings tailored for the hybrid setup, such as:
    *   **Model Selection:** Configured to use `mixtral:8x7b` as the main reasoning model.
    *   **Tokenizer Paths:** Set to use the already-cached `bert-base-uncased` tokenizer paths.
    *   **Dataset Paths:** Added `gaia_data_path`, `tmdb_data_path`, and `tmdb_toolset_path` to correctly locate dataset and tool specification files.
    *   **API Keys:** Included placeholder for `tmdb_access_token`.

These modifications aim to enhance the stability, compatibility, and performance of DeepAgent within this specific hybrid home-lab environment.