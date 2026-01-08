# Feature Draft: Tiered RAG & Personality Memory

**Status:** Backlog / Concept
**Related to:** Items #15 (Memory), #16 (Intrusiveness), #17 (Tiered Summarization)
**Model Reference:** Apple CLaRa (Semantic Compression)

## Concept
Improve RAG quality and agent "memory" by moving from a flat context dump to a **Tiered Summarization** architecture. This prevents the "Context Wall" (RAG intrusiveness) and allows agents to remember weeks of conversation without hitting token limits.

## The Tiered Memory System

### Tier 1: The Raw Stream (Working Memory)
*   **Source:** Live conversation logs.
*   **Retention:** Last 5-10 turns.
*   **Format:** Exact text.

### Tier 2: The Session Summary (Short-Term Memory)
*   **Trigger:** Conversation timeout or "Goodnight" signal.
*   **Action:** Pinky uses a summarization model (or **CLaRa**) to compress the session into 5-10 bullet points.
*   **Storage:** Appended to a `history_summaries.json` file.
*   **Context:** Injected into the *next* conversation to provide continuity.

### Tier 3: The Knowledge Base (Long-Term Memory)
*   **Trigger:** Weekly or after high-value milestones.
*   **Action:** Tier 2 summaries are indexed into **ChromaDB**.
*   **Timestamps:** Metadata includes `timestamp` (Idea #17) to allow "What did we talk about last Tuesday?" queries.

## CLaRa Integration (Semantic Compression)
*   Instead of traditional RAG (which returns whole paragraphs), we use **CLaRa** to compress retrieved documents by 16x/128x.
*   **Benefit:** We can fit 10x more "Knowledge" into Pinky's prompt without hitting his 200-token output cap or slow inference.

## Intrusiveness Guard Rails (Item #16)
*   **The "Need Check" Router:** (Already implemented v1) Pinky evaluates if a query actually *needs* context before triggering the MCP/ChromaDB search.
