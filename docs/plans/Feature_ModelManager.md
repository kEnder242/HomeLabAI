# Feature Draft: Pinky as Model Manager

**Status:** Backlog / Concept
**Related to:** Item #10 (Model Management)

## Concept
Pinky acts as the "Gateway" not just for queries, but for the AI resources themselves. He autonomously manages the model inventory on the Windows host (The Brain).

## Capabilities

### 1. Autonomous Model Selection & Pulling
*   **Trigger:** If a user query requires a specialized domain (e.g., "coding," "medical," "roleplay"), Pinky identifies that the currently loaded Brain model is insufficient.
*   **Action:** Pinky issues a command to the Windows host to `ollama pull <specialized_model>`.
*   **Constraint:** Pinky checks available disk space and VRAM before pulling. If space is low, he may delete unused models (LRU - Least Recently Used) or ask for permission.

### 2. "The Loading Screen Persona"
*   **Problem:** Large model loads/pulls take time (minutes).
*   **Solution:** Pinky fills the silence.
    *   *Pinky:* "Narf! I'm feeding the Brain a new encyclopedia! It's a big one... 5 gigabytes! *chewing noises*... Almost there!"
*   **Technical:** Pinky receives progress updates from the Ollama API and translates them into in-character status messages.

### 3. Model "Vibe Check" (The Savant Trait)
*   Pinky maintains a metadata registry of models (e.g., "This one is grumpy," "This one is good at Python").
*   He selects the Brain's "personality" based on the task.

## Technical Requirements
*   **Ollama Management API:** Pinky (Linux) needs access to `/api/pull`, `/api/delete`, and `/api/tags` on the Windows host.
*   **System Metrics:** Pinky needs to query Windows disk space (via a small agent or SSH command).
