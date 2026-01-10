# Acme Lab: The Architecture of Two Minds

**Date:** January 9, 2026
**Theme:** The Bicameral Mind (Right & Left Hemispheres)

## 1. The Core Analogy
We are modeling a bicameral mind using distinct hardware nodes. This aligns perfectly with the "Pinky and the Brain" personas.

### 🐹 Pinky: The Right Hemisphere (The Experience Engine)
*   **Hardware:** Local Linux (Low Latency, Always On, Close to Sensors).
*   **Cognitive Style:** **Holistic, Emotional, Spatial, Intuitive, "The Vibe".**
*   **Role:**
    *   **Sensory Cortex:** He feels the room (Mic, Presence, "User sounds angry").
    *   **Wernicke’s Area (Prosody):** He understands *how* something is said, not just *what*.
    *   **The Interface:** He manages the boundary between the User and the Machine.
    *   **The Improviser:** He handles "Narf!" (Randomness/Creativity) and keeping the flow alive.

### 🧠 The Brain: The Left Hemisphere (The Reasoning Engine)
*   **Hardware:** Remote Windows GPU (High Power, Burst, Isolated).
*   **Cognitive Style:** **Linear, Logical, Mathematical, Abstract, "The Truth".**
*   **Role:**
    *   **Broca’s Area (Production):** He constructs complex, structured outputs (Code, Plans).
    *   **The Simulator:** He runs mental models and simulations.
    *   **The Archivist:** He turns chaotic experiences into structured Long-Term Memory.
    *   **The Critic:** He corrects Pinky's hallucinations with hard facts.

---

## 2. The Corpus Callosum (The Shared Context)
The connection between them (`acme_lab.py`) is not just a pipe; it is a **Translator**. It must convert Pinky's "Vibes" into The Brain's "Parameters".

**The Shared Context Object (SCO):**
```json
{
  "hemisphere_state": {
    "right_vibe": "User is rushing, environment is noisy",
    "left_focus": "Debugging python script 'main.py'"
  },
  "short_term_memory": [
    {"source": "Pinky", "type": "sensation", "content": "Loud noise detected"},
    {"source": "Brain", "type": "fact", "content": "Python 3.12 syntax requires..."}
  ],
  "coordination": {
    "current_turn": "Pinky",
    "interrupt_level": "high"
  }
}
```

*   **Pinky Writes:** "User sounds frustrated."
*   **The System Translates:** `frustrated` -> `Brain Prompt: Be concise, avoid lecture.`
*   **Brain Reads:** "User is frustrated. I will give the answer directly."

---

## 3. Subconscious Compression ("Dreaming")
This is the mechanism for Long-Term Memory consolidation.

### The Problem
Pinky (Right Brain) collects **Episodic Memory**—a chaotic stream of raw audio transcripts, half-finished thoughts, and sensory data ("The Pile"). This is stored in `ChromaDB`.

### The "Dreaming" Cycle (Implemented)
"Dreaming" is a specific active state where The Brain processes Pinky's experiences. It is **NOT** "Sleep" (Power Off).

*   **Implementation:** `src/dream_cycle.py` (The Dreamer).
*   **Workflow:**
    1.  **Recall:** `get_stream_dump` tool pulls raw logs from `short_term_stream`.
    2.  **Synthesis:** The Brain synthesizes a narrative summary focused on goals, progress, and struggles.
    3.  **Consolidation:** `dream` tool saves summary to `long_term_wisdom` and purges the stream.
*   **Result:** The "Pile" is cleared, and the "Wisdom" collection is updated with semantic insights.

---

## 4. The Bridge (Sensory Extensions)
Since Pinky is the **Right Brain (Spatial Awareness)**, he owns the "Nerve Endings."
*   **The Intercom (ESP32):** Not a node, but a nerve. It extends Pinky's "Touch" to the kitchen.
*   **The Red Phone (Windows Client):** A direct optic nerve to the desktop environment.

Pinky aggregates these signals into the **Vibe** before The Brain ever wakes up.
