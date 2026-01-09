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

### The "Dreaming" Cycle
"Dreaming" is a specific active state where The Brain processes Pinky's experiences. It is **NOT** "Sleep" (Power Off).

1.  **Trigger:**
    *   **Scheduled:** 3:00 AM (Wake-on-LAN the Windows Machine).
    *   **Opportunistic:** When the User is away but the Windows Machine is already on (Idle).
2.  **The Process:**
    *   **Recall:** The Brain pulls the last 24 hours of raw vectors from Pinky's Pile.
    *   **Synthesis:** The Brain (using a prompt or CLaRa) rewrites the chaos into a narrative.
        *   *Input:* "User: list files... User: cat main.py... User: damn it... User: fix bug."
        *   *Output (The Dream):* "The User struggled with a syntax error in `main.py` regarding the asyncio loop."
    *   **Consolidation:** This summary is written to the **Semantic Store** (Long-Term).
    *   **Forgetting:** The raw "Pile" vectors are deleted or archived to cold storage.
3.  **Result:**
    *   The next day, Pinky searches the Semantic Store first. He "remembers" the struggle, not the keystrokes.

---

## 4. The Bridge (Sensory Extensions)
Since Pinky is the **Right Brain (Spatial Awareness)**, he owns the "Nerve Endings."
*   **The Intercom (ESP32):** Not a node, but a nerve. It extends Pinky's "Touch" to the kitchen.
*   **The Red Phone (Windows Client):** A direct optic nerve to the desktop environment.

Pinky aggregates these signals into the **Vibe** before The Brain ever wakes up.
