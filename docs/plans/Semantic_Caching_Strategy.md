# The Clipboard Protocol (Semantic Caching)

## Overview
To address the high latency and compute cost of local LLM inference (specifically "The Brain" on the 4090 Ti), HomeLabAI implements **Adaptive Semantic Caching**, known internally as **The Clipboard Protocol**.

Instead of requiring exact text matches, we embed incoming queries and search for semantically similar past questions. If a match exceeds our confidence threshold, we serve the cached response instantly, bypassing the inference step.

## Source & Inspiration
This strategy is directly adapted from:
**"Why your LLM bill is exploding — and how semantic caching can cut it by 73%"**
*By Sreenivasa Reddy Hulebeedu Reddy (VentureBeat)*

## Implementation Details

### 1. Vector Search (ChromaDB)
*   **Collection:** `semantic_cache`
*   **Tools:**
    *   `consult_clipboard(query)`: Checks for matches.
    *   `scribble_note(query, response)`: Saves new matches.
*   **Embedding Model:** `sentence-transformers/all-MiniLM-L6-v2`
*   **Metric:** Euclidean Distance (Lower is better).

### 2. Adaptive Thresholds
The article identifies that a single threshold is insufficient. We map "Similarity %" to "Euclidean Distance" approximately (where `Distance ~= 1 - Similarity`, roughly).

| Query Type | Article Rec (Similarity) | Implemented Threshold (Distance) |
| :--- | :--- | :--- |
| **FAQ (Strict)** | 0.94 | **0.35** (Current Default) |
| Support | 0.92 | 0.40 |
| Search (Broad) | 0.88 | 0.45 |
| Transactional | 0.97 | 0.15 |

*Current Setting: We use a strict `0.35` distance to ensure "FAQ-level" trust.*

### 3. Expiration (TTL) Strategy
Facts go stale. We implement a **Time-To-Live (TTL)** check on every cache hit.

*   **Default TTL:** 14 Days.
*   **Logic:** `consult_clipboard` inspects the `timestamp` metadata. If `(Now - Timestamp) > MaxAge`, the hit is discarded, and we force a re-inference.

### 4. Exclusion Rules (Safety Guardrails)
We explicitly **do not cache** queries containing volatile keywords. 
*   **Keywords:** `time`, `date`, `weather`, `status`, `current`, `now`, `latest`, `news`, `update`, `schedule`.
*   **Reasoning:** "What time is it?" is semantically identical every time, but the answer changes every second. Caching this would be disastrous.

### 5. Persona Integration
*   **"His Notes"**: The Semantic Clipboard. Pinky attributes hits to this ("I have a note...").
*   **"The Library"**: The RAG filesystem. Pinky attributes this to "Your files".
*   **Bypass:** Users can say "Ask the Brain" to force `ignore_clipboard=True`.

## Future Tuning
If we find the cache is too aggressive (false positives) or too timid (misses), we should adjust the default threshold in `archive_node.py` based on the table above.
