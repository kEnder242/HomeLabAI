# Research & Inspiration

A curated list of ideas, models, and articles to explore for the Home Lab AI project.

## Models to Evaluate

*   **[NVIDIA Nemotron-Speech-Streaming-0.6b](https://huggingface.co/nvidia/nemotron-speech-streaming-en-0.6b)**
    *   **Status:** **Active / In Use.**
    *   **Why:** Currently powering our "Hearing" layer. We should keep an eye on updates or fine-tunes.

*   **[Apple CLaRa-7B-Instruct](https://huggingface.co/apple/CLaRa-7B-Instruct/blob/main/README.md)**
    *   **Category:** RAG / Compression
    *   **Why:** A RAG model with built-in semantic compression (16x - 128x).
    *   **Relevance:** Directly addresses **Idea #17 (Tiered Summarization)** and **#16 (RAG Improvements)**. Could allow Pinky (Linux) to hold vast amounts of context in limited VRAM.

*   **[Top 5 Small AI Coding Models](https://www.kdnuggets.com/top-5-small-ai-coding-models-that-you-can-run-locally)**
    *   **Category:** Coding / Edge
    *   **Models:** gpt-oss-20b, Qwen3-VL-32B, Apriel-1.5-15B-Thinker.
    *   **Why:** Highlights "Thinker" models designed for stepwise reasoning.
    *   **Relevance:** Potential upgrades for "The Brain" or "Pinky" (if smaller 7B versions exist).

## Agent Architecture & Orchestration

*   **[Recursive Language Models (RLMs)](https://www.marktechpost.com/2026/01/02/recursive-language-models-rlms-from-mits-blueprint-to-prime-intellects-rlmenv-for-long-horizon-llm-agents/?amp)**
    *   **Category:** Architecture
    *   **Key Concept:** Treat context as an external string to be "read" via code, not just ingested.
    *   **Relevance:** Supports our **Tiered Memory** plan. Pinky shouldn't just "have" memory; he should "read" it via tools.

*   **[Local Multi-Agent Orchestration with TinyLlama](https://www.marktechpost.com/2025/12/05/how-to-design-a-fully-local-multi-agent-orchestration-system-using-tinyllama-for-intelligent-task-decomposition-and-autonomous-collaboration/?amp)**
    *   **Category:** Architecture
    *   **Key Concept:** Use tiny models (1B-3B) for *routing* and *decomposition*, preserving big models for execution.
    *   **Relevance:** Validates our "Pinky (Small) -> Brain (Large)" architecture. Suggests we could optimize Pinky further.

*   **[Oh My OpenCode](https://github.com/code-yeongyu/oh-my-opencode/blob/dev/README.md)**
    *   **Category:** Agent Framework / Tooling
    *   **Why:** Advanced orchestration with "Frontend Engineer", "Librarian", etc.
    *   **Relevance:** A reference for how "The Brain" should handle complex coding requests. Also features **Token Efficiency** (Idea #7).

## RAG & Knowledge Management

*   **[Open Source NotebookLM Alternative (OpenNotebook)](https://www.zdnet.com/article/i-found-an-open-source-notebooklm-alternative-thats-powerful-private-and-free/)**
    *   **Category:** RAG App
    *   **Why:** Private, local RAG with "podcast" style interaction.
    *   **Relevance:** Validates our goal of a personal, voice-driven knowledge assistant.

## Developer Experience & Best Practices

*   **[Vibe Coding in Style](https://evilmartians.com/chronicles/vibe-coding-in-style-dot-md)**
    *   **Category:** Workflow
    *   **Key Idea:** `AGENTS.md` - A file in the repo that defines coding style and patterns for the AI.
    *   **Relevance:** **We should implement this immediately.** An `AGENTS.md` file will help The Brain write code that matches our style without constant reprompting.