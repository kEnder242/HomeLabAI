# Acme Lab: Debug Insights & Operational Wins (Updated Feb 13)

## 🏛️ The Lab Attendant Pattern
- Stable HTTP API for lifecycle management. Hero of the Marathon Sprint. Provides a clean "Truth Anchor" for system state.

## 🛠️ Strategic Patching
- Atomic hunks are mandatory. Large patches fail on minor context shifts. The "Strategic Architect's Scalpel" is much more reliable than brittle string replacement.

## 🔄 The Sync-Flush Pattern (Platform Workaround)
- **Problem:** Stale tool output bleeding into new turns during high-load sessions.
- **Solution:** Use `echo "SYNC_ID"` to flush the platform's response buffer if output looks mismatched.
- **BKM:** Always verify turn-intent by checking for specific description strings in the output.

## 🧪 Bicameral Test Design (The Consensus Rule)
- **Problem:** Stream-based interfaces (WebSockets) leave "ghost messages" if only one agent response is consumed by a test script.
- **Solution:** Tests MUST wait for the full agent chain (e.g., Pinky Notice + Brain Vibe Check) to complete before proceeding. This ensures the pipe is empty for the sub-tasks or next interaction.
