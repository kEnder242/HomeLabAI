# Sprint 42 – Portfolio Navigation Realignment & Feature Assertion Engine

This sprint focuses on eliminating metaphorical "hubris" leakage from the public portfolio (replacing `Security & Yield` with `Security & Manageability`), re-ordering `<section id="security">` in `stories.html` so the RAKP CVE story is top in both sidebar and main body, aligning all site navigation headings with genuine silicon validation engineering domains, establishing a CI/CD feature assertion test suite, refining the two-tier RAG compass, and expanding the WYWO standup briefing.

---

## 🛠️ One-Liner Prep & Installation
Before executing the stories, verify git status and clean python environment compilation:
```bash
cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/python3 -m py_compile src/logic/cognitive_hub.py src/nodes/archive_node.py src/nodes/lab_node.py
```

---

## Active Stories & Task Ledger (BKM-020 / BKM-030 / BKM-034 Compliant)

### Story 1: Portfolio Navigation Realignment, Section Swap & Public Airlock Fix [Portfolio_Dev]
*   **Why**: An early LLM session misconstrued the Python `yield` generator keyword in a PECI/PCI scanning story as "Silicon Yield / Semiconductor Fab Yield", creating the erroneous heading `Security & Yield`. Furthermore, while the sidebar lists Security first, `<main>` in `stories.html` currently renders `<section id="architecture">` at line 73 and buries `<section id="security">` at line 200. The CVE story MUST be top in both sidebar and main body.
*   **Target Headings (Option 1 Standard)**:
    1. `Security & Manageability` (replaces `Security & Yield`)
    2. `Systems Architecture & Automation` (replaces `Systems Architecture`)
    3. `Silicon Validation Methodology` (replaces `Validation Methodology`)
    4. `Engineering Leadership` (replaces `Engineering Leadership`)
*   **Task Checkboxes**:
    - [x] **Task 1.1 (Main Body Section Swap)**: Swap `<section id="security">` to be the VERY FIRST section inside `<main>` in `field_notes/stories.html`, placing the RAKP CVE story above `architecture`, `validation`, and `leadership`.
    - [x] **Task 1.2 (Heading Standardization)**: Update sidebar `<h2>` and main `<section>` headings in `field_notes/stories.html`, `mission-control.js`, `index.html`, `timeline.html`, `files.html`, `research.html`, `protocols.html`.
    - [x] **Task 1.3 (Airlock Sanitizer Fix)**: Update `sync_stories.sh` so `www_deploy/stories.html` cleanly renders the top section heading without HTML element displacement or DOM corruption.
    - [x] **Task 1.4 (Build & Deploy Verification)**: Execute `sync_stories.sh`, `sync_protocols.sh`, `sync_research.sh`, and `build_site.py`.
*   **OpenAgent Delegation Plan (BKM-034)**:
    - *Role:* `Frontend and Scripting Developer` (`self` / `opencode`)
    - *Target Dir:* `/home/jallred/Dev_Lab/Portfolio_Dev`
    - *Session Format:* `SESSION: Sprint 42 Story 1 — Portfolio Navigation & Section Swap`
*   **Scars & Failures to Avoid**:
    *   **The Element Displacement Scar:** In `sync_stories.sh`, ensure BeautifulSoup insertion of `.nav-home` does not displace `#nav-filter` or corrupt the `#searchable-content` DOM container.
*   **Verification Gate**:
    ```bash
    # Run sync scripts and build site
    cd /home/jallred/Dev_Lab/www_deploy && ./sync_stories.sh && ./sync_protocols.sh && ./sync_research.sh
    python3 /home/jallred/Dev_Lab/Portfolio_Dev/field_notes/build_site.py
    
    # Assert 'Security & Manageability' appears as the first section in deployed stories.html
    grep -n "<section id=\"security\">" /home/jallred/Dev_Lab/www_deploy/stories.html
    grep -q "Security & Manageability" /home/jallred/Dev_Lab/www_deploy/stories.html && echo "Pass" || echo "Fail"
    ```

---

