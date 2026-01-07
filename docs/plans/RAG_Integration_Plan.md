# RAG Integration & Latency Optimization Plan

**Goal:** Transform the Voice Gateway from a "Chatbot" into a "Knowledge Assistant" that knows your personal notes, while ensuring snappy response times.

---

## Part 1: Killing the Latency (The "Wake Signal")

**The Problem:** Large models on Windows (via Ollama) offload from VRAM to save power. Reloading them takes ~10-50 seconds ("Cold Start").
**The Solution:** Send a "Wake Up" signal the moment voice activity is detected, *before* the user finishes their sentence.

### Implementation Strategy
1.  **Trigger:**
    *   In `src/audio_server.py`, detect when `RMS > SILENCE_THRESHOLD` (Voice Activity Detected).
    *   OR trigger on the very first transcribed token.
2.  **Action:**
    *   Fire an asynchronous, non-blocking HTTP request to Ollama.
    *   **Endpoint:** `/api/generate`
    *   **Payload:** `{"model": "llama3:latest", "keep_alive": "5m"}` (This loads the model without generating text).
3.  **Outcome:** By the time the user finishes speaking (3-5s), the model is loading or loaded.

---

## Part 2: The Knowledge Engine (RAG)

**The Problem:** The LLM knows the world, but it doesn't know your "HomeLabAI" notes or your "Resume".
**The Solution:** Index `~/knowledge_base` (Google Drive) locally and inject relevant snippets into the prompt.

### Architecture
*   **Database:** `ChromaDB` (Local, file-based, runs inside `audio_server.py` process).
*   **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (Running on Linux CPU/GPU).
*   **Source:** `~/knowledge_base` (synced via rclone).

### Workflow (The "Thinking" Loop 2.0)
1.  **User Speaks:** "What was the plan for the Voice Gateway?"
2.  **Transcription:** `src/audio_server.py` captures text.
3.  **Search:**
    *   Generate embedding for the query.
    *   Query ChromaDB for top 3 matching chunks from `~/knowledge_base`.
    *   *Result:* "VoiceAssistantPlan.md: ...Gateway: z87-Linux..."
4.  **Prompt Assembly:**
    *   Construct:
        ```text
        System: You are a helpful assistant. Use the context below to answer.
        Context: ... (VoiceAssistantPlan.md content) ...
        User: What was the plan for the Voice Gateway?
        ```
5.  **Inference:** Send assembled prompt to Windows Ollama.

---

## Part 3: Step-by-Step Implementation

### Phase 3.1: The Indexer
*   [ ] Create `src/indexer.py`.
*   [ ] Scan `~/knowledge_base` for `.md` and `.txt` files.
*   [ ] Chunk text (e.g., 500 characters).
*   [ ] Embed and store in ChromaDB.

### Phase 3.2: The Wake Signal
*   [ ] Modify `src/audio_server.py` to add `prime_ollama()` async task.
*   [ ] Call it on first detected audio chunk.

### Phase 3.3: Integration
*   [ ] Import `chromadb` in `src/audio_server.py`.
*   [ ] Intercept the "Turn End" event.
*   [ ] Perform lookup -> Construct Prompt -> Call Ollama.

