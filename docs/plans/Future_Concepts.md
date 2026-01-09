# The Concept Lab (Future Concepts)

This file ("The Freezer") stores high-value ideas that are currently on hold but fit the long-term vision.

## 1. The Laboratory Intercom (Hardware Bridge)
*   **Concept:** Bringing physical devices (ESP32-S3 Box, Atom Echo) into the Lab.
*   **Role:** **Nerve Endings for Pinky.**
*   **Why:** Pinky (Right Brain) needs spatial awareness. These devices provide "presence" data (e.g., "Kitchen is noisy") even if no command is spoken.

## 2. The Direct Line (Global Push-to-Talk)
*   **Concept:** A lightweight Python client running on the Windows Desktop.
*   **Role:** **The Optic Nerve.**
*   **Why:** Allows for high-fidelity, low-latency input directly from the user's primary workspace (Coding/Gaming), bypassing the "Air Gap" of room microphones.

## 3. Subconscious Compression ("Dreaming")
*   **Concept:** Using The Brain to consolidate Pinky's raw logs into semantic wisdom.
*   **Definition:**
    *   **Sleep:** Windows Machine is Off (Power Saving).
    *   **Dreaming:** Windows Machine is **On and Active**, but the User is idle. The Brain is running a background batch job to analyze the day's events.
*   **Mechanism:**
    *   Brain queries Pinky's `ChromaDB` for the last 24h of "Raw Vectors".
    *   Brain generates a high-level summary (Narrative).
    *   Summary is stored in `SemanticDB`.
    *   Raw Vectors are purged.