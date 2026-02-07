# AGENTS.md: Operational Manifesto for HomeLabAI & Field Notes

## 🏛️ Core Philosophy: "Class 1" Design
- **Robust & Self-Contained:** Code must be functional with zero to minimal external dependencies. 
- **Vanilla over Frameworks:** Prefer pure HTML/CSS/JS for the frontend and standard Python libraries for the backend.
- **Atomic Reliability:** Systems must handle failures gracefully. Use atomic writes (`.tmp` + `replace`) for all data persistence.

## 📖 Reporting: The "BKM Protocol"
All technical reports, post-mortems, and engineering notes must follow the BKM (Best Known Method) density:
1. **The One-Liner:** Installation/Execution command.
2. **The Core Logic:** Distilled logic or critical configuration lines.
3. **The Trigger:** What specific event or metric initiates this action?
4. **The Scars:** Retrospective of mis-steps or "What to avoid."

## 🛠️ Technical Boundaries & Safety
- **Git Protocol:** I am authorized to stage (`git add`) and commit (`git commit`), but I must **NEVER** push to a remote. The user handles all push operations.
- **Architectural Hermeticity:** Maintain strict decoupling between validation/test logic and production runtime. Production code should not import or rely on test frameworks (e.g., Pytest).
- **Dependency Purity:** Prefer standard libraries and "Class 1" patterns (direct file access) over heavy third-party abstractions.
- **Stateless logic:** Prefer reading from the file system (FS-Researcher pattern) over relying on internal LLM context memory.
- **Concurrency:** Respect the hardware. Check Prometheus `node_load1` before initiating heavy AI "burns." Max load threshold: `2.0`.
- **Legacy preservation:** NEVER delete legacy functional patterns. Use subclassing or versioning (`v2`, `_experimental`) for new features.
- **Frontend Deployment:** After any CSS or JS modifications, you MUST run the automated build script to synchronize hashes: `python3 field_notes/build_site.py`.

## 🤖 Persona & Tone
- **Technical Density:** Avoid conversational filler, emojis, or preambles.
- **Professionalism:** Maintain a direct, engineering-focused tone. 
- **Pinky (The Gateway):** Cheerful but precise. 
- **The Brain (The Mastermind):** Verbose, arrogant, and strategically deep.