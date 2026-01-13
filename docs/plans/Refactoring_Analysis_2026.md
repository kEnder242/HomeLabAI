# Refactoring & Strategy Analysis (Jan 2026)

This document analyzes two backlog items identified at the close of the Clipboard Protocol phase.

---

## 1. CI/CD Migration: Shell vs. Pytest

### Current State
*   **Method:** `src/run_tests.sh` executes individual Python scripts via `subprocess`.
*   **Pros:** Simple, explicit control over server lifecycle (start/kill).
*   **Cons:** Brittle timeout logic, poor error reporting, no test discovery, difficult to manage async context.

### Proposal: Move to Pytest
We should migrate to `pytest` with `pytest-asyncio`.

#### Advantages
1.  **Fixtures:** We can write a `@pytest.fixture` that spins up the `FastMCP` server in a background process and yields a client session. This replaces the manual `start_server.sh` logic in shell scripts.
2.  **Reporting:** Detailed failure traces instead of just "Exit Code 1".
3.  **Discovery:** Just run `pytest` to find all `test_*.py` files.
4.  **Parallelism:** `pytest-xdist` could run tests in parallel (though we need to manage port conflicts).

#### Implementation Plan
1.  Create `conftest.py` in `src/`.
2.  Define a fixture `acme_server` that starts the server subprocess and kills it on teardown.
3.  Rewrite `test_cache_integration.py` as a function-based test using `await acme_server.call_tool(...)`.

---

## 2. Note Indexing Strategy: "Latest on Top"

### Context
*   **User Preference:** Personal notes in Google Drive are ordered **Reverse Chronologically** (Newest entries at the top of the file).
*   **RAG Implication:** Standard "chunking" (top-down) reads the file linearly. For a "Latest on Top" file, Chunk 1 is "Today," Chunk 2 is "Yesterday," etc.

### The Problem
If we blindly chunk a large log file:
1.  **Semantic Drift:** "Today" in Chunk 1 is not the same date as "Today" in Chunk 50.
2.  **Context Reversal:** LLMs expect narrative flow (Cause -> Effect). Reverse-chron is (Effect -> Cause). Reading a chunk might be confusing: "I fixed the bug. [Next Line] I found a bug."

### Proposed Strategy: "Header-Based Atomic Indexing"

We should **not** treat these files as continuous text streams. We should treat them as **Collections of Entries**.

#### The Algorithm
1.  **Parse:** Read the file line-by-line.
2.  **Split:** Detect Date Headers (e.g., `# 2026-01-12`).
3.  **Re-Order (Virtual):** When creating the context window for the LLM, we can present the chunks in *chronological* order if needed, OR we just index them as atomic units.
4.  **Metadata:** Each chunk must be tagged with its specific date.

#### Recommendation
Update `archive_node.py` (or the future `indexer.py`) to use a **MarkdownHeaderSplitter**.
*   **Split On:** `# YYYY-MM-DD` or similar patterns.
*   **Index:** Each day/entry becomes a separate vector document.
*   **Result:** Searching for "bug fix" finds the specific entry from Jan 12, regardless of whether it was at the top or bottom of the file.

This avoids the "Reverse Flow" problem entirely by breaking the file into independent, date-stamped units.