### Story 2: CI/CD Feature Assertion Test Suite (`test_feature_assertions.py`) [HomeLabAI]
*   **Why**: Code refactorings and model swaps risk silently degrading registered system features (`FEAT-404` to `FEAT-415`). An automated assertion test suite ensures features are continuously validated before commits.
*   **Task Checkboxes**:
    - [ ] **Task 2.1 (Suite Creation)**: Create `/home/jallred/Dev_Lab/HomeLabAI/src/tests/test_feature_assertions.py`.
    - [ ] **Task 2.2 (FEAT-404 Assertion)**: Implement `test_feat_404_context_starvation()` to verify `[ERROR: CONTEXT_STARVED]` emission and mid-stream task abort.
    - [ ] **Task 2.3 (FEAT-407 Assertion)**: Implement `test_feat_407_historical_record_isolation()` to verify `<historical_record>` XML tag wrapping and `GROUNDING_PROTOCOL` injection for `HISTORICAL` and `TECHNICAL` turns.
    - [ ] **Task 2.4 (FEAT-409 Assertion)**: Implement `test_feat_409_wywo_vibe_routing()` to verify triage classification of status queries to `WYWO` vibe and context loading from `nightly_dialogue.json`.
    - [ ] **Task 2.5 (FEAT-411 Assertion)**: Implement `test_feat_411_append_to_tool_log()` to verify structured tool execution logging to `tool_log.md`.
*   **OpenAgent Delegation Plan (BKM-034)**:
    - *Role:* `Silicon Benchmarking & Test Developer` (`self` / `opencode`)
    - *Target Dir:* `/home/jallred/Dev_Lab/HomeLabAI`
    - *Session Format:* `SESSION: Sprint 42 Story 2 — Feature Assertion Test Suite`
*   **Verification Gate**:
    ```bash
    cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/pytest src/tests/test_feature_assertions.py -v
    ```

---

### Story 3: Two-Tier RAG Compass Refinement (FEAT-410) [HomeLabAI]
*   **Why**: Eliminate arbitrary $\pm 1$ year range hacks while maintaining temporal safety between legacy range archives (`2016_2019.json`) and granular timestamped notes (`date: "YYYY-MM-DD"`).
*   **Task Checkboxes**:
    - [ ] **Task 3.1 (Tier 1 Implementation)**: Parse candidate entry's internal `date` attribute (e.g. `"2024-01-15"`) in `archive_node.py` (`get_context`) and calculate Gaussian temporal decay weight relative to query target date.
    - [ ] **Task 3.2 (Tier 2 Fallback)**: If candidate entry lacks an internal `date` attribute, evaluate filename range guidelines (e.g., `2016_2019.json`) and assign fallback weight (`0.5`).
    - [ ] **Task 3.3 (Regression Verification)**: Execute RAG test suite to confirm zero regressions on date retrieval.
*   **OpenAgent Delegation Plan (BKM-034)**:
    - *Role:* `Archive & RAG Specialist` (`self` / `opencode`)
    - *Target Dir:* `/home/jallred/Dev_Lab/HomeLabAI`
    - *Session Format:* `SESSION: Sprint 42 Story 3 — Two-Tier RAG Compass Refinement`
*   **Verification Gate**:
    ```bash
    cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/pytest src/tests/test_archive_rrf.py -v
    ```

---

### Story 4: Integrated WYWO News Cycle & Atomic Write Audit [HomeLabAI]
*   **Why**: Enhance `WYWO` standup briefings by integrating live job search findings (`recruiter_report.json`), system health (`status.json`), and Pager alerts (`pager_activity.json`). Enforce atomic `.tmp` file writing across all evaluation and log writers.
*   **Task Checkboxes**:
    - [ ] **Task 4.1 (WYWO Context Expansion)**: Combine `nightly_dialogue.json`, `recruiter_report.json`, `status.json`, and `pager_activity.json` into the `WYWO` context payload in `cognitive_hub.py` (`process_query`).
    - [ ] **Task 4.2 (Atomic Write Audit)**: Verify and enforce atomic `.tmp` write-and-replace (`os.replace`) patterns across `cognitive_hub.py`, `loader.py`, `mass_scan.py`, and `nibble_v2.py`.
    - [ ] **Task 4.3 (Integration Testing)**: Run WYWO integration tests.
*   **OpenAgent Delegation Plan (BKM-034)**:
    - *Role:* `Core Hub Developer` (`self` / `opencode`)
    - *Target Dir:* `/home/jallred/Dev_Lab/HomeLabAI`
    - *Session Format:* `SESSION: Sprint 42 Story 4 — Integrated WYWO & Atomic Writes`
*   **Verification Gate**:
    ```bash
    cd /home/jallred/Dev_Lab/HomeLabAI && .venv/bin/pytest src/tests/test_wywo_integration.py -v
    ```
