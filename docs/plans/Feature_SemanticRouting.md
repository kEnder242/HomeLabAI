# Feature Plan: Semantic Routing (The "Smart" Corpus Callosum)

**Status:** Planned
**Target:** HomeLabAI v2.1
**Objective:** Decouple "Decision Making" from "Personality" by empowering the Lab Orchestrator (`acme_lab.py`) to route queries based on vector similarity.

## The Problem
Currently, **Pinky** (the LLM) is the sole decision-maker. This leads to:
1.  **Personality Bleed:** Pinky might refuse to delegate because of his "persona" (stubbornness).
2.  **Latency:** We wait for Pinky to generate tokens just to decide "I shouldn't handle this."
3.  **Prompt Fragility:** We rely on "begging" the prompt to behave.

## The Solution: Vector-Based Routing
We move the routing logic into the `Corpus Callosum` (`acme_lab.py`) using the existing `all-MiniLM-L6-v2` embedding model hosted in `archive_node.py`.

### Architecture Flow

1.  **User Input:** Client sends text to `acme_lab.py`.
2.  **Classification (Fast):**
    *   `acme_lab` sends query to `archive_node.classify(query)`.
    *   `archive_node` compares the query vector against pre-defined **Anchor Vectors**.
3.  **Decision (Deterministic):**
    *   If `Distance(Query, Brain_Anchor) < Threshold`: **Route Directly to Brain**.
    *   Else: **Route to Pinky**.

### The Anchors

We define semantic anchors to represent the "Vibe" of each node.

*   **Brain Anchors:**
    *   "Calculate pi"
    *   "Write python code"
    *   "Analyze this data"
    *   "Complex reasoning"
    *   "Wake up"
    *   "Hard facts"

*   **Pinky Anchors:**
    *   "Hello"
    *   "Tell me a joke"
    *   "How are you?"
    *   "Good morning"
    *   "What do you think?"

### Implementation Steps

1.  **Update `archive_node.py`:** Add a `classify_intent(query)` tool.
    *   This tool holds the Anchor Vectors in memory (computed once at startup).
    *   Returns: `{"target": "BRAIN" | "PINKY", "confidence": float}`.
2.  **Update `acme_lab.py`:**
    *   Before entering the "Round Table", call `archive.classify_intent`.
    *   If `BRAIN`, skip Pinky's `facilitate` step and call `brain.deep_think` directly.
    *   *Crucial:* Pinky is then invoked *after* the Brain to deliver the response (maintaining the interface), or we deliver raw Brain output depending on preference.

## Benefits
*   **Speed:** Embedding lookup is ~10ms vs LLM generation ~500ms+.
*   **Control:** We can tune the `Threshold` to make the system "Eager" or "Lazy".
*   **Stability:** Math doesn't hallucinate or get stubborn.
