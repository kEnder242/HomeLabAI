# The Concept Lab (Future Concepts)

This file ("The Freezer") stores high-value ideas that are currently on hold but fit the long-term vision.

## 1. The Laboratory Intercom (Hardware Bridge)
*   **Concept:** Bringing physical devices (ESP32-S3 Box, Atom Echo) into the Lab.
*   **Role:** **Nerve Endings for Pinky.**
*   **Why:** Pinky (Right Brain) needs spatial awareness. These devices provide "presence" data (e.g., "Kitchen is noisy") even if no command is spoken.

## 2. The Intercom (Windows Client)
*   **Concept:** Evolving `mic_test.py` into a production-worthy utility.
*   **Role:** **The Primary Interface.**
*   **Features:**
    *   **Mode:** "Mute & Focus" toggle. `SPACE`/`ENTER` switches from Voice (Listening) to Text (Terminal).
    *   **OS Target:** Windows Native (Focus on quality/lightweight over cross-platform bloat).
    *   **Protocol:** OS-agnostic JSON over WebSocket.

## 3. The Secretary's Desk (External Comms)
*   **Philosophy:** All external signals are serialized through **Pinky**. He is the Secretary; he decides if The Brain needs to be disturbed.

### A. The Pager (Outbound)
*   **Concept:** Simple text notifications to mobile.
*   **Use Case:** "Task Complete," "Server Started."
*   **Interaction:** One-way (mostly). Listening for replies is low priority.

### B. The Fridge Note (Web UI)
*   **Concept:** A lightweight, secure web server.
*   **Use Case:** "Take a look at this URL."
*   **Interaction:** Passive. Pinky accepts the input with a tailored ACK ("Got it, I'll file it for later") without necessarily waking The Brain immediately.
*   **Security:** Obscure port, tight auth, minimal surface area.

### C. The Phone Call (Home Assistant)
*   **Concept:** Integration with Google Home Mini / Echo Dot (or hacked ESP32).
*   **Use Case:** Voice relay from other rooms.

## 4. The Research Bench (Toolkit)
*   **Concept:** Enabling The Brain to use external tools.
*   **Role:** **The Library Card.**
*   **Flow:** Pinky (Triage) -> Brain (Plan) -> Tool (Web Search) -> Brain (Analyze) -> Tool (Download Model).
*   **Constraint:** Requires solid Memory foundation first to prevent "Research Loops."

## 5. Subconscious Compression ("Dreaming")
*   **Concept:** Using The Brain to consolidate Pinky's raw logs into semantic wisdom.
*   **Definition:**
    *   **Sleep:** Windows Machine is Off (Power Saving).
    *   **Dreaming:** Windows Machine is **On and Active**, but the User is idle. The Brain is running a background batch job to analyze the day's events.
*   **Mechanism:**
    *   Brain queries Pinky's `ChromaDB` for the last 24h of "Raw Vectors".
    *   Brain generates a high-level summary (Narrative).
    *   Summary is stored in `SemanticDB`.
    *   Raw Vectors are purged.