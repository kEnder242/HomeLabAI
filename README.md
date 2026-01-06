# HomeLabAI

> **The Vision:**
> To build a distributed, voice-native AI ecosystem that acts as a proactive partner in the Home Lab. Like an "Iron Man" system, it lives in the background, handles complex tasks across machines (Windows/Linux/Cloud), and leverages personal knowledge to accelerate work. It is not a chatbot; it is an Operator.

## Architecture (The Triad)
*   **Brain (Linux Server):** Orchestration, RAG, Embeddings, DeepAgent.
*   **Brawn (Windows Workstation):** Heavy LLM Inference (Ollama/GPU), Microphone input.
*   **Memory (Cloud/Drive):** Synced Knowledge Base via Google Drive + rclone.

## Components
*   **VoiceGateway:** Real-time STT streaming (NeMo) and WebSocket audio pipeline.
*   **DeepAgent:** Autonomous agent framework (Forked & Patched).
*   **Infrastructure:** Sync scripts and Docker configs.
